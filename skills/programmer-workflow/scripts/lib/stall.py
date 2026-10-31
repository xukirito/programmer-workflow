"""Lightweight stall counters.

The model still decides what counts as a failed round, but persisting a small
counter makes the "3 rounds" and "bug still not fixed" triggers reliable across
turns and context loss.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .common import atomic_write_json, ensure_dir, load_plugin_config, locked, now_iso, read_json, workspace_state

THRESHOLDS = {"satisfaction": 3, "bugfix": 2}
TRACKS = tuple(THRESHOLDS)
STALE_AFTER = timedelta(hours=8)


def thresholds(workspace: Path | None = None) -> dict[str, int]:
    cfg = load_plugin_config(workspace)
    return {
        "satisfaction": max(1, min(10, int(cfg.get("satisfactionThreshold", 3)))),
        "bugfix": max(1, min(10, int(cfg.get("bugfixThreshold", 2)))),
    }


def _state_path(workspace: Path | None = None) -> Path:
    return workspace_state(workspace) / "stall.json"


def _key(session: str | None = None) -> str:
    session = session or os.environ.get("DSH_SESSION_ID") or os.environ.get("KIMI_SESSION_ID") or "default"
    return session


def _default() -> dict[str, Any]:
    return {"schema": 1, "sessions": {}}


def _load(path: Path) -> dict[str, Any]:
    data = read_json(path, _default()) or _default()
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
        return _default()
    return data


def _fresh(entry: dict[str, Any]) -> bool:
    try:
        last = datetime.fromisoformat(str(entry.get("last_at")))
        if last.tzinfo is None:
            last = last.astimezone()
        return datetime.now().astimezone() - last < STALE_AFTER
    except (ValueError, TypeError):
        return False


def _entry(data: dict[str, Any], key: str) -> dict[str, Any]:
    sessions = data["sessions"]
    entry = sessions.get(key)
    if not isinstance(entry, dict) or not _fresh(entry):
        entry = {"satisfaction": 0, "bugfix": 0, "last_at": now_iso(), "notes": []}
        sessions[key] = entry
    entry.setdefault("satisfaction", 0)
    entry.setdefault("bugfix", 0)
    entry.setdefault("notes", [])
    return entry


def bump(
    track: str = "satisfaction",
    *,
    note: str = "",
    session: str | None = None,
    workspace: Path | None = None,
    amount: int = 1,
) -> dict[str, Any]:
    if track not in TRACKS:
        raise ValueError(f"track must be one of: {', '.join(TRACKS)}")
    path = _state_path(workspace)
    ensure_dir(path.parent)
    with locked(path.with_suffix(".lock")):
        data = _load(path)
        entry = _entry(data, _key(session))
        entry[track] = int(entry.get(track, 0)) + max(1, int(amount))
        entry["last_at"] = now_iso()
        if note:
            entry.setdefault("notes", []).append({"at": now_iso(), "track": track, "text": note[:500]})
            entry["notes"] = entry["notes"][-20:]
        atomic_write_json(path, data)
    return status(track=track, session=session, workspace=workspace, _data=data)


def status(
    track: str = "satisfaction",
    *,
    session: str | None = None,
    workspace: Path | None = None,
    _data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _state_path(workspace)
    data = _data or _load(path)
    entry = _entry(data, _key(session))
    counts = {t: int(entry.get(t, 0)) for t in TRACKS}
    threshold = thresholds(workspace).get(track, 3)
    return {
        "track": track,
        "session": _key(session),
        "counts": counts,
        "threshold": threshold,
        "current": counts.get(track, 0),
        "triggered": counts.get(track, 0) >= threshold,
        "state_path": str(path),
        "note": "计数只用于提醒，最终是否触发由协议判断：连续实质尝试失败或用户明确表达不满意。",
    }


def reset(
    *,
    session: str | None = None,
    workspace: Path | None = None,
    track: str | None = None,
) -> dict[str, Any]:
    path = _state_path(workspace)
    ensure_dir(path.parent)
    with locked(path.with_suffix(".lock")):
        data = _load(path)
        entry = _entry(data, _key(session))
        if track in TRACKS:
            entry[track] = 0
        else:
            for t in TRACKS:
                entry[t] = 0
        entry["last_at"] = now_iso()
        atomic_write_json(path, data)
    return status(track=track or "satisfaction", session=session, workspace=workspace, _data=data)
