"""Strict, host-scoped configuration read/write for the settings page.

The CLI keeps using ``common.load_plugin_config`` for tolerant reads. This module
is the *write* path used by the local settings server: it validates every known
field strictly, merges a partial payload with the on-disk document under a file
lock, and only then atomically replaces ``<host-root>/config.json``.

Nothing here falls back to DSH for another host, and a save failure never
replaces the user's draft with defaults.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable

from . import common, hosts

SCHEMA_VERSION = common.SCHEMA_VERSION
PLUGIN_VERSION = "0.1.1"

# common.DEFAULT_CONFIG is the shared base; the settings page adds the fields
# the DSH Host plugin already writes so both surfaces keep the same document.
DEFAULTS: Dict[str, Any] = dict(common.DEFAULT_CONFIG)
DEFAULTS.update({
    "migrationActionEnabled": True,
    "migrationTarget": "",
    "kimiMigrationTarget": "",
    "kimiMigrationTools": "",
    "pluginMigrationTargetRoot": "",
    "runtimeMigrationTargetRoot": "",
})

PATH_FIELDS = ("workspaceDataDir", "debugLogDir", "docsDir", "prototypeFile")
BOOL_FIELDS = (
    "userMemoryEnabled", "workspaceMemoryEnabled", "devOnlyAutoInstrument",
    "docsEnabled", "prototypeEnabled", "promptMigration", "migrationActionEnabled",
    "screenshotEnabled", "balanceDisplay",
)
INT_LIMITS = {
    "satisfactionThreshold": (1, 10),
    "bugfixThreshold": (1, 10),
    "retentionDays": (1, 365),
    "balanceRefreshSeconds": (15, 600),
}
WORKFLOW_MODES = tuple(common.WORKFLOW_MODES)
PLAN_FORMATS = ("md", "html")
TARGET_FIELDS = ("migrationTarget", "kimiMigrationTarget", "kimiMigrationTools")
OPTIONAL_ROOT_FIELDS = ("pluginMigrationTargetRoot", "runtimeMigrationTargetRoot")
LANGUAGE_MAX = 20
# Windows batch launchers cannot survive these characters, and a target root is
# interpolated into `set "..."` lines. Reject the same set as the DSH Host.
_BATCH_UNSAFE = re.compile(r'[%!&|<>^"\r\n\x00]')
_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
METADATA_KEYS = ("schema", "name", "host", "version", "generatedAt", "globalRoot")


class ConfigError(ValueError):
    """Base error for configuration read/write problems."""


class ConfigValidationError(ConfigError):
    """A strict validation failure carrying one message per field."""

    def __init__(self, errors: Dict[str, str]):
        self.errors = dict(errors)
        super().__init__(self.describe())

    def describe(self) -> str:
        return "；".join(f"{key}: {message}" for key, message in self.errors.items())


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def config_path(host: str | None = None) -> Path:
    """The one config file this host owns."""
    return hosts.plugin_root(host) / "config.json"


def lock_path(host: str | None = None) -> Path:
    return config_path(host).with_name(".config.lock")


def is_safe_relative(value: Any) -> bool:
    """A non-empty workspace-relative path that cannot escape the workspace."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or _CONTROL.search(text):
        return False
    normalized = text.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        return False
    if _DRIVE_PATH.match(normalized) or re.match(r"^[A-Za-z]:", normalized):
        return False
    if normalized.startswith("~"):
        return False
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts:
        return False
    return all(part != ".." for part in parts)


def normalize_relative(value: str) -> str:
    parts = [part for part in str(value).strip().replace("\\", "/").split("/") if part not in ("", ".")]
    return "/".join(parts)


def is_valid_target(value: Any, allow_empty: bool = True) -> bool:
    """Windows drive path or POSIX absolute path; UNC/shell metacharacters refused."""
    if value is None:
        return allow_empty
    if not isinstance(value, str):
        return False
    text = value.strip().strip('"')
    if not text:
        return allow_empty
    if _CONTROL.search(text) or _BATCH_UNSAFE.search(text):
        return False
    if text.startswith("\\\\") or text.startswith("//"):
        return False
    if not (_DRIVE_PATH.match(text) or text.startswith("/")):
        return False
    return ".." not in re.split(r"[\\/]", text)


def normalize_target(value: Any) -> str:
    """Store a canonical target string; empty stays empty."""
    if value is None:
        return ""
    text = str(value).strip().strip('"')
    if not text:
        return ""
    if text.startswith("/") and not text.startswith("//"):
        return text.rstrip("/") or "/"
    return text.replace("/", "\\").rstrip("\\") or text


# --------------------------------------------------------------------------
# Read (tolerant, for display) and raw read (for merge)
# --------------------------------------------------------------------------

def _raw_document(host: str | None = None) -> Dict[str, Any]:
    path = config_path(host)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, ValueError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _coerce_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _coerce_int(value: Any, default: int, limits: Iterable[int]) -> int:
    low, high = limits
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(int(low), min(int(high), value))


def normalize_config(source: Any) -> Dict[str, Any]:
    """Best-effort normalization used for display and for launcher inputs.

    This never raises and never writes. The strict rules live in
    :func:`validate_config` and are applied on every save.
    """
    raw = source if isinstance(source, dict) else {}
    config: Dict[str, Any] = {}
    for key in PATH_FIELDS:
        config[key] = common.safe_workspace_relative(raw.get(key, DEFAULTS[key]), str(DEFAULTS[key]))
    for key in BOOL_FIELDS:
        config[key] = _coerce_bool(raw.get(key), bool(DEFAULTS[key]))
    for key, limits in INT_LIMITS.items():
        config[key] = _coerce_int(raw.get(key), int(DEFAULTS[key]), limits)
    mode = str(raw.get("workflowMode") or "").strip().lower().replace("_", "-")
    config["workflowMode"] = mode if mode in WORKFLOW_MODES else str(DEFAULTS["workflowMode"])
    config["planFormat"] = "html" if str(raw.get("planFormat", "")).strip().lower() == "html" else "md"
    language = str(raw.get("language") or "").strip() or str(DEFAULTS["language"])
    config["language"] = _CONTROL.sub("", language)[:LANGUAGE_MAX] or str(DEFAULTS["language"])
    for key in TARGET_FIELDS + OPTIONAL_ROOT_FIELDS:
        candidate = raw.get(key, DEFAULTS[key])
        config[key] = normalize_target(candidate) if is_valid_target(candidate) else str(DEFAULTS[key])
    return config


def read(host: str | None = None) -> Dict[str, Any]:
    """The effective values shown by the settings page (tolerant)."""
    return normalize_config(_raw_document(host))


# --------------------------------------------------------------------------
# Strict validation
# --------------------------------------------------------------------------

def validate_config(config: Any) -> Dict[str, str]:
    """Return ``{field: message}``; an empty dict means the document is valid."""
    if not isinstance(config, dict):
        return {"config": "配置必须是 JSON 对象"}
    errors: Dict[str, str] = {}
    for key in PATH_FIELDS:
        if not is_safe_relative(config.get(key)):
            errors[key] = "必须是工作区内的非空相对路径（不能是绝对路径，也不能包含 ..）"
    for key in BOOL_FIELDS:
        if not isinstance(config.get(key), bool):
            errors[key] = "必须是 JSON 布尔值 true 或 false"
    for key, (low, high) in INT_LIMITS.items():
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            errors[key] = f"必须是 {low}–{high} 的整数"
        elif value < low or value > high:
            errors[key] = f"必须在 {low}–{high} 之间"
    mode = config.get("workflowMode")
    if mode not in WORKFLOW_MODES:
        errors["workflowMode"] = "必须是 plan 或 full-authority"
    if config.get("planFormat") not in PLAN_FORMATS:
        errors["planFormat"] = "必须是 md 或 html"
    language = config.get("language")
    if not isinstance(language, str) or not language.strip():
        errors["language"] = "必须是非空字符串"
    elif len(language) > LANGUAGE_MAX or _CONTROL.search(language):
        errors["language"] = f"必须是不超过 {LANGUAGE_MAX} 个字符且不含控制字符的字符串"
    for key in TARGET_FIELDS + OPTIONAL_ROOT_FIELDS:
        value = config.get(key)
        if value is None:
            errors[key] = "必须是绝对路径或留空"
        elif not isinstance(value, str):
            errors[key] = "必须是字符串路径或留空"
        elif not is_valid_target(value):
            errors[key] = "必须是绝对路径（不能是 UNC，且不能包含 % ! & | < > ^ \"）或留空"
    return errors


def _normalize_valid(config: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalize already-valid values before writing."""
    result = dict(config)
    for key in PATH_FIELDS:
        result[key] = normalize_relative(str(result[key]))
    result["language"] = str(result["language"]).strip()
    for key in TARGET_FIELDS + OPTIONAL_ROOT_FIELDS:
        result[key] = normalize_target(result.get(key))
    return result


def _document(host_id: str, config: Dict[str, Any], extras: Dict[str, Any] | None = None) -> Dict[str, Any]:
    document: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "name": "Programmer Workflow",
        "host": host_id,
        "version": PLUGIN_VERSION,
        "generatedAt": common.now_iso(),
        "globalRoot": str(hosts.plugin_root(host_id)),
    }
    for key in DEFAULTS:
        document[key] = config[key]
    # Preserve fields a newer DSH/CLI surface may have written; dropping them
    # would be a silent cross-version field loss even though this page does not
    # know how to edit them.
    for key, value in (extras or {}).items():
        if key not in METADATA_KEYS and key not in DEFAULTS:
            document[key] = value
    return document


def _merge_with(payload: Dict[str, Any], old: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in old:
            merged[key] = old[key]
    for key in DEFAULTS:
        if key in payload:
            merged[key] = payload[key]
    return merged


def save(host: str, payload: Any) -> Dict[str, Any]:
    """Lock -> read old -> merge -> full validation -> atomic write.

    A partial payload is merged with the document on disk *inside* the lock so a
    concurrent save from the DSH and Kimi settings pages cannot drop fields.
    """
    host_id = hosts.resolve_host(host)
    if not isinstance(payload, dict):
        raise ConfigValidationError({"config": "配置必须是 JSON 对象"})
    path = config_path(host_id)
    common.ensure_dir(path.parent)
    with common.locked(lock_path(host_id)):
        old = _raw_document(host_id)
        merged = _merge_with({key: value for key, value in payload.items() if key in DEFAULTS}, old)
        errors = validate_config(merged)
        if errors:
            raise ConfigValidationError(errors)
        config = _normalize_valid(merged)
        extras = {key: value for key, value in old.items() if key not in DEFAULTS and key not in METADATA_KEYS}
        common.atomic_write_json(path, _document(host_id, config, extras))
    return config


def reset(host: str) -> Dict[str, Any]:
    """Restore only this host's config.json; memory files are untouched."""
    host_id = hosts.resolve_host(host)
    path = config_path(host_id)
    common.ensure_dir(path.parent)
    config = _normalize_valid(dict(DEFAULTS))
    with common.locked(lock_path(host_id)):
        common.atomic_write_json(path, _document(host_id, config))
    return config


def exists(host: str | None = None) -> bool:
    return config_path(host).is_file()
