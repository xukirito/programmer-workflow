#!/usr/bin/env python3
"""Start the loopback settings server for Kimi's plugin-details shortcut.

A SessionStart hook starts one long-lived 127.0.0.1 server on the fixed port
used by the manifest's websiteURL. The /quick link opens the token-protected
settings page without a model turn or a user-entered command.
"""
from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

PORT = 8765
HOST = "127.0.0.1"


def _server_ready(port: int) -> bool:
    connection = http.client.HTTPConnection(HOST, port, timeout=0.5)
    try:
        connection.request("GET", "/quick?host=kimi")
        response = connection.getresponse()
        response.read(0)
        location = response.getheader("Location") or ""
        return response.status == 302 and location.startswith("/?host=kimi#token=")
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def _companion() -> Optional[Path]:
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "skills" / "programmer-workflow" / "scripts" / "companion.py",
        here.parent / "companion.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _workspace(payload: Dict[str, Any]) -> Path:
    candidate = payload.get("cwd")
    if candidate:
        path = Path(str(candidate)).expanduser()
        if path.is_dir():
            return path.resolve()
    for name in ("KIMI_PROJECT_DIR", "KIMI_WORKSPACE"):
        candidate = os.environ.get(name)
        if candidate and Path(candidate).is_dir():
            return Path(candidate).resolve()
    return Path.cwd().resolve()


def _read_payload() -> Dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError, UnicodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    payload = _read_payload()
    if _server_ready(PORT):
        return 0
    companion = _companion()
    if companion is None:
        return 0
    workspace = _workspace(payload)
    command = [
        sys.executable,
        str(companion),
        "settings",
        "--host",
        "kimi",
        "--workspace",
        str(workspace),
        "--port",
        str(PORT),
    ]
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(workspace),
        "close_fds": True,
    }
    if os.name == "nt":
        flags = 0
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(command, **kwargs)
    except OSError:
        return 0
    for _ in range(20):
        if _server_ready(PORT):
            return 0
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
