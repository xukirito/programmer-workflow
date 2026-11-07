"""Workspace environment discovery, caching and command preflight.

The same workflow runs on Windows and Linux (and occasionally macOS). A failed
``command not found`` attempt costs a tool round, a log directory and often a
retry; this module removes that loop:

* ``probe`` records the local OS, shell, availability and capture/clipboard tools.
* The result is cached at ``<workspace-data>/environment.json`` and written to
  active workspace memory, so later sessions do not repeat the discovery.
* ``check_command`` is a pure lookup (``shutil.which`` plus the cache) used by
  ``run`` before spawning anything.
* A target OS that differs from the local OS is never executed; callers get a
  short instruction to output target-specific commands instead.

Standard library only. The module never imports ``memory`` at import time to
avoid a boot/memory cycle; the one write path imports it lazily.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from . import common

SCHEMA_VERSION = 2
DEFAULT_MAX_AGE_DAYS = 7

# Probed in one pass. Keep this list focused: a long list makes boot slower and
# the memory entry noisier. Capture entries are used by screenshot.py.
COMMANDS: Tuple[str, ...] = (
    "python", "python3", "py", "node", "npm", "pnpm", "yarn", "corepack",
    "git", "rg", "grep", "findstr", "curl", "wget", "tar", "unzip", "7z",
    "powershell", "pwsh", "cmd", "bash", "sh", "zsh",
    "magick", "convert", "ffmpeg",
    "grim", "gnome-screenshot", "spectacle", "scrot", "import", "xdotool",
    "wl-copy", "xclip", "xsel", "wmctrl", "swaymsg",
    "winget", "choco", "scoop", "apt", "dnf", "pacman", "brew",
)
KEY_COMMANDS: Tuple[str, ...] = ("python", "node", "pnpm", "git", "rg")
SHELL_BUILTINS = {
    "cd", "echo", "set", "export", "dir", "copy", "move", "del", "erase",
    "type", "cls", "mkdir", "md", "rmdir", "rd", "if", "for", "while", "true",
    "false", "test", "source", ".", "call", "start", "where", "which",
}
ALTERNATIVES: Dict[str, Tuple[str, ...]] = {
    "python3": ("python", "py"),
    "python": ("py", "python3"),
    "py": ("python", "python3"),
    "pnpm": ("npm", "yarn", "corepack"),
    "npm": ("pnpm", "yarn"),
    "yarn": ("npm", "pnpm"),
    "corepack": ("npm", "pnpm"),
    "pwsh": ("powershell",),
    "powershell": ("pwsh",),
    "bash": ("sh",),
    "sh": ("bash",),
    "rg": ("grep", "findstr"),
    "grep": ("rg", "findstr"),
    "findstr": ("rg", "grep"),
    "curl": ("wget",),
    "wget": ("curl",),
    "magick": ("convert",),
    "convert": ("magick",),
    "grim": ("gnome-screenshot", "spectacle", "scrot", "import"),
    "gnome-screenshot": ("grim", "spectacle", "scrot", "import"),
    "spectacle": ("grim", "gnome-screenshot", "scrot", "import"),
    "scrot": ("grim", "gnome-screenshot", "spectacle", "import"),
    "import": ("grim", "gnome-screenshot", "spectacle", "scrot"),
    "xclip": ("wl-copy", "xsel"),
    "xsel": ("wl-copy", "xclip"),
    "wl-copy": ("xclip", "xsel"),
    "apt": ("dnf", "pacman"),
    "dnf": ("apt", "pacman"),
    "pacman": ("apt", "dnf"),
    "7z": ("tar",),
}

OS_LABELS = {"windows": "Windows", "linux": "Linux", "macos": "macOS"}


class CommandNotFoundError(RuntimeError):
    """Raised by ``run`` before spawning a command that is not installed."""


class CrossOsTargetError(RuntimeError):
    """Raised when the user asks for an OS other than the local one."""


def normalize_os(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    if text in ("win", "win32", "windows", "windows-nt", "powershell", "pwsh", "cmd"):
        return "windows"
    if text in ("linux", "unix", "posix", "ubuntu", "debian", "fedora", "centos", "arch", "wsl"):
        return "linux"
    if text in ("mac", "macos", "darwin", "osx"):
        return "macos"
    return ""


def local_os() -> str:
    name = platform.system().lower()
    if name.startswith("win"):
        return "windows"
    if name == "darwin":
        return "macos"
    if name == "linux":
        return "linux"
    return name or "unknown"


def os_label(os_id: str | None = None) -> str:
    return OS_LABELS.get(os_id or local_os(), (os_id or local_os()).title())


def _which(name: str) -> str:
    try:
        found = shutil.which(name)
    except (OSError, ValueError):
        found = None
    return str(Path(found)) if found else ""


def _found(name: str) -> str:
    path = _which(name)
    if path:
        return path
    # Windows Python launchers are frequently exposed as `py` even when
    # `python`/`python3` are absent. Resolve the alias so run() does not fail.
    if name in ("python", "python3") and local_os() == "windows":
        return _which("py")
    return ""


def _display_version() -> str:
    return platform.python_version()


def _platform_label() -> str:
    system = platform.system() or "Unknown"
    release = platform.release() or ""
    if local_os() == "windows":
        # platform.release() is 10/11; platform.version() carries the build.
        return f"{system} {release}".strip()
    return f"{system} {release}".strip()


def _graphical_session() -> bool:
    if local_os() in ("windows", "macos"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _shell() -> str:
    os_id = local_os()
    if os_id == "windows":
        return "pwsh" if _which("pwsh") else ("powershell" if _which("powershell") else "cmd")
    if os_id == "macos":
        return os.environ.get("SHELL") or "zsh"
    return os.environ.get("SHELL") or ("bash" if _which("bash") else "sh")


def _exists(path: str) -> bool:
    try:
        return Path(path).is_file()
    except OSError:
        return False


def _capture_tools(commands: Dict[str, str]) -> List[str]:
    os_id = local_os()
    if os_id == "windows":
        return ["windows-gdi"] if commands.get("powershell") or commands.get("pwsh") else []
    if os_id == "macos":
        return ["screencapture"] if _which("screencapture") else []
    order = ("grim", "gnome-screenshot", "spectacle", "scrot", "import")
    return [name for name in order if commands.get(name)]


def workspace_cache_path(workspace: Path) -> Path:
    return common.workspace_state(workspace) / "environment.json"


def probe(workspace: Path) -> Dict[str, Any]:
    """Detect the local environment without executing the probed commands."""
    ws = Path(workspace).resolve()
    commands: Dict[str, str] = {}
    for name in COMMANDS:
        path = _found(name)
        if path:
            commands[name] = path
    missing = [name for name in KEY_COMMANDS if not commands.get(name)]
    graph = _graphical_session()
    cache: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "workspace": str(ws),
        "os": local_os(),
        "osLabel": _platform_label(),
        "arch": platform.machine() or "",
        "python": sys.executable,
        "pythonVersion": _display_version(),
        "shell": _shell(),
        "graphical": graph,
        "commands": commands,
        "available": sorted(commands),
        "missing": missing,
        "capture": _capture_tools(commands) if graph else [],
        "recognition": "model",
        "probedAt": common.now_iso(),
        "probedBy": "companion env probe",
    }
    return cache


def load_cached(workspace: Path) -> Dict[str, Any] | None:
    path = workspace_cache_path(workspace)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != SCHEMA_VERSION or not data.get("os"):
        return None
    return data


def _parse_iso(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def age_days(cache: Dict[str, Any] | None) -> float | None:
    if not cache:
        return None
    stamp = _parse_iso(cache.get("probedAt"))
    if stamp is None:
        return None
    now = datetime.now().astimezone()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=now.tzinfo)
    return max(0.0, (now - stamp).total_seconds() / 86400.0)


def is_stale(cache: Dict[str, Any] | None, max_age_days: float = DEFAULT_MAX_AGE_DAYS) -> bool:
    age = age_days(cache)
    return age is None or age > max_age_days


def _write_cache(workspace: Path, cache: Dict[str, Any]) -> Path:
    path = workspace_cache_path(workspace)
    common.ensure_dir(path.parent)
    common.atomic_write_json(path, cache)
    return path


def _memory_text(cache: Dict[str, Any]) -> str:
    available = cache.get("commands") or {}
    parts = [
        f"本机环境（{cache.get('osLabel') or os_label(cache.get('os'))}，自动探测 {cache.get('probedAt')}）",
        f"shell={cache.get('shell')}",
        f"python={'✓' if available.get('python') or available.get('py') else '✗'}",
        f"node={'✓' if available.get('node') else '✗'}",
        f"pnpm={'✓' if available.get('pnpm') else '✗'}",
        f"git={'✓' if available.get('git') else '✗'}",
        f"rg={'✓' if available.get('rg') else '✗'}",
        "截图识别=大模型读取PNG（不用本机OCR）",
    ]
    text = "；".join(parts) + "。"
    text += " 运行前先用 `env check <命令>`；缺失时不要重试，改用已安装替代或请用户安装。"
    text += " 用户指定其他系统时只输出目标系统命令，不在本机执行。"
    return text


def _record_memory(workspace: Path, cache: Dict[str, Any], cache_path: Path) -> Dict[str, Any]:
    """Write or update the single active environment entry for this workspace."""
    try:
        from .memory import MemoryStore

        store = MemoryStore("workspace", workspace=workspace)
        store.ensure()
        text = _memory_text(cache)
        detail = (
            f"缓存文件：{cache_path}；探测命令：{cache.get('probedBy')}；"
            "该条目由 env probe/boot 自动维护，更新会覆盖同一标签的旧条目。"
        )
        evidence = [
            f"os={cache.get('os')}",
            f"platform={cache.get('osLabel')}",
            f"probedAt={cache.get('probedAt')}",
        ]
        existing = None
        for entry in store.entries(status="active"):
            if "environment-probe" in (entry.get("tags") or []):
                existing = entry
                break
        if existing:
            entry = store.edit(existing["id"], text=text, detail=detail, evidence=evidence, tags=["environment-probe", "environment"])
            return {"updated": True, "entry": entry}
        entry, created = store.add(
            kind="environment",
            text=text,
            detail=detail,
            evidence=evidence,
            confidence=1.0,
            source="environment",
            status="active",
            tags=["environment-probe", "environment"],
            dedupe=False,
        )
        return {"updated": False, "created": bool(created), "entry": entry}
    except (OSError, PermissionError, ValueError, KeyError) as error:
        return {"error": str(error)}


def ensure_cached(
    workspace: Path,
    *,
    force: bool = False,
    record: bool = True,
    refresh_stale: bool = False,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
) -> Tuple[Dict[str, Any], bool]:
    """Return ``(cache, probed_now)``.

    Boot calls this with the defaults: an existing cache is reused even when
    stale, so starting a session never pays for a probe. ``env probe`` passes
    ``force=True``; a caller that wants automatic refresh passes
    ``refresh_stale=True``.
    """
    ws = Path(workspace).resolve()
    cached = load_cached(ws)
    if cached and not force and not (refresh_stale and is_stale(cached, max_age_days)):
        # Reuse without touching memory: boot runs this on every session and a
        # write per boot would churn memory.json for no new information.
        return cached, False
    cache = probe(ws)
    path = _write_cache(ws, cache)
    if record:
        result = _record_memory(ws, cache, path)
        if result.get("error"):
            cache["memoryError"] = result["error"]
    return cache, True


def _looks_like_path(command: str) -> bool:
    return "/" in command or "\\" in command or command.startswith(".") or (len(command) > 2 and command[1] == ":")


def _path_found(command: str, workspace: Path) -> str:
    candidate = Path(command)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    try:
        if candidate.is_file() and (os.name == "nt" or os.access(str(candidate), os.X_OK)):
            return str(candidate.resolve())
    except OSError:
        pass
    return ""


def check_command(command: str, workspace: Path, target_os: str | None = None) -> Dict[str, Any]:
    """Check one command without running it. Returns a JSON-ready dict."""
    ws = Path(workspace).resolve()
    name = str(command or "").strip().strip('"').strip("'")
    if not name:
        return {"command": "", "found": False, "error": "empty command", "alternatives": [], "hint": "提供要检查的命令名。"}
    wanted_os = normalize_os(target_os) if target_os else ""
    if wanted_os and wanted_os != local_os():
        return {
            "command": name,
            "found": False,
            "deferred": True,
            "targetOs": wanted_os,
            "localOs": local_os(),
            "alternatives": [],
            "hint": f"目标是 {os_label(wanted_os)}，本机是 {os_label()}：不要在本机执行；只输出 {os_label(wanted_os)} 对应命令（{'PowerShell' if wanted_os == 'windows' else 'bash'}）。",
        }
    if name in SHELL_BUILTINS:
        return {"command": name, "found": True, "builtin": True, "path": "", "alternatives": [], "hint": "shell 内置命令。"}
    path = _path_found(name, ws) if _looks_like_path(name) else _found(name)
    if path:
        return {"command": name, "found": True, "path": path, "alternatives": [], "hint": ""}
    cached = load_cached(ws) or {}
    known = cached.get("commands") or {}
    alternatives = [alt for alt in ALTERNATIVES.get(name, ()) if known.get(alt) or _found(alt)]
    hint = f"未在 PATH 中找到 {name}（本机 {os_label()}）。"
    if alternatives:
        hint += " 已安装的替代：" + "、".join(alternatives) + "；直接改用替代，不要重复尝试原命令。"
    else:
        hint += " 请安装后重试，或换用已安装的等价工具；不要原样重试。"
    return {
        "command": name,
        "found": False,
        "path": "",
        "alternatives": alternatives,
        "hint": hint,
        "cache": str(workspace_cache_path(ws)),
    }


def require_command(command: str, workspace: Path, target_os: str | None = None) -> Dict[str, Any]:
    result = check_command(command, workspace, target_os=target_os)
    if result.get("found") or result.get("deferred"):
        return result
    raise CommandNotFoundError(str(result.get("hint") or f"command not found: {command}"))


def assert_local_target(target_os: Any) -> None:
    wanted = normalize_os(target_os)
    if not wanted or wanted == local_os():
        return
    raise CrossOsTargetError(
        f"目标系统 {os_label(wanted)} 与本机 {os_label()} 不同：不要在本机执行该命令。"
        f"请只输出 {os_label(wanted)} 的命令（{'PowerShell' if wanted == 'windows' else 'bash'}），"
        "或让用户在目标系统上运行后反馈输出。"
    )


def summary(cache: Dict[str, Any] | None, workspace: Path | None = None) -> Dict[str, Any]:
    """Compact data for boot/status output; never includes the full command map."""
    if not cache:
        return {"probed": False, "cache": str(workspace_cache_path(workspace)) if workspace else ""}
    commands = cache.get("commands") or {}
    key = {name: bool(commands.get(name)) for name in KEY_COMMANDS}
    return {
        "probed": True,
        "os": cache.get("os"),
        "osLabel": cache.get("osLabel"),
        "shell": cache.get("shell"),
        "arch": cache.get("arch"),
        "graphical": bool(cache.get("graphical")),
        "key": key,
        "capture": cache.get("capture") or [],
        "recognition": "model",
        "probedAt": cache.get("probedAt"),
        "ageDays": round(age_days(cache) or 0.0, 1),
        "stale": is_stale(cache),
        "cache": str(workspace_cache_path(workspace)) if workspace else "",
        "memoryError": cache.get("memoryError"),
    }


def boot_line(cache: Dict[str, Any] | None, workspace: Path) -> str:
    data = summary(cache, workspace)
    if not data.get("probed"):
        return "ENVIRONMENT — 尚未探测；运行 `env probe` 一次，缓存到工作区记忆。"
    key = data.get("key") or {}
    flags = " · ".join(f"{name} {'✓' if ok else '✗'}" for name, ok in key.items())
    stale = "（已过期，可 env probe 刷新）" if data.get("stale") else ""
    return (
        f"ENVIRONMENT（缓存 {data.get('ageDays')} 天）{stale} — {data.get('osLabel')} · {data.get('shell')} · "
        f"{flags} · 截图识别=大模型 · {data.get('cache')}"
    )


def format_check(result: Dict[str, Any]) -> str:
    if result.get("found"):
        if result.get("builtin"):
            return f"✓ {result.get('command')}（shell 内置）"
        return f"✓ {result.get('command')} → {result.get('path')}"
    if result.get("deferred"):
        return f"⏸ {result.get('command')}：{result.get('hint')}"
    lines = [f"✗ {result.get('command')}：{result.get('hint')}"]
    if result.get("alternatives"):
        lines.append("替代：" + "、".join(result["alternatives"]))
    if result.get("cache"):
        lines.append("缓存：" + result["cache"])
    return "\n".join(lines)


def command_names_for_run(command: List[str], shell: bool) -> List[str]:
    """First executable token(s) that should exist before spawning."""
    if not command:
        return []
    if not shell:
        return [str(command[0])]
    text = " ".join(str(part) for part in command)
    try:
        import shlex

        parts = shlex.split(text, posix=(os.name != "nt"))
    except ValueError:
        return []
    if not parts:
        return []
    # Only check a simple first word; cmd.exe built-ins, pipes and redirection
    # are left to the shell so the preflight never becomes a false negative.
    if any(token in text for token in ("|", ">", "<", "&&", "||", ";", "&")):
        return []
    return [parts[0]] if parts[0] not in SHELL_BUILTINS else []
