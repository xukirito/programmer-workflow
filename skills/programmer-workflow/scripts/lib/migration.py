"""Two-stage, host-scoped Programmer Workflow data migration.

Stage 1 moves only this host's plugin data (``<host-home>/programmer-workflow``).
Stage 2 is the editor's own runtime data and is gated on a completed stage 1.
All functions are usable on temporary directories; nothing here touches another
host's root.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import hosts
from .common import atomic_write_json, now_iso, now_stamp, read_json, sha256_file

TRANSFER_FILES = ("memory.json", "MEMORY.md", "config.json", "README.md")
TRANSIENT_NAMES = {"memory.lock"}
STAGE1_STATUSES = ("not-started", "prepared", "completed", "failed", "rolled-back", "conflict")
STAGE2_STATUSES = ("not-started", "prepared", "active", "completed", "failed", "rolled-back")
# A stage 1 rollback must wait until stage 2 is gone: a runtime junction can
# still point into the plugin root being restored.
STAGE2_BLOCKS_STAGE1_ROLLBACK = ("prepared", "active", "completed")
MIGRATE_SCRIPT = {"dsh": "migrate-dsh-data.bat", "kimi": "migrate-kimi-data.bat"}
ROLLBACK_SCRIPT = {"dsh": "rollback-dsh-data.bat", "kimi": "rollback-kimi-data.bat"}
# No machine-specific adapter path is shipped. An explicit
# `kimiMigrationTools` setting or the environment always wins.
LEGACY_TOOL_DIRS = {}


def system_drive() -> str:
    """The app's own volume. Overridable for tests/non-C: installations."""
    raw = os.environ.get("PROGRAMMER_WORKFLOW_SYSTEM_DRIVE") or os.environ.get("SystemDrive")
    if not raw:
        return "C:" if os.name == "nt" else ""
    return str(raw).rstrip("\\/").upper()


def is_off_system_drive(path: str | Path) -> bool:
    """True when the *real* location is on a volume other than the system one.

    A junction whose target lives elsewhere means the visible path is only a
    mapping; that is a completed move for migration purposes.
    """
    if not path:
        return False
    drive = Path(os.path.abspath(os.path.expanduser(str(path)))).drive.upper()
    sys = system_drive()
    return bool(sys) and bool(drive) and drive != sys


def _real_location(path: str | Path) -> Path | None:
    try:
        return Path(os.path.realpath(str(path)))
    except OSError:
        return None


def stage1_summary(host: str | None = None) -> dict[str, Any]:
    """Completed stage 1: our verified record, or a real landing off the system drive."""
    host_id = hosts.resolve_host(host)
    state = read_state(host_id)
    source = Path((state or {}).get("source") or hosts.plugin_root(host_id))
    record = verified_stage1(host_id)
    real = _real_location(source)
    relocated = bool(real) and is_off_system_drive(real)
    completed = bool(record) or relocated
    return {
        "completed": completed,
        "verified": bool(record),
        "completedVia": "record" if record else ("relocated" if relocated else None),
        "relocated": relocated,
        "systemDrive": system_drive(),
        "target": str(record["target"]) if record else (str(real) if relocated else None),
        "verifiedAt": record.get("verifiedAt") if record else None,
    }


def stage2_summary(host: str | None = None) -> dict[str, Any]:
    """Completed stage 2: marker+link, or a host home that really lands elsewhere."""
    host_id = hosts.resolve_host(host)
    state = read_runtime_state(host_id) or {}
    control = control_dir(host_id)
    marker_completed = (control / "runtime-completed.txt").exists()
    marker_rolled = (control / "runtime-rolled-back.txt").exists()
    home = hosts.host_home(host_id)
    real = _real_location(home)
    relocated = bool(real) and is_off_system_drive(real)
    recorded = state.get("target")
    verified = bool(
        marker_completed
        and recorded
        and _is_reparse(home)
        and real is not None
        and os.path.normcase(str(real)) == os.path.normcase(os.path.realpath(str(recorded)))
    )
    completed = verified or relocated
    if completed:
        status = "completed"
    elif marker_completed:
        status = "stale"
    elif marker_rolled:
        status = "rolled-back"
    else:
        status = str(state.get("status") or "not-started")
    return {
        "status": status,
        "completed": completed,
        "verified": verified,
        "completedVia": "record" if verified else ("relocated" if relocated else None),
        "relocated": relocated,
        "actualLocation": str(real) if real else None,
        "recordedTarget": str(recorded) if recorded else None,
    }


class MigrationError(RuntimeError):
    pass


def _safe_json(path: Path) -> Any:
    """Read JSON for status/preflight paths; corruption must not crash a report."""
    try:
        return read_json(path)
    except (ValueError, OSError, UnicodeError):
        return None


def control_dir(host: str | None = None) -> Path:
    return hosts.host_home(host) / ".programmer-workflow-migration"


def state_path(host: str | None = None) -> Path:
    return control_dir(host) / "plugin-state.json"


def runtime_state_path(host: str | None = None) -> Path:
    return control_dir(host) / "runtime-state.json"


def read_state(host: str | None = None) -> dict[str, Any] | None:
    host_id = hosts.resolve_host(host)
    data = _safe_json(state_path(host_id))
    if isinstance(data, dict) and data.get("host") == host_id:
        return data
    return None


def read_runtime_state(host: str | None = None) -> dict[str, Any] | None:
    host_id = hosts.resolve_host(host)
    path = runtime_state_path(host_id)
    data = _safe_json(path)
    if isinstance(data, dict) and data.get("host") == host_id:
        return data
    # Fail safe: an unreadable stage 2 state must keep blocking stage 1 rollback
    # instead of looking like "not started".
    if path.exists():
        return {"host": host_id, "status": "active", "error": "runtime-state.json is unreadable"}
    return None


def runtime_stage_status(host: str | None = None) -> str:
    """Stage 2 status, derived exactly like the Host plugin's runtimeStageStatus.

    The launchers write completion/rollback markers because a batch file cannot
    edit JSON; the markers win over `runtime-state.json`, which keeps saying
    `prepared` after stage 2 actually finished or was rolled back.
    """
    host_id = hosts.resolve_host(host)
    control = control_dir(host_id)
    if (control / "runtime-completed.txt").exists():
        return "completed"
    if (control / "runtime-rolled-back.txt").exists():
        return "rolled-back"
    state = read_runtime_state(host_id)
    status = str((state or {}).get("status") or "not-started")
    return status if status in STAGE2_STATUSES else "not-started"


def write_state(host: str, state: dict[str, Any]) -> None:
    state = dict(state)
    state["host"] = host
    atomic_write_json(state_path(host), state)


def memory_file(root: Path) -> Path:
    """Resolve the real memory.json of a plugin root.

    A plugin root keeps its memory in ``<root>/memory/memory.json``; the flat
    ``<root>/memory.json`` form is accepted for older/exported trees. Both
    ``inventory()`` and ``preflight()`` must use this one rule.
    """
    root = Path(root)
    direct = root / "memory.json"
    if direct.exists():
        return direct
    nested = root / "memory" / "memory.json"
    if nested.exists():
        return nested
    return direct


def inventory(root: Path) -> dict[str, Any]:
    root = Path(root)
    memory_path = memory_file(root)
    data = _safe_json(memory_path)
    entries = data.get("entries", []) if isinstance(data, dict) else []
    counts = {"active": 0, "proposed": 0, "rejected": 0, "total": len(entries)}
    for entry in entries:
        status = entry.get("status") if isinstance(entry, dict) else None
        if status in counts:
            counts[status] += 1
    return {
        "root": str(root),
        "memoryPath": str(memory_path),
        "memoryExists": memory_path.exists(),
        "memoryValid": isinstance(data, dict),
        "counts": counts,
        "ids": sorted(str(entry.get("id")) for entry in entries if isinstance(entry, dict) and entry.get("id")),
        "sha256": {
            "memory": sha256_file(memory_path) if memory_path.exists() else None,
            "memoryMd": sha256_file(memory_path.parent / "MEMORY.md") if (memory_path.parent / "MEMORY.md").exists() else None,
            "config": sha256_file(root / "config.json") if (root / "config.json").exists() else None,
        },
    }


def legacy_candidates(host: str) -> list[Path]:
    host_id = hosts.resolve_host(host)
    home = Path(os.environ.get("PROGRAMMER_WORKFLOW_LEGACY_HOME") or Path.home()).expanduser()
    result = [home / ".workflow-companion"]
    if host_id != "dsh":
        result.append(home / ".dsh" / "programmer-workflow")
    return result


def legacy_status(host: str) -> dict[str, Any]:
    host_id = hosts.resolve_host(host)
    root = hosts.plugin_root(host_id)
    memory_dir = hosts.memory_root(host_id)
    target_memory = memory_dir / "memory.json"
    candidates = legacy_candidates(host_id)
    present = [p for p in candidates if p.exists()]
    source = next((p for p in present if (p / "memory.json").exists() or (p / "memory" / "memory.json").exists()), None)
    source_memory_root = (source / "memory") if source and not (source / "memory.json").exists() else source
    marker = root / "legacy-import.json"
    source_inventory = inventory(source_memory_root if source else Path("__missing__"))
    target_inventory = inventory(memory_dir)
    imported = marker.exists()
    same = bool(
        source_inventory["sha256"]["memory"]
        and source_inventory["sha256"]["memory"] == target_inventory["sha256"]["memory"]
    )
    conflict = bool(
        source_inventory["memoryExists"]
        and target_inventory["memoryExists"]
        and not same
    )
    return {
        "candidates": [str(p) for p in candidates],
        "present": [str(p) for p in present],
        "source": str(source) if source else None,
        "sourceInventory": source_inventory,
        "targetInventory": target_inventory,
        "imported": imported,
        "same": same,
        "conflict": conflict,
        "status": "conflict" if conflict else ("same" if same else ("pending" if source else "none")),
    }


def plugin_target(host: str, target_root: str | Path) -> Path:
    host_id = hosts.resolve_host(host)
    spec = hosts.host_spec(host_id)
    root = Path(str(target_root)).expanduser()
    if not root.is_absolute():
        raise MigrationError("target root must be an absolute path")
    if str(root).startswith("\\\\") or str(root).startswith("//"):
        raise MigrationError("UNC targets are not supported by the junction migration path")
    return (root / spec["data_dir"] / "programmer-workflow").resolve()


def _overlaps(a: Path, b: Path) -> bool:
    try:
        a.resolve().relative_to(b.resolve())
        return True
    except ValueError:
        pass
    try:
        b.resolve().relative_to(a.resolve())
        return True
    except ValueError:
        return False


def _is_reparse(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError:
        return False
    if path.is_symlink():
        return True
    attrs = getattr(stat, "st_file_attributes", 0)
    return bool(attrs & 0x400)


def nested_links(root: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    root = Path(root)
    if not root.exists():
        return result
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        for name in list(dirnames) + list(filenames):
            candidate = current / name
            if _is_reparse(candidate):
                result.append({"path": str(candidate), "target": os.path.realpath(candidate)})
        dirnames[:] = [name for name in dirnames if not _is_reparse(current / name)]
    return result


def preflight(host: str, target_root: str | Path) -> dict[str, Any]:
    host_id = hosts.resolve_host(host)
    source = hosts.plugin_root(host_id)
    target = plugin_target(host_id, target_root)
    errors: list[str] = []
    warnings: list[str] = []
    if not source.exists():
        errors.append(f"source plugin data does not exist: {source}")
    if source == target or _overlaps(source, target):
        errors.append("target must not overlap the source plugin directory")
    if target.exists():
        entries = list(target.iterdir())
        plugin_like = (target / "memory.json").exists() or (target / "config.json").exists()
        if entries and not plugin_like:
            errors.append("target already contains unrelated data; choose an empty directory")
        elif entries:
            errors.append("target already contains plugin data; refusing to merge silently")
    if (source / "memory.json").exists() or (source / "memory" / "memory.json").exists():
        actual = memory_file(source)
        data = _safe_json(actual)
        if not isinstance(data, dict):
            errors.append(f"source memory file is not a JSON object: {actual}")
        elif not isinstance(data.get("entries"), list):
            errors.append(f"source memory file has no entries array: {actual}")
    links = nested_links(source)
    if links:
        errors.append("source contains nested junctions/reparse points; stage 2 must rebuild them explicitly")
    if str(source).startswith("\\\\"):
        errors.append("source is a UNC path; junction migration does not support UNC")
    inv = inventory(source)
    legacy = legacy_status(host_id)
    if legacy["conflict"]:
        warnings.append("legacy/shared memory exists with a different memory.json; import is a separate conflict step")
    return {
        "host": host_id,
        "source": str(source),
        "realSource": os.path.realpath(source),
        "target": str(target),
        "targetRoot": str(Path(target_root)),
        "errors": errors,
        "warnings": warnings,
        "inventory": inv,
        "legacy": legacy,
        "nestedLinks": links,
        # Partial support: nested links are detected and refused, never rebuilt
        # from a manifest. Do not describe this as a complete rebuild.
        "nestedJunctionRebuild": "unsupported",
        "ok": not errors,
    }


def _copy_plugin(source: Path, target: Path) -> None:
    if target.exists():
        if any(target.iterdir()):
            raise MigrationError(f"target is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    for name in ("memory", "artifacts", "logs"):
        src = source / name
        if src.exists():
            shutil.copytree(
                src, target / name,
                ignore=shutil.ignore_patterns("memory.lock", "*.lock"),
                symlinks=False,
            )
    for name in TRANSFER_FILES:
        src = source / name
        if src.exists():
            shutil.copy2(src, target / name)


def _backup_plugin(host: str, label: str, source: str | Path | None = None) -> Path:
    """Copy the plugin data currently at ``source`` (default: the host root).

    Rollback passes the source recorded in the migration state, so a later
    environment change (for example a different ``PROGRAMMER_WORKFLOW_GLOBAL``)
    can never make the backup read a different directory than the one being
    rolled back. A second backup in the same second gets a numeric suffix
    instead of failing.
    """
    stamp = now_stamp()
    source = Path(source) if source else hosts.plugin_root(host)
    backup: Path | None = None
    for counter in range(1, 1000):
        suffix = f"{stamp}-{label}" if counter == 1 else f"{stamp}-{label}-{counter}"
        candidate = control_dir(host) / "backups" / suffix / "plugin"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            backup = candidate
            break
        except FileExistsError:
            continue
    if backup is None:
        raise MigrationError("could not allocate a unique backup directory")
    for name in ("memory", "artifacts", "logs"):
        src = source / name
        if src.exists():
            shutil.copytree(src, backup / name, ignore=shutil.ignore_patterns("memory.lock", "*.lock"))
    for name in TRANSFER_FILES:
        src = source / name
        if src.exists():
            shutil.copy2(src, backup / name)
    atomic_write_json(backup / "inventory.json", {
        "at": now_iso(), "host": host, "source": str(source), "inventory": inventory(source),
    })
    return backup


def create_junction(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise MigrationError(f"mklink failed: {result.stderr or result.stdout}")
    else:
        os.symlink(target, link, target_is_directory=True)


def remove_junction(link: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True, text=True)
        if result.returncode != 0:
            raise MigrationError(f"rmdir failed: {result.stderr or result.stdout}")
    else:
        os.unlink(link)


def _previous_completed(host: str) -> dict[str, Any] | None:
    """The most recent verified stage 1 record, even while a new one is staged."""
    state = read_state(host)
    if not state:
        return None
    if state.get("status") == "completed" and state.get("verifiedAt"):
        return state
    previous = state.get("previous")
    if isinstance(previous, dict) and previous.get("status") == "completed" and previous.get("verifiedAt"):
        return previous
    return None


def verified_stage1(host: str | None = None) -> dict[str, Any] | None:
    """A completed stage 1 record whose source really links to its target.

    A state file alone never counts: the live junction (or symlink) at the
    plugin source must resolve to the recorded target, which is what "verified"
    means here. A pending re-migration keeps the previous record valid until
    the new one succeeds.
    """
    host_id = hosts.resolve_host(host)
    state = read_state(host_id)
    if not state:
        return None
    source = Path(state.get("source") or hosts.plugin_root(host_id))
    try:
        source_is_link = _is_reparse(source)
    except OSError:
        source_is_link = False
    try:
        home_is_link = _is_reparse(hosts.host_home(host_id))
    except OSError:
        home_is_link = False
    if not source_is_link and not home_is_link:
        return None
    candidates = [state]
    if isinstance(state.get("previous"), dict):
        candidates.append(state["previous"])
    for record in candidates:
        if not record or record.get("status") != "completed" or not record.get("verifiedAt"):
            continue
        target = record.get("target")
        if not target:
            continue
        try:
            real = os.path.realpath(source)
        except OSError:
            continue
        if os.path.normcase(real) == os.path.normcase(os.path.realpath(str(target))):
            return record
    return None


def prepare(host: str, target_root: str | Path) -> dict[str, Any]:
    report = preflight(host, target_root)
    if not report["ok"]:
        raise MigrationError("; ".join(report["errors"]))
    backup = _backup_plugin(host, "stage1-prepare")
    previous = _previous_completed(host)
    state = {
        "host": host,
        "status": "prepared",
        "source": report["source"],
        "target": report["target"],
        "targetRoot": report["targetRoot"],
        "backup": str(backup),
        "preparedAt": now_iso(),
        "verifiedAt": None,
        "inventory": report["inventory"],
        "legacy": report["legacy"],
        "previous": previous,
    }
    write_state(host, state)
    return {"ok": True, **state}


def _unique_old(source: Path) -> Path:
    stamp = now_stamp()
    candidate = source.with_name(source.name + f".old-{stamp}")
    counter = 2
    while candidate.exists():
        candidate = source.with_name(source.name + f".old-{stamp}-{counter}")
        counter += 1
    return candidate


def apply(host: str, target_root: str | Path, assume_yes: bool = False) -> dict[str, Any]:
    if not assume_yes:
        raise MigrationError("stage 1 apply requires --yes after the user has approved it")
    report = preflight(host, target_root)
    if not report["ok"]:
        raise MigrationError("; ".join(report["errors"]))
    source = Path(report["source"])
    target = Path(report["target"])
    before = inventory(source)
    backup = _backup_plugin(host, "stage1-apply")
    previous = _previous_completed(host)
    old = _unique_old(source)
    try:
        _copy_plugin(source, target)
        after = inventory(target)
        if before["sha256"]["memory"] != after["sha256"]["memory"]:
            raise MigrationError("memory.json hash changed during copy")
        if before["ids"] != after["ids"] or before["counts"] != after["counts"]:
            raise MigrationError("memory entries changed during copy")
        source.rename(old)
        create_junction(source, target)
        real = os.path.realpath(source)
        if os.path.normcase(real) != os.path.normcase(str(target)):
            raise MigrationError(f"junction verification failed: {real} != {target}")
        state = {
            "host": host,
            "status": "completed",
            "source": str(source),
            "target": str(target),
            "targetRoot": report["targetRoot"],
            "backup": str(backup),
            "oldSource": str(old),
            "preparedAt": now_iso(),
            "verifiedAt": now_iso(),
            "inventory": after,
            "previous": previous,
        }
        write_state(host, state)
        return {"ok": True, **state}
    except Exception as exc:
        # Only undo the switch once the source was actually renamed. A failure
        # during copy must leave the live source link untouched.
        if old.exists():
            if source.exists() and _is_reparse(source):
                try:
                    remove_junction(source)
                except MigrationError:
                    pass
            if not source.exists():
                try:
                    old.rename(source)
                except OSError:
                    pass
        try:
            write_state(host, {
                "host": host,
                "status": "failed",
                "source": str(source),
                "target": str(target),
                "targetRoot": report["targetRoot"],
                "backup": str(backup),
                "failedAt": now_iso(),
                "error": str(exc),
                "inventory": before,
                "previous": previous,
            })
        except Exception:
            pass
        raise


def rollback(host: str) -> dict[str, Any]:
    """Restore stage 1 from the recorded ``.old`` backup.

    Order is enforced: while stage 2 is prepared/active/completed this refuses,
    because a runtime junction may still point into the plugin data being
    restored. The pre-rollback backup is taken from the source recorded in the
    state, never from a re-resolved environment override.
    """
    host_id = hosts.resolve_host(host)
    state = read_state(host_id)
    if not state or state.get("status") != "completed":
        raise MigrationError("stage 1 is not in a completed state")
    stage2 = runtime_stage_status(host_id)
    if stage2 in STAGE2_BLOCKS_STAGE1_ROLLBACK:
        raise MigrationError(
            f"stage 2 runtime migration is still {stage2}; roll back stage 2 first "
            f"(run the stage 2 rollback launcher, then retry the stage 1 rollback)"
        )
    source = Path(state["source"])
    target = Path(state["target"])
    old = Path(state.get("oldSource") or "")
    if not str(old) or not old.exists():
        raise MigrationError("source backup is missing; refusing to remove the junction")
    latest = _backup_plugin(host_id, "stage1-rollback-latest", source=source)
    current = inventory(source)
    changed = current["sha256"] != state.get("inventory", {}).get("sha256") or current["ids"] != state.get("inventory", {}).get("ids")

    removed_link = False
    moved_aside: Path | None = None
    try:
        if _is_reparse(source):
            remove_junction(source)
            removed_link = True
        elif source.exists():
            moved_aside = source.with_name(source.name + f".pre-rollback-{now_stamp()}")
            source.rename(moved_aside)
        old.rename(source)
    except Exception as exc:
        # Keep the host working: put back a link to the migrated data (or the
        # directory we just moved aside) and leave every artifact in place.
        recovery = "none"
        try:
            if not source.exists():
                if removed_link:
                    create_junction(source, target)
                    recovery = "junction-restored"
                elif moved_aside is not None and moved_aside.exists():
                    moved_aside.rename(source)
                    moved_aside = None
                    recovery = "source-restored"
        except Exception:
            recovery = "failed"
        raise MigrationError(
            f"rollback could not restore the original source directory: {exc}; "
            f"backup kept at {old}, migrated data kept at {target}, recovery={recovery}"
        ) from exc

    state.update({
        "status": "rolled-back",
        "rolledBackAt": now_iso(),
        "latestBackup": str(latest),
        "latestBackupSource": str(source),
        "oldSourceRestored": True,
        "stage2Status": stage2,
        "preRollbackCopy": str(moved_aside) if moved_aside else None,
        "rollbackWarning": "current plugin data changed after migration; latest backup kept" if changed else None,
    })
    write_state(host_id, state)
    return {
        "ok": True,
        "changed": changed,
        "latestBackup": str(latest),
        "oldSourceRestored": True,
        "preRollbackCopy": str(moved_aside) if moved_aside else None,
        "stage2Status": stage2,
        **state,
    }


def legacy_import(host: str, source: str | Path | None = None, apply_now: bool = False) -> dict[str, Any]:
    host_id = hosts.resolve_host(host)
    status = legacy_status(host_id)
    source_path = Path(source) if source else (Path(status["source"]) if status["source"] else None)
    if source_path is None:
        raise MigrationError("no legacy/shared memory source found")
    source_memory = source_path / "memory.json"
    if not source_memory.exists():
        source_memory = source_path / "memory" / "memory.json"
    source_memory_root = source_memory.parent
    target_root = hosts.plugin_root(host_id)
    target_memory_dir = hosts.memory_root(host_id)
    target_memory = target_memory_dir / "memory.json"
    if not source_memory.exists():
        raise MigrationError(f"legacy source has no memory.json: {source_path}")
    if target_memory.exists():
        if inventory(target_memory_dir)["sha256"]["memory"] == inventory(source_memory_root)["sha256"]["memory"]:
            return {"ok": True, "status": "same", "source": str(source_path)}
        report = control_dir(host_id) / "legacy-conflicts" / f"{now_stamp()}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(report, {
            "at": now_iso(), "host": host_id, "source": str(source_path),
            "target": str(target_root), "status": "conflict",
            "sourceInventory": inventory(source_memory_root), "targetInventory": inventory(target_memory_dir),
        })
        return {"ok": False, "status": "conflict", "report": str(report)}
    if not apply_now:
        return {"ok": True, "status": "ready", "source": str(source_path), "target": str(target_root)}
    backup = _backup_plugin(host_id, "legacy-import")
    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_memory_root, target_memory_dir, dirs_exist_ok=True)
    atomic_write_json(target_root / "legacy-import.json", {
        "at": now_iso(), "host": host_id, "source": str(source_path),
        "backup": str(backup), "status": "imported",
    })
    return {"ok": True, "status": "imported", "source": str(source_path), "target": str(target_root)}


def _runtime_tools_candidates(host_id: str, spec: dict[str, Any]) -> list[Path]:
    adapter = spec.get("runtime_adapter")
    candidates: list[Path] = []
    if adapter == "dsh":
        for name in ("PROGRAMMER_WORKFLOW_DSH_TOOLS", "DSH_MIGRATION_TOOLS"):
            value = os.environ.get(name)
            if value:
                candidates.append(Path(value).expanduser())
        # Repository layout: <repo>/dsh-plugin/dsh-migration-tools.
        candidates.append(Path(__file__).resolve().parents[4] / "dsh-plugin" / "dsh-migration-tools")
    elif adapter == "kimi":
        config = _safe_json(hosts.plugin_root(host_id) / "config.json")
        configured = config.get("kimiMigrationTools") if isinstance(config, dict) else None
        if configured:
            candidates.append(Path(str(configured)).expanduser())
        value = os.environ.get("KIMI_MIGRATION_TOOLS")
        if value:
            candidates.append(Path(value).expanduser())
        legacy = LEGACY_TOOL_DIRS.get("kimi")
        if legacy is not None:
            candidates.append(legacy)
    return candidates


def _script_mentions(script: Path, token: str) -> bool:
    try:
        return token.encode("ascii") in script.read_bytes()
    except OSError:
        return False


def _kimi_source_follows_home(migrate: Path) -> bool:
    """A Kimi adapter must honor KIMI_MIG_SRC or the settings page lies."""
    home = os.environ.get("KIMI_HOME")
    if not home:
        return True  # default source is %USERPROFILE%\.kimi-code, exactly what adapters use
    resolved = Path(home).expanduser().resolve()
    if resolved == (Path.home() / ".kimi-code").resolve():
        return True
    return _script_mentions(migrate, "KIMI_MIG_SRC")


def _missing_batch_label(script: Path) -> str | None:
    """First `call :Label` whose `:Label` is absent (an adapter that silently no-ops)."""
    try:
        text = script.read_bytes().decode("latin-1", errors="ignore")
    except OSError:
        return None
    labels: set[str] = set()
    calls: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(":") and len(line) > 1:
            label = line[1:].split()[0]
            if label:
                labels.add(label.lower())
        match = re.match(r"call\s+:([A-Za-z0-9_.\-]+)", line, re.IGNORECASE)
        if match:
            calls.append(match.group(1))
    for name in calls:
        if name.lower() not in labels:
            return name
    return None


def inspect_runtime_adapter(host: str) -> dict[str, Any]:
    """Resolve the stage-2 adapter and prove it is usable.

    A directory counts as ready only when both the migrate and the rollback
    script exist; a migrate-only directory is reported but never treated as
    ready, so status can no longer claim support that prepare cannot use.
    """
    host_id = hosts.resolve_host(host)
    spec = hosts.host_spec(host_id)
    adapter = spec.get("runtime_adapter")
    result: dict[str, Any] = {
        "adapter": adapter,
        "supported": bool(spec.get("runtime_migration_supported")),
        "toolsPath": None,
        "detectedToolsPath": None,
        "adapterReady": False,
        "reason": spec.get("runtime_note", ""),
        "migrateScript": None,
        "rollbackScript": None,
    }
    if not adapter:
        result["reason"] = "当前尚未适配该编辑器的运行数据迁移。"
        return result
    migrate_name = MIGRATE_SCRIPT[adapter]
    rollback_name = ROLLBACK_SCRIPT[adapter]
    candidates = _runtime_tools_candidates(host_id, spec)
    detected = next((c for c in candidates if c and (c / migrate_name).exists()), None)
    complete = next(
        (c for c in candidates if c and (c / migrate_name).exists() and (c / rollback_name).exists()),
        None,
    )
    result["detectedToolsPath"] = str(complete or detected) if (complete or detected) else None
    result["toolsPath"] = str(complete or detected) if (complete or detected) else None
    if complete is None:
        result["reason"] = (
            f"adapter directory is missing {rollback_name}; stage 2 needs a migrate+rollback pair."
            if detected is not None
            else "no usable migration adapter tools found (migrate and rollback scripts are both required)."
        )
        return result
    if adapter == "kimi" and not _kimi_source_follows_home(complete / migrate_name):
        result["reason"] = (
            "KIMI_HOME points outside ~/.kimi-code but the Kimi adapter reads a fixed "
            "%USERPROFILE%\\.kimi-code; install an adapter that honors KIMI_MIG_SRC, or "
            "unset/move KIMI_HOME back to the default."
        )
        return result
    for script_name in (migrate_name, rollback_name):
        missing = _missing_batch_label(complete / script_name)
        if missing:
            result["reason"] = (
                f"{script_name} calls the missing batch label :{missing}; "
                "the adapter's migration/rollback path cannot run."
            )
            return result
    result["adapterReady"] = True
    result["toolsPath"] = str(complete)
    result["migrateScript"] = str(complete / migrate_name)
    result["rollbackScript"] = str(complete / rollback_name)
    result["reason"] = ""
    return result


def runtime_status(host: str) -> dict[str, Any]:
    host_id = hosts.resolve_host(host)
    spec = hosts.host_spec(host_id)
    stage1 = stage1_summary(host_id)
    supported = bool(spec.get("runtime_migration_supported"))
    stage2 = stage2_summary(host_id)
    adapter = inspect_runtime_adapter(host_id)
    status = "blocked"
    reason = "请先完成并校验第一阶段插件数据迁移。"
    if not supported:
        status = "unavailable"
        reason = "当前仅支持迁移 Programmer Workflow 插件数据，尚未适配该编辑器的运行数据迁移。"
    elif not stage1["completed"]:
        status = "blocked"
        reason = "请先完成并校验第一阶段插件数据迁移。"
    elif not adapter["adapterReady"]:
        status = "unavailable"
        reason = adapter["reason"]
    else:
        status = "ready"
        reason = ""
    runtime_state = read_runtime_state(host_id) or {}
    return {
        "host": host_id,
        "supported": supported,
        "adapter": spec.get("runtime_adapter"),
        "stage1Completed": stage1["completed"],
        "stage1Verified": stage1["verified"],
        "stage1CompletedVia": stage1["completedVia"],
        "stage1Target": stage1["target"],
        "stage1VerifiedAt": stage1["verifiedAt"],
        "stage2Status": stage2["status"],
        "stage2Completed": stage2["completed"],
        "stage2Verified": stage2["verified"],
        "stage2CompletedVia": stage2["completedVia"],
        "status": status,
        "reason": reason,
        "note": spec.get("runtime_note", ""),
        "adapterReady": adapter["adapterReady"],
        "adapterReason": adapter["reason"],
        "toolsPath": adapter["toolsPath"],
        "detectedToolsPath": adapter["detectedToolsPath"],
        "migrateScript": adapter["migrateScript"],
        "rollbackScript": adapter["rollbackScript"],
        "launcher": runtime_state.get("launcher"),
        "rollbackLauncher": runtime_state.get("rollbackLauncher"),
        "target": runtime_state.get("target"),
        "targetRoot": runtime_state.get("targetRoot"),
        "actualLocation": stage2["actualLocation"] if stage2["completed"] else None,
        "completedAt": runtime_state.get("completedAt"),
    }
