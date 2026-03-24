"""Track ArgoCD app health across cycles to detect stuck states.

Persists to /opt/sentinel-agent/state/app-health-history.json.
If an app has been Progressing or Degraded for 2+ consecutive cycles
(10+ minutes), it's stuck — not a normal rollout.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_STATE_PATH = "/opt/sentinel-agent/state/app-health-history.json"
MAX_ENTRIES_PER_APP = 5
STUCK_THRESHOLD = 2  # consecutive cycles before flagging


def load_health_history(config: dict) -> dict:
    """Load app health history from state file.

    Returns dict: {app_name: [{cycle, health, sync}, ...]}
    Handles missing/corrupt file gracefully.
    """
    path = _state_path(config)
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_health_history(config: dict, history: dict,
                        log: Optional[logging.Logger] = None):
    """Save app health history, pruning to MAX_ENTRIES_PER_APP."""
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Prune old entries
    pruned = {}
    for app, entries in history.items():
        pruned[app] = entries[-MAX_ENTRIES_PER_APP:]

    try:
        with open(path, "w") as f:
            json.dump(pruned, f, indent=2)
    except OSError as e:
        if log:
            log.error(f"Failed to write health history: {e}")


def record_app_health(history: dict, app_name: str,
                      health: str, sync: str) -> dict:
    """Record current cycle's health for an app."""
    if app_name not in history:
        history[app_name] = []

    history[app_name].append({
        "cycle": datetime.now(timezone.utc).isoformat(),
        "health": health,
        "sync": sync,
    })

    return history


def is_stuck(history: dict, app_name: str,
             statuses: set = None) -> bool:
    """Check if app has been in a problem state for 2+ consecutive cycles.

    Args:
        history: full health history dict
        app_name: app to check
        statuses: set of health statuses considered "stuck" (default: Progressing, Degraded)
    """
    if statuses is None:
        statuses = {"progressing", "degraded", "missing"}

    entries = history.get(app_name, [])
    if len(entries) < STUCK_THRESHOLD:
        return False

    # Check last N entries
    recent = entries[-STUCK_THRESHOLD:]
    return all(e["health"].lower() in statuses for e in recent)


def clear_app(history: dict, app_name: str) -> dict:
    """Clear history for an app that's recovered."""
    history.pop(app_name, None)
    return history


def _state_path(config: dict) -> Path:
    """Get state file path from config."""
    return Path(config.get("agent", {}).get(
        "state_dir", "/opt/sentinel-agent/state"
    )) / "app-health-history.json"
