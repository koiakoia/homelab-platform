"""Escalation actions — Plane comment + ntfy notification.

Used when a signal is outside sentinel-agent's authority or
cannot be classified by rules/LLM.
"""

import logging

import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models import Signal, ActionResult
from notify.ntfy import send_ntfy


def escalate(signal: Signal, config: dict, secrets: dict,
             log: logging.Logger) -> ActionResult:
    """Escalate a signal via Plane comment + ntfy push.

    1. Post diagnosis + proposed action as Plane issue comment
    2. Fire ntfy push with issue link
    """
    # Build escalation message
    message = _build_escalation_message(signal)

    # Post to Plane — dedup: check for existing open issue first
    plane_success = False
    if signal.plane_issue_id:
        plane_success = _comment_on_plane(
            signal.plane_issue_id, message, config, secrets, log
        )
    else:
        # Check for existing open issue with same signal (dedup)
        existing_id = _find_existing_escalation(signal, config, secrets, log)
        if existing_id:
            log.info(f"Dedup: found existing escalation issue, commenting instead of creating")
            plane_success = _comment_on_plane(existing_id, message, config, secrets, log)
            signal.plane_issue_id = existing_id
        else:
            issue_id = _create_plane_issue(signal, message, config, secrets, log)
            if issue_id:
                signal.plane_issue_id = issue_id
                plane_success = True

    # Fire ntfy
    ntfy_priority = _signal_to_ntfy_priority(signal)
    issue_ref = signal.source_id or signal.plane_issue_id or "unknown"
    ntfy_msg = f"[ESCALATE] {issue_ref}: {signal.summary}"

    send_ntfy(config, ntfy_msg, priority=ntfy_priority)

    return ActionResult(
        signal=signal,
        action_taken=f"escalated priority={ntfy_priority}",
        success=plane_success,
        evidence=f"Plane comment posted, ntfy priority {ntfy_priority} sent",
        error="" if plane_success else "Plane comment failed",
    )


def _build_escalation_message(signal: Signal) -> str:
    """Build a human-readable escalation message."""
    return (
        f"<p><strong>ESCALATION</strong> — sentinel-agent needs operator input</p>"
        f"<p><strong>Signal:</strong> {signal.summary}</p>"
        f"<p><strong>Source:</strong> {signal.source.value} "
        f"(ID: {signal.source_id})</p>"
        f"<p><strong>Severity:</strong> {signal.severity}</p>"
        f"<p><strong>Why escalating:</strong> Outside autonomous authority "
        f"or unclassified signal pattern</p>"
        f"<p><strong>Raw data (excerpt):</strong></p>"
        f"<pre>{_safe_json(signal.raw_data)}</pre>"
        f"<p><strong>Recommended:</strong> Review and assign to appropriate "
        f"agent/role or handle manually.</p>"
    )


def _safe_json(data: dict, max_len: int = 500) -> str:
    """JSON-serialize with truncation for HTML display."""
    import json
    text = json.dumps(data, indent=2)
    if len(text) > max_len:
        text = text[:max_len] + "\n... (truncated)"
    return text


def _comment_on_plane(issue_id: str, comment_html: str,
                      config: dict, secrets: dict,
                      log: logging.Logger) -> bool:
    """Post a comment on an existing Plane issue."""
    api_key = secrets.get("plane_api_key")
    if not api_key:
        log.warning("No Plane API key for escalation comment")
        return False

    plane_cfg = config["plane"]
    url = (f"{plane_cfg['base_url']}/workspaces/{plane_cfg['workspace_slug']}"
           f"/projects/{plane_cfg['project_id']}/issues/{issue_id}/comments/")

    try:
        resp = requests.post(
            url,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={"comment_html": comment_html},
            timeout=15,
        )
        resp.raise_for_status()
        log.info(f"Escalation comment posted to issue {issue_id}")
        return True
    except Exception as e:
        log.error(f"Failed to post escalation comment: {e}")
        return False


def _find_existing_escalation(signal: Signal, config: dict, secrets: dict,
                               log: logging.Logger) -> str:
    """Search Plane for an open issue matching this signal.

    Returns issue UUID if a matching issue exists (created within last hour,
    still in Todo/In Progress state). Otherwise returns empty string.
    """
    from datetime import datetime, timezone, timedelta

    api_key = secrets.get("plane_api_key")
    if not api_key:
        return ""

    plane_cfg = config["plane"]
    url = (f"{plane_cfg['base_url']}/workspaces/{plane_cfg['workspace_slug']}"
           f"/projects/{plane_cfg['project_id']}/issues/")

    # Search for issues with sentinel-agent prefix matching this signal
    search_term = signal.summary[:60]

    try:
        resp = requests.get(
            url,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            params={"search": "sentinel-agent"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"Dedup search failed: {e}")
        return ""

    data = resp.json()
    results = data.get("results", data) if isinstance(data, dict) else data

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    for issue in results:
        name = issue.get("name", "")
        if "[sentinel-agent]" not in name:
            continue

        # Check if signal summary matches (fuzzy: first 40 chars of summary)
        signal_prefix = signal.summary[:40].lower()
        issue_signal = name.replace("[sentinel-agent] ", "").lower()
        if signal_prefix not in issue_signal and issue_signal[:40] not in signal_prefix:
            continue

        # Check if still open (unstarted or started state groups)
        state_detail = issue.get("state_detail", {})
        state_group = ""
        if isinstance(state_detail, dict):
            state_group = state_detail.get("group", "")

        if state_group in ("completed", "cancelled"):
            continue

        # Check if created within last hour
        created = issue.get("created_at", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if created_dt < one_hour_ago:
                    continue  # Too old, re-escalate
            except (ValueError, TypeError):
                pass

        log.info(f"Dedup match: OPS-{issue.get('sequence_id')} ({issue['id'][:8]}...)")
        return issue["id"]

    return ""


def _create_plane_issue(signal: Signal, description: str,
                        config: dict, secrets: dict,
                        log: logging.Logger) -> str:
    """Create a new Plane issue for an untracked signal. Returns issue UUID."""
    api_key = secrets.get("plane_api_key")
    if not api_key:
        return ""

    plane_cfg = config["plane"]
    url = (f"{plane_cfg['base_url']}/workspaces/{plane_cfg['workspace_slug']}"
           f"/projects/{plane_cfg['project_id']}/issues/")

    priority = "high" if signal.severity >= 10 else "medium"

    try:
        resp = requests.post(
            url,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "name": f"[sentinel-agent] {signal.summary[:100]}",
                "description_html": description,
                "priority": priority,
            },
            timeout=15,
        )
        resp.raise_for_status()
        issue_id = resp.json().get("id", "")
        seq = resp.json().get("sequence_id", "?")
        log.info(f"Created Plane issue OPS-{seq} for escalation")
        return issue_id
    except Exception as e:
        log.error(f"Failed to create Plane issue: {e}")
        return ""


def _signal_to_ntfy_priority(signal: Signal) -> int:
    """Map signal to ntfy priority level.

    5 (urgent): Vault sealed, multiple services down, security from internal IP
    4 (high): Fix failed, compliance regression >= 5
    3 (default): Routine escalation, new issue
    2 (low): Heartbeat
    """
    if signal.severity >= 14:
        return 5
    if signal.severity >= 10:
        return 4
    if signal.severity >= 6:
        return 3
    return 2
