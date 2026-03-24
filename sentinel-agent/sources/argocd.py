"""Poll ArgoCD API for unhealthy or out-of-sync applications.

Uses cross-cycle state to detect stuck Progressing/Degraded apps.
An app must be in a problem state for 2+ consecutive cycles (10+ min)
before the agent acts — transient states are normal rollout behavior
that ArgoCD handles automatically.
"""

import logging

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models import Signal, SignalSource, Tier
from state.health_history import (
    load_health_history, save_health_history,
    record_app_health, is_stuck, clear_app,
)


def poll_argocd(config: dict, secrets: dict, log: logging.Logger) -> list[Signal]:
    """Poll ArgoCD for applications with health or sync problems.

    Uses cross-cycle state persistence to distinguish transient
    from stuck states:
    - OutOfSync + no SyncError → Tier 1 (skip, auto-sync handles)
    - Degraded/Progressing for 1 cycle → log only, no action
    - Degraded/Progressing for 2+ cycles → Tier 2 (stuck, act)
    - SyncFailed/ComparisonError → Tier 3 (may need manifest fix)
    """
    argocd_cfg = config["argocd"]
    api_url = argocd_cfg["api_url"]

    # Authenticate
    token = secrets.get("argocd_token")
    if not token:
        token = _get_argocd_session_token(argocd_cfg, secrets, log)
    if not token:
        log.warning("No ArgoCD credentials — skipping ArgoCD poll")
        return []

    try:
        resp = requests.get(
            f"{api_url}/applications",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
    except (requests.ConnectionError, requests.Timeout) as e:
        log.warning(f"ArgoCD unreachable: {e}")
        return []
    except requests.HTTPError as e:
        log.error(f"ArgoCD API error: {e}")
        return []

    data = resp.json()
    apps = data.get("items", [])

    sync_error_statuses = set(s.lower() for s in argocd_cfg.get(
        "sync_error_statuses", ["SyncFailed", "ComparisonError"]))

    # Load cross-cycle state
    history = load_health_history(config)

    signals = []
    healthy_apps = set()

    for app in apps:
        metadata = app.get("metadata", {})
        app_name = metadata.get("name", "unknown")
        status = app.get("status", {})

        health = status.get("health", {})
        health_status = health.get("status", "Unknown")

        sync = status.get("sync", {})
        sync_status = sync.get("status", "Unknown")

        op_state = status.get("operationState", {})
        phase = op_state.get("phase", "").lower()
        sync_error = phase in sync_error_statuses

        health_lower = health_status.lower()
        is_healthy = health_lower == "healthy"
        is_progressing = health_lower == "progressing"
        is_degraded = health_lower in ("degraded", "missing")
        is_outofsync = sync_status.lower() == "outofsync"

        # Track healthy apps to clear their history
        if is_healthy and not is_outofsync and not sync_error:
            healthy_apps.add(app_name)
            continue

        # Record non-healthy state in history
        if is_progressing or is_degraded:
            record_app_health(history, app_name, health_status, sync_status)

        # --- Classification ---

        # OutOfSync + Healthy → Tier 1 skip (auto-sync)
        if is_outofsync and not sync_error and is_healthy:
            signals.append(_make_signal(app_name, health_status, sync_status,
                                        sync_error, health, metadata, Tier.SKIP, 3))
            continue

        # OutOfSync + not healthy but no sync error → Tier 1 skip
        if is_outofsync and not sync_error and not is_degraded:
            signals.append(_make_signal(app_name, health_status, sync_status,
                                        sync_error, health, metadata, Tier.SKIP, 3))
            continue

        # SyncFailed → Tier 3 immediately (manifest issue, no point waiting)
        if sync_error:
            signals.append(_make_signal(app_name, health_status, sync_status,
                                        sync_error, health, metadata, Tier.GIT_CHANGE, 8))
            continue

        # Progressing or Degraded — check persistence
        if is_progressing or is_degraded:
            if is_stuck(history, app_name):
                # Stuck for 2+ cycles → act
                label = "stuck rollout" if is_progressing else "persistent degradation"
                log.info(f"ArgoCD {app_name}: {label} (2+ cycles)")
                signals.append(Signal(
                    source=SignalSource.ARGOCD,
                    source_id=f"argocd-{app_name}",
                    summary=f"ArgoCD {app_name}: {label} — "
                            f"health={health_status}, sync={sync_status}",
                    severity=10,
                    tier=Tier.OPERATIONAL,
                    raw_data={
                        "app_name": app_name,
                        "health_status": health_status,
                        "sync_status": sync_status,
                        "sync_error": sync_error,
                        "phase": phase,
                        "stuck": True,
                        "message": health.get("message", ""),
                        "namespace": metadata.get("namespace", "argocd"),
                    },
                ))
            else:
                # First cycle seeing this — log but don't act
                log.info(f"ArgoCD {app_name}: {health_status} (first cycle, monitoring)")
            continue

    # Clear history for recovered apps
    for app_name in healthy_apps:
        clear_app(history, app_name)

    # Save updated history
    save_health_history(config, history, log)

    log.info(f"ArgoCD: found {len(signals)} apps needing attention")
    return signals


def _make_signal(app_name: str, health_status: str, sync_status: str,
                 sync_error: bool, health: dict, metadata: dict,
                 tier: Tier, severity: int) -> Signal:
    """Create a Signal for an ArgoCD app."""
    return Signal(
        source=SignalSource.ARGOCD,
        source_id=f"argocd-{app_name}",
        summary=f"ArgoCD {app_name}: health={health_status}, "
                f"sync={sync_status}"
                f"{', sync_error' if sync_error else ''}",
        severity=severity,
        tier=tier,
        raw_data={
            "app_name": app_name,
            "health_status": health_status,
            "sync_status": sync_status,
            "sync_error": sync_error,
            "message": health.get("message", ""),
            "namespace": metadata.get("namespace", "argocd"),
        },
    )


def _get_argocd_session_token(argocd_cfg: dict, secrets: dict,
                               log: logging.Logger) -> str:
    """Get ArgoCD session token via username/password auth."""
    import subprocess

    api_url = argocd_cfg["api_url"]
    username = argocd_cfg.get("admin_user", "admin")
    password = secrets.get("argocd_password", "")

    if not password and "password_from_secret" in argocd_cfg:
        secret_cfg = argocd_cfg["password_from_secret"]
        try:
            kubeconfig = argocd_cfg.get("kubeconfig", "/home/sentinel-agent/.kube/config")
            result = subprocess.run(
                ["oc", f"--kubeconfig={kubeconfig}",
                 "get", "secret", secret_cfg["secret_name"],
                 "-n", secret_cfg["namespace"],
                 "-o", "json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                import base64, json
                secret_data = json.loads(result.stdout).get("data", {})
                encoded = secret_data.get(secret_cfg["key"], "")
                if encoded:
                    password = base64.b64decode(encoded).decode()
        except Exception as e:
            log.warning(f"Failed to read ArgoCD password from OKD secret: {e}")

    if not password:
        return ""

    try:
        resp = requests.post(
            f"{api_url}/session",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        token = resp.json().get("token", "")
        if token:
            log.info("ArgoCD session token obtained")
        return token
    except Exception as e:
        log.warning(f"ArgoCD session auth failed: {e}")
        return ""
