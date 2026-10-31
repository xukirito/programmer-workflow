"""Host registry and per-host plugin-data roots.

Programmer Workflow keeps one plugin-data tree per Agent/editor. Nothing here
falls back to DSH for a non-DSH host; an unknown host must be explicit, and the
neutral `generic` host is the only anonymous destination.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

HOST_ALIASES = {
    "dsh": "dsh",
    "deepseek": "dsh",
    "deepseek-harness": "dsh",
    "kimi": "kimi",
    "kimi-code": "kimi",
    "kimicode": "kimi",
    "codebuddy": "codebuddy",
    "code-buddy": "codebuddy",
    "claude": "claude",
    "claude-code": "claude",
    "cursor": "cursor",
    "codex": "codex",
    "generic": "generic",
}

HOSTS: dict[str, dict[str, Any]] = {
    "dsh": {
        "id": "dsh",
        "label": "DeepSeek Harness",
        "data_dir": ".dsh",
        "home_env": "DSH_HOME",
        "default_home": "~/.dsh",
        "plugin_migration_supported": True,
        "runtime_adapter": "dsh",
        "runtime_migration_supported": True,
        "runtime_note": "DSH 运行数据迁移适配器（内置脚本，仍为静态/临时目录验证）。",
    },
    "kimi": {
        "id": "kimi",
        "label": "Kimi Code",
        "data_dir": ".kimi-code",
        "home_env": "KIMI_HOME",
        "default_home": "~/.kimi-code",
        "plugin_migration_supported": True,
        "runtime_adapter": "kimi",
        "runtime_migration_supported": True,
        "runtime_note": "Kimi 运行数据迁移适配器；依赖本地 kimi-migration-tools，未配置时不可用。",
    },
    "codebuddy": {
        "id": "codebuddy",
        "label": "CodeBuddy",
        "data_dir": ".codebuddy",
        "home_env": "CODEBUDDY_HOME",
        "default_home": "~/.codebuddy",
        "plugin_migration_supported": True,
        "runtime_adapter": None,
        "runtime_migration_supported": False,
        "runtime_note": "当前只适配项目级 Skill；CodeBuddy 运行数据迁移未实现。",
    },
    "claude": {
        "id": "claude",
        "label": "Claude Code",
        "data_dir": ".claude",
        "home_env": "CLAUDE_HOME",
        "default_home": "~/.claude",
        "plugin_migration_supported": True,
        "runtime_adapter": None,
        "runtime_migration_supported": False,
        "runtime_note": "运行数据迁移未实现；仅插件数据使用独立根。",
    },
    "cursor": {
        "id": "cursor",
        "label": "Cursor",
        "data_dir": ".cursor",
        "home_env": "CURSOR_HOME",
        "default_home": "~/.cursor",
        "plugin_migration_supported": True,
        "runtime_adapter": None,
        "runtime_migration_supported": False,
        "runtime_note": "运行数据迁移未实现；仅插件数据使用独立根。",
    },
    "codex": {
        "id": "codex",
        "label": "Codex",
        "data_dir": ".codex",
        "home_env": "CODEX_HOME",
        "default_home": "~/.codex",
        "plugin_migration_supported": True,
        "runtime_adapter": None,
        "runtime_migration_supported": False,
        "runtime_note": "运行数据迁移未实现；仅插件数据使用独立根。",
    },
    "generic": {
        "id": "generic",
        "label": "Generic",
        "data_dir": ".programmer-workflow",
        "home_env": "PROGRAMMER_WORKFLOW_GENERIC_HOME",
        "default_home": "~/.programmer-workflow",
        "plugin_at_home": True,
        "plugin_migration_supported": True,
        "runtime_adapter": None,
        "runtime_migration_supported": False,
        "runtime_note": "未确定宿主时的中性位置；不共享 DSH 数据，运行数据迁移未实现。",
    },
}


class HostResolutionError(ValueError):
    """Raised when no host was supplied and no deterministic host ID exists."""


def normalize_host(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", "-").replace(" ", "-")
    return HOST_ALIASES.get(text)


def resolve_host(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get("PROGRAMMER_WORKFLOW_HOST")
    if not candidate:
        raise HostResolutionError(
            "host is not specified; pass --host dsh|kimi|codebuddy|claude|cursor|codex|generic "
            "or set PROGRAMMER_WORKFLOW_HOST. Programmer Workflow will not infer a host from cwd "
            "and will not fall back to ~/.dsh for other hosts."
        )
    host = normalize_host(candidate)
    if host is None:
        raise HostResolutionError(f"unknown host: {candidate}")
    return host


def host_spec(host: str | None = None) -> dict[str, Any]:
    host_id = resolve_host(host)
    return dict(HOSTS[host_id])


def _abs(path: Path | str) -> Path:
    """Absolute but NOT symlink-resolved.

    Migration needs the logical path: after a junction exists,
    ``Path.resolve()`` would collapse ``<home>/programmer-workflow`` to its
    target, and a second migration would rename the target instead of the link.
    """
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def host_home(host: str | None = None) -> Path:
    spec = host_spec(host)
    override = os.environ.get(spec["home_env"]) if spec.get("home_env") else None
    if override:
        return _abs(override)
    return _abs(spec["default_home"])


def default_plugin_root(host: str | None = None) -> Path:
    spec = host_spec(host)
    home = host_home(spec["id"])
    if spec.get("plugin_at_home"):
        return home
    return _abs(home / "programmer-workflow")


def plugin_root(host: str | None = None) -> Path:
    override = os.environ.get("PROGRAMMER_WORKFLOW_GLOBAL")
    if override:
        return _abs(override)
    return default_plugin_root(host)


def memory_root(host: str | None = None) -> Path:
    override = os.environ.get("PROGRAMMER_WORKFLOW_HOME")
    if override:
        return _abs(override)
    return _abs(plugin_root(host) / "memory")


def path_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


CLI_ENV = "PROGRAMMER_WORKFLOW_CLI"


def companion_cli(host: str | None = None) -> Path | None:
    """Resolve the Skill CLI that can run stage 1 for this host.

    ``PROGRAMMER_WORKFLOW_CLI`` wins (custom/portable installs, CodeBuddy
    project trees); otherwise the host's own ``skills/programmer-workflow``
    directory is probed. A missing CLI is an explicit "unavailable", never an
    assumed capability.
    """
    override = os.environ.get(CLI_ENV)
    if override:
        candidate = Path(override).expanduser()
        return candidate.resolve() if candidate.exists() else None
    candidate = host_home(host) / "skills" / "programmer-workflow" / "scripts" / "companion.py"
    return candidate.resolve() if candidate.exists() else None


def plugin_migration_capability(host: str | None = None) -> dict[str, Any]:
    spec = host_spec(host)
    if not spec.get("plugin_migration_supported"):
        return {
            "supported": False,
            "ready": False,
            "cliPath": None,
            "reason": spec.get("plugin_migration_note", "该宿主暂不支持插件数据迁移。"),
        }
    cli = companion_cli(spec["id"])
    if cli is None:
        return {
            "supported": True,
            "ready": False,
            "cliPath": None,
            "reason": (
                "未找到该宿主的 Skill CLI（companion.py）：请先安装 Programmer Workflow Skill，"
                f"或把 {CLI_ENV} 指向可用的 companion.py。"
            ),
        }
    return {"supported": True, "ready": True, "cliPath": str(cli), "reason": ""}


def external_overrides(host: str | None = None) -> dict[str, Any]:
    spec = host_spec(host)
    default = default_plugin_root(spec["id"])
    root = plugin_root(spec["id"])
    legacy_memory = os.environ.get("PROGRAMMER_WORKFLOW_HOME")
    mem = memory_root(spec["id"])
    return {
        "globalOverride": str(root) if root != default else None,
        "memoryOverride": str(mem) if legacy_memory else None,
        "pluginRootIsExternal": root != default,
        "memoryRootIsExternal": not path_within(mem, root),
        "hostHome": str(host_home(spec["id"])),
        "defaultPluginRoot": str(default),
    }


def all_hosts() -> list[dict[str, Any]]:
    result = []
    for spec in HOSTS.values():
        capability = plugin_migration_capability(spec["id"])
        result.append({
            "id": spec["id"],
            "label": spec["label"],
            "dataDir": spec["data_dir"],
            "pluginMigrationSupported": bool(spec.get("plugin_migration_supported")),
            "pluginMigrationReady": capability["ready"],
            "pluginMigrationCli": capability["cliPath"],
            "pluginMigrationReason": capability["reason"],
            "runtimeMigrationSupported": bool(spec.get("runtime_migration_supported")),
            "runtimeAdapter": spec.get("runtime_adapter"),
            "runtimeNote": spec.get("runtime_note", ""),
        })
    return result
