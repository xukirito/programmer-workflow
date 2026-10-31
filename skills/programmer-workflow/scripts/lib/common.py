"""Shared utilities for Programmer Workflow.

Standard library only. All user-facing text is UTF-8.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator

from . import hosts

SCHEMA_VERSION = 1
SKILL_NAME = "programmer-workflow"

WORKFLOW_MODES = {
    "plan": {
        "label": "Plan",
        "description": "先生成 plan.md 或 plan.html，用户批准后才执行。",
    },
    "full-authority": {
        "label": "Full authority",
        "description": "普通命令直接执行；破坏性操作仍需确认。",
    },
}
DEFAULT_WORKFLOW_MODE = "plan"


def normalize_workflow_mode(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    return text if text in WORKFLOW_MODES else DEFAULT_WORKFLOW_MODE

# Marker used by installers and host bootstrap files.
BOOTSTRAP_START = "<!-- programmer-workflow:start -->"
BOOTSTRAP_END = "<!-- programmer-workflow:end -->"

IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", "vendor",
    "dist", "build", "out", "target", "bin", "obj", "coverage", ".venv",
    "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".next", ".nuxt", ".cache", ".gradle", ".idea", ".vs", "Pods",
    ".programmer-workflow", "debug-logs", ".dsh", ".agents", ".claude",
}

TEXT_EXTS = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".cs", ".java", ".kt",
    ".kts", ".swift", ".m", ".mm", ".php", ".rb", ".lua", ".r", ".jl", ".scala",
    ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".bat", ".cmd", ".sql", ".html",
    ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte", ".json",
    ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml", ".md",
    ".markdown", ".rst", ".txt", ".tex", ".proto", ".graphql", ".gql", ".dockerfile",
}

SKIP_FILE_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock",
    "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum",
}

MAX_TEXT_BYTES = 1_500_000


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def skill_root() -> Path:
    """Return the installed skill directory (the folder holding SKILL.md)."""
    return Path(__file__).resolve().parents[2]


def templates_dir() -> Path:
    return skill_root() / "templates"


def assets_dir() -> Path:
    return skill_root() / "assets"


def user_home() -> Path:
    """Per-host global user-memory directory.

    The default is `<host-home>/programmer-workflow/memory`; hosts never share
    this tree. `PROGRAMMER_WORKFLOW_HOME` remains an exact memory-directory
    override for old installations and tests, and is reported as external.
    """
    return hosts.memory_root()


def dsh_home() -> Path:
    """DSH home only. Other hosts must not use this as a fallback."""
    return hosts.host_home("dsh")


def global_root() -> Path:
    """Per-host Programmer Workflow data root."""
    return hosts.plugin_root()


DEFAULT_CONFIG: dict[str, Any] = {
    "workspaceDataDir": ".programmer-workflow",
    "debugLogDir": "debug-logs",
    "docsDir": "docs",
    "prototypeFile": "Prototype.html",
    "userMemoryEnabled": True,
    "workspaceMemoryEnabled": True,
    "satisfactionThreshold": 3,
    "bugfixThreshold": 2,
    "workflowMode": DEFAULT_WORKFLOW_MODE,
    "devOnlyAutoInstrument": True,
    "docsEnabled": True,
    "prototypeEnabled": True,
    "retentionDays": 30,
    "language": "zh-CN",
    "promptMigration": True,
    "planFormat": "md",
}


def safe_workspace_relative(value: Any, default: str) -> str:
    """Return a normalized relative path that cannot escape the workspace."""
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return default
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return default
    return "/".join(parts)


def workspace_output_path(workspace: Path | None, value: Any, default: str) -> Path:
    """Resolve a user-supplied output path strictly inside the workspace.

    Unlike ``safe_workspace_relative`` this is for command-line/output writes:
    absolute paths and ``..`` are rejected rather than silently replaced.
    """
    base = (workspace or workspace_root()).resolve()
    raw = str(value or "").strip()
    text = raw.replace("\\", "/")
    if not text:
        text = default
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ValueError(f"output path must be inside the workspace (absolute path rejected): {raw}")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts:
        parts = default.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise ValueError(f"output path must not contain '..': {raw}")
    target = (base / Path(*parts)).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"output path escapes the workspace: {raw}") from exc
    return target


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _coerce_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def load_plugin_config(workspace: Path | None = None) -> dict[str, Any]:
    """Read the Host-written config mirror; fall back to safe defaults.

    The DSH plugin writes `<global_root>/config.json`; the CLI must be usable
    without the plugin, so missing/invalid values fall back rather than fail.
    Workspace-relative paths are validated here as a second layer of defense.
    """
    cfg = dict(DEFAULT_CONFIG)
    path = global_root() / "config.json"
    data = read_json(path, {})
    if isinstance(data, dict):
        for key in (
            "workspaceDataDir", "debugLogDir", "docsDir", "prototypeFile",
            "language",
        ):
            if key in data:
                cfg[key] = data[key]
        cfg["planFormat"] = "html" if str(data.get("planFormat", "")).lower() == "html" else "md"
        cfg["workflowMode"] = normalize_workflow_mode(data.get("workflowMode"))
        for key in ("userMemoryEnabled", "workspaceMemoryEnabled",
                    "devOnlyAutoInstrument", "docsEnabled", "prototypeEnabled", "promptMigration"):
            if key in data:
                cfg[key] = _coerce_bool(data[key], bool(DEFAULT_CONFIG[key]))
        cfg["satisfactionThreshold"] = _coerce_int(data.get("satisfactionThreshold"), 3, 1, 10)
        cfg["bugfixThreshold"] = _coerce_int(data.get("bugfixThreshold"), 2, 1, 10)
        cfg["retentionDays"] = _coerce_int(data.get("retentionDays"), 30, 1, 365)
    for key in ("workspaceDataDir", "debugLogDir", "docsDir", "prototypeFile"):
        cfg[key] = safe_workspace_relative(cfg.get(key), str(DEFAULT_CONFIG[key]))
    cfg["language"] = str(cfg.get("language") or "zh-CN")[:20]
    cfg["host"] = hosts.resolve_host()
    cfg["globalRoot"] = str(global_root())
    cfg["dshHome"] = str(hosts.host_home("dsh"))
    cfg["hostHome"] = str(hosts.host_home(cfg["host"]))
    cfg["overrides"] = hosts.external_overrides(cfg["host"])
    return cfg


def workspace_root(start: Path | None = None) -> Path:
    """Find the project root: nearest ancestor with .git or .programmer-workflow.

    A plain directory is its own root. This mirrors the convention used by
    coding agents and keeps nested shells in the same workspace.
    """
    start = (start or Path.cwd()).resolve()
    if start.is_file():
        start = start.parent
    override = os.environ.get("PROGRAMMER_WORKFLOW_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / ".programmer-workflow").is_dir() or (candidate / ".workflow-companion").is_dir():
            return candidate
    return start


def workspace_state(workspace: Path | None = None) -> Path:
    base = (workspace or workspace_root()).resolve()
    return base / load_plugin_config(base)["workspaceDataDir"]


def docs_dir(workspace: Path | None = None) -> Path:
    base = (workspace or workspace_root()).resolve()
    return base / load_plugin_config(base)["docsDir"]


def debug_log_dir(workspace: Path | None = None) -> Path:
    base = (workspace or workspace_root()).resolve()
    return base / load_plugin_config(base)["debugLogDir"]


def prototype_path(workspace: Path | None = None) -> Path:
    base = (workspace or workspace_root()).resolve()
    return base / load_plugin_config(base)["prototypeFile"]


# --------------------------------------------------------------------------
# Time / ids / text
# --------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3)}"


def one_line(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def md_escape(text: str) -> str:
    text = one_line(text, 4000)
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("|", "\\|")


def html_escape(text: Any) -> str:
    import html
    return html.escape(str(text), quote=True)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


# --------------------------------------------------------------------------
# JSON / files
# --------------------------------------------------------------------------

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def atomic_write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def copy_tree(src: Path, dst: Path) -> None:
    """Copy a directory, replacing the destination only after a backup."""
    if dst.exists():
        backup = dst.with_name(f"{dst.name}.bak-{now_stamp()}")
        shutil.move(str(dst), str(backup))
    shutil.copytree(src, dst)


# --------------------------------------------------------------------------
# Console
# --------------------------------------------------------------------------

def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")


def emit(text: str = "") -> None:
    print(text)


def emit_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def warn(text: str) -> None:
    print(f"[warn] {text}", file=sys.stderr)


def fail(text: str, code: int = 2) -> int:
    print(f"[error] {text}", file=sys.stderr)
    return code


# --------------------------------------------------------------------------
# File walking
# --------------------------------------------------------------------------

def should_skip_dir(name: str, rel: Path | None = None) -> bool:
    if name in IGNORED_DIRS:
        return True
    if name.startswith(".") and name not in {".github", ".vscode", ".devcontainer"}:
        return True
    return False


def iter_project_files(
    root: Path,
    *,
    max_files: int = 6000,
    follow_symlinks: bool = False,
) -> Iterator[Path]:
    """Yield regular files under root, skipping vendored/build directories."""
    root = root.resolve()
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        current = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames
            if not should_skip_dir(d, current.relative_to(root) / d)
        )
        for name in sorted(filenames):
            if name in SKIP_FILE_NAMES:
                continue
            path = current / name
            if path.is_symlink() and not follow_symlinks:
                continue
            if not path.is_file():
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def read_text_limited(path: Path, max_bytes: int = MAX_TEXT_BYTES) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def language_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    mapping = {
        ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
        ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C/C++ header", ".cc": "C++",
        ".cpp": "C++", ".cxx": "C++", ".hpp": "C++", ".cs": "C#", ".java": "Java",
        ".kt": "Kotlin", ".swift": "Swift", ".php": "PHP", ".rb": "Ruby",
        ".lua": "Lua", ".sh": "Shell", ".ps1": "PowerShell", ".sql": "SQL",
        ".html": "HTML", ".css": "CSS", ".vue": "Vue", ".svelte": "Svelte",
        ".md": "Markdown", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
        ".toml": "TOML", ".xml": "XML", ".csproj": "MSBuild", ".sln": "Visual Studio",
    }
    return mapping.get(ext)


def line_count(path: Path, max_bytes: int = MAX_TEXT_BYTES) -> int:
    text = read_text_limited(path, max_bytes)
    if text is None:
        return 0
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


# --------------------------------------------------------------------------
# Locking
# --------------------------------------------------------------------------

class FileLock:
    """Small cross-platform advisory lock with a timeout."""

    def __init__(self, path: Path, timeout: float = 8.0):
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self) -> "FileLock":
        ensure_dir(self.path.parent)
        self._fh = open(self.path, "a+b")
        deadline = time.time() + self.timeout
        while True:
            try:
                self._acquire()
                return self
            except OSError:
                if time.time() >= deadline:
                    self._fh.close()
                    self._fh = None
                    raise TimeoutError(f"lock timeout: {self.path}")
                time.sleep(0.05)

    def _acquire(self) -> None:
        assert self._fh is not None
        if os.name == "nt":
            import msvcrt
            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


@contextlib.contextmanager
def locked(path: Path, timeout: float = 8.0) -> Iterator[None]:
    with FileLock(path, timeout=timeout):
        yield


# --------------------------------------------------------------------------
# Process helpers
# --------------------------------------------------------------------------

def run_git(args: list[str], cwd: Path, timeout: float = 8.0) -> str | None:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def redact_url(url: str) -> str:
    """Remove credentials from a remote URL before writing it to disk."""
    url = re.sub(r"(https?://)[^/@\s]+@", r"\1", url)
    return url


def find_python() -> str:
    """Best-effort interpreter command for printed instructions."""
    return sys.executable or ("python" if os.name == "nt" else "python3")


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
