"""Local, token-protected settings state and HTTP server.

The Kimi Code surface cannot reuse the DSH React client. Instead
``companion.py settings`` starts this standard-library server on 127.0.0.1 and
opens a static page that talks to a small JSON API:

    GET  /api/config?host=<id>
    GET  /api/status?host=<id>
    POST /api/config?host=<id>
    POST /api/migration/plugin/prepare
    POST /api/migration/runtime/prepare
    POST /api/migration/legacy-import

The workspace is fixed when the server starts. No API accepts a workspace path,
no API executes a migration/rollback/batch file, and every request must name a
known host explicitly. A missing/unknown host is a 400, never a DSH fallback.
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from . import common, config as configlib, hosts, migration

MAX_BODY_BYTES = 256 * 1024
PAGE_HOSTS = ("dsh", "kimi", "codebuddy")
SKILL_NAME = "programmer-workflow"
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
}
STATIC_FILES = {
    "/": ("settings.html", "text/html; charset=utf-8"),
    "/settings.css": ("settings.css", "text/css; charset=utf-8"),
    "/settings.js": ("settings.js", "application/javascript; charset=utf-8"),
}
GET_ROUTES = frozenset({"/api/config", "/api/status"})
POST_ROUTES = frozenset({
    "/api/config",
    "/api/migration/plugin/prepare",
    "/api/migration/runtime/prepare",
    "/api/migration/legacy-import",
})


class SettingsError(RuntimeError):
    """A request-level error the handler can turn into a JSON response."""

    def __init__(self, status: int, message: str, extra: Optional[Dict[str, Any]] = None):
        self.status = int(status)
        self.message = message
        self.extra = dict(extra or {})
        super().__init__(message)


# --------------------------------------------------------------------------
# State assembly
# --------------------------------------------------------------------------

def _real(path: Path) -> str:
    try:
        return str(Path(os.path.realpath(str(path))))
    except OSError:
        return str(path)


def _is_reparse(path: Path) -> bool:
    try:
        return migration._is_reparse(path)
    except OSError:
        return False


def _running_skill_marker() -> str:
    running = hosts.running_companion_cli()
    if running is None or hosts.running_host() is None:
        return ""
    marker = running.parent.parent / "SKILL.md"
    return str(marker) if marker.is_file() else ""


def skill_marker(host_id: str, workspace: Path) -> str:
    candidates = [
        hosts.host_home(host_id) / "skills" / SKILL_NAME / "SKILL.md",
        workspace / ".agents" / "skills" / SKILL_NAME / "SKILL.md",
    ]
    if host_id == "codebuddy":
        candidates.insert(1, workspace / ".codebuddy" / "skills" / SKILL_NAME / "SKILL.md")
    if hosts.running_host() == host_id:
        running_marker = _running_skill_marker()
        if running_marker:
            candidates.insert(0, Path(running_marker))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def _paths_for(host_id: str) -> Dict[str, str]:
    root = hosts.plugin_root(host_id)
    memory = hosts.memory_root(host_id)
    return {
        "globalRoot": str(root),
        "realGlobalRoot": _real(root),
        "memoryRoot": str(memory),
        "realMemoryRoot": _real(memory),
        "configPath": str(root / "config.json"),
        "realConfigPath": _real(root / "config.json"),
        "hostHome": str(hosts.host_home(host_id)),
        "pluginRootDefault": str(hosts.default_plugin_root(host_id)),
        "artifacts": str(root / "artifacts"),
        "logs": str(root / "logs"),
    }


def _desired_plugin_target(host_id: str, cfg: Dict[str, Any]) -> str:
    root = cfg.get("pluginMigrationTargetRoot") or ""
    if not root or not configlib.is_valid_target(root):
        return ""
    try:
        return str(migration.plugin_target(host_id, root))
    except (migration.MigrationError, OSError):
        return ""


def build_plugin_migration(host_id: str) -> Dict[str, Any]:
    state = migration.read_state(host_id) or {}
    summary = migration.stage1_summary(host_id)
    cfg = configlib.read(host_id)
    root = hosts.plugin_root(host_id)
    launcher, rollback_launcher = migration.stage1_launcher_paths(host_id)
    capability = hosts.plugin_migration_capability(host_id)
    desired = _desired_plugin_target(host_id, cfg)
    if summary["completed"]:
        status = "completed"
    elif state.get("status") == "prepared":
        status = "prepared"
    elif state.get("status") == "failed":
        status = "failed"
    elif state.get("status") == "rolled-back":
        status = "rolled-back"
    elif state.get("status") == "completed":
        status = "stale"
    elif _is_reparse(root):
        status = "external"
    else:
        status = "not-started"
    labels = {
        "not-started": ("未开始", "muted"),
        "prepared": ("已准备", "warn"),
        "completed": ("已完成", "ok"),
        "external": ("需要检查", "warn"),
        "stale": ("需要检查", "warn"),
        "failed": ("失败", "error"),
        "rolled-back": ("已回滚", "muted"),
    }
    label, tone = labels.get(status, ("需要检查", "warn"))
    target = summary.get("target") or state.get("target") or desired
    reasons = []
    if not migration.platform_supported():
        reasons.append(migration.platform_reason())
    if not cfg.get("migrationActionEnabled", True):
        reasons.append("设置页的“允许准备迁移脚本”开关当前关闭。")
    if not capability["supported"]:
        reasons.append("该宿主暂不支持插件数据迁移。")
    elif not capability["ready"]:
        reasons.append(capability["reason"])
    ready = not reasons
    return {
        "host": host_id,
        "status": status,
        "label": label,
        "tone": tone,
        "completed": bool(summary["completed"]),
        "verified": bool(summary["verified"]),
        "completedVia": summary.get("completedVia"),
        "verifiedAt": summary.get("verifiedAt"),
        "relocated": bool(summary.get("relocated")),
        "systemDrive": summary.get("systemDrive"),
        "prepared": status == "prepared",
        "source": str(root),
        "target": str(target or ""),
        "desiredTarget": desired,
        "targetRoot": str(state.get("targetRoot") or cfg.get("pluginMigrationTargetRoot") or ""),
        "backup": state.get("backup"),
        "launcher": str(launcher),
        "launcherExists": launcher.is_file(),
        "rollbackLauncher": str(rollback_launcher),
        "rollbackLauncherExists": rollback_launcher.is_file(),
        "statePath": str(migration.state_path(host_id)),
        "supported": bool(capability["supported"]),
        "ready": ready,
        "reasons": [reason for reason in reasons if reason],
        "reason": " ".join(reason for reason in reasons if reason),
        "cliPath": capability.get("cliPath"),
        "linkStatus": "junction" if _is_reparse(root) else ("directory" if root.exists() else "missing"),
        "hostHomeLink": _is_reparse(hosts.host_home(host_id)),
        "actualTargetExists": bool(target) and Path(str(target)).exists(),
        "inventory": migration.inventory(hosts.memory_root(host_id)),
    }


def build_runtime_migration(host_id: str) -> Dict[str, Any]:
    runtime = migration.runtime_status(host_id)
    cfg = configlib.read(host_id)
    state = migration.read_runtime_state(host_id) or {}
    launcher, rollback_launcher = migration.stage2_launcher_paths(host_id)
    stage2_status = str(runtime.get("stage2Status") or "not-started")
    if stage2_status == "completed":
        label, tone = "已完成", "ok"
    elif stage2_status == "prepared":
        label, tone = "已准备", "warn"
    elif stage2_status == "failed":
        label, tone = "需要检查", "error"
    elif stage2_status == "stale":
        label, tone = "需要检查", "warn"
    elif stage2_status == "rolled-back":
        label, tone = "已回滚", "muted"
    elif runtime.get("status") == "blocked":
        label, tone = "等待第一阶段", "warn"
    elif runtime.get("status") == "unavailable":
        label, tone = "当前不可用", "muted"
    else:
        label, tone = "未开始", "muted"
    can_prepare = bool(
        migration.platform_supported()
        and cfg.get("migrationActionEnabled", True)
        and runtime.get("status") == "ready"
        and runtime.get("adapterReady")
    )
    configured_root = configlib.normalize_target(cfg.get("runtimeMigrationTargetRoot") or "")
    desired_target = ""
    if configured_root and configlib.is_valid_target(configured_root):
        desired_target = os.path.join(configured_root, hosts.host_spec(host_id)["data_dir"])
    result = dict(runtime)
    result.update({
        "actionEnabled": bool(cfg.get("migrationActionEnabled", True)),
        "label": label,
        "tone": tone,
        "canPrepare": can_prepare,
        "configuredTargetRoot": str(cfg.get("runtimeMigrationTargetRoot") or ""),
        "desiredTarget": desired_target,
        "launcher": str(state.get("launcher") or launcher),
        "launcherExists": Path(str(state.get("launcher") or launcher)).is_file(),
        "rollbackLauncher": str(state.get("rollbackLauncher") or rollback_launcher),
        "rollbackLauncherExists": Path(str(state.get("rollbackLauncher") or rollback_launcher)).is_file(),
        "statePath": str(migration.runtime_state_path(host_id)),
    })
    return result


def build_legacy(host_id: str) -> Dict[str, Any]:
    status = migration.legacy_status(host_id)
    return {
        "status": status.get("status"),
        "candidates": status.get("candidates", []),
        "present": status.get("present", []),
        "source": status.get("source"),
        "imported": bool(status.get("imported")),
        "same": bool(status.get("same")),
        "conflict": bool(status.get("conflict")),
        "sourceInventory": status.get("sourceInventory"),
        "targetInventory": status.get("targetInventory"),
        "note": "旧共享记忆只能一次性导入；内容不同会生成冲突报告，不会覆盖现有记忆。",
    }


def build_hosts(workspace: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for host_id in PAGE_HOSTS:
        spec = hosts.HOSTS[host_id]
        cfg = configlib.read(host_id)
        capability = hosts.plugin_migration_capability(host_id)
        marker = skill_marker(host_id, workspace)
        result[host_id] = {
            "id": host_id,
            "label": spec["label"],
            "dataDir": spec["data_dir"],
            "home": str(hosts.host_home(host_id)),
            "pluginRoot": str(hosts.plugin_root(host_id)),
            "memoryRoot": str(hosts.memory_root(host_id)),
            "configPath": str(configlib.config_path(host_id)),
            "planFile": f"plan.{cfg.get('planFormat', 'md')}",
            "installed": bool(marker),
            "skillPath": marker,
            "projectLevel": host_id == "codebuddy",
            "pluginMigrationSupported": bool(capability["supported"]),
            "pluginMigrationReady": bool(capability["ready"]),
            "pluginMigrationCli": capability.get("cliPath"),
            "runtimeMigrationSupported": bool(spec.get("runtime_migration_supported")),
            "runtimeAdapter": spec.get("runtime_adapter"),
        }
    return result


def build_state(host: str, workspace: Path) -> Dict[str, Any]:
    host_id = hosts.resolve_host(host)
    workspace = Path(workspace).resolve()
    cfg = configlib.read(host_id)
    paths = _paths_for(host_id)
    plugin = build_plugin_migration(host_id)
    runtime = build_runtime_migration(host_id)
    inventory = migration.inventory(Path(paths["memoryRoot"]))
    return {
        "ok": True,
        "application": SKILL_NAME,
        "version": configlib.PLUGIN_VERSION,
        "host": host_id,
        "hostLabel": hosts.host_spec(host_id)["label"],
        "workspace": str(workspace),
        "config": cfg,
        "configExists": configlib.exists(host_id),
        "paths": paths,
        "external": hosts.external_overrides(host_id),
        "hosts": build_hosts(workspace),
        "hostOrder": list(PAGE_HOSTS),
        "workflowModes": [
            {"id": key, "label": value["label"], "description": value["description"]}
            for key, value in common.WORKFLOW_MODES.items()
        ],
        "migration": {
            "actionEnabled": bool(cfg.get("migrationActionEnabled", True)),
            "platform": {
                "ok": migration.platform_supported(),
                "label": platform.platform(),
                "reason": migration.platform_reason(),
            },
            "plugin": plugin,
            "runtime": runtime,
            "legacy": build_legacy(host_id),
            "workspaceMemory": {
                "path": str(workspace / cfg["workspaceDataDir"]),
                "migratesWithApp": False,
                "note": "工作区记忆属于项目数据，不随任何宿主/应用迁移移动。",
            },
        },
        "inventory": inventory,
        "memoryExists": (Path(paths["memoryRoot"]) / "memory.json").is_file(),
    }


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------

class SettingsServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 16

    def __init__(self, address: tuple[str, int], handler, host: str, workspace: Path, token: str):
        self.host_id = hosts.resolve_host(host)
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise ValueError(f"workspace is not a directory: {self.workspace}")
        self.token = token
        super().__init__(address, handler)

    @property
    def url(self) -> str:
        token = urllib.parse.quote(self.token, safe="")
        host = urllib.parse.quote(self.host_id, safe="")
        return f"http://127.0.0.1:{self.server_address[1]}/?host={host}#token={token}"


def create_server(
    host: str,
    workspace: Path | str,
    port: int = 0,
    token: str | None = None,
) -> SettingsServer:
    """Bind a loopback-only server; port 0 asks the OS for a free port."""
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("port must be an integer between 0 and 65535")
    if port < 0 or port > 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    workspace_path = Path(workspace).expanduser()
    return SettingsServer(
        ("127.0.0.1", port),
        SettingsHandler,
        host,
        workspace_path,
        token or secrets.token_urlsafe(32),
    )


class SettingsHandler(BaseHTTPRequestHandler):
    server_version = "ProgrammerWorkflowSettings/0.1"
    sys_version = ""

    # Keep stdout/stderr clean: the host runs this as a long-lived background
    # task, and the CLI already prints the one URL the user needs.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    # Browser requests are same-origin; no CORS headers are ever sent.
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(405, {"ok": False, "error": "method not allowed"})

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(405, {"ok": False, "error": "method not allowed"})

    def do_PUT(self) -> None:  # noqa: N802
        self._send_json(405, {"ok": False, "error": "method not allowed"})

    def do_PATCH(self) -> None:  # noqa: N802
        self._send_json(405, {"ok": False, "error": "method not allowed"})

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_json(405, {"ok": False, "error": "method not allowed"})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/quick":
            self._quick_link(parsed.query)
            return
        if parsed.path in STATIC_FILES:
            self._serve_static(parsed.path)
            return
        if parsed.path.startswith("/api/"):
            if not self._authorized():
                self._send_json(403, {"ok": False, "error": "访问令牌无效"})
                return
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            try:
                self._handle_get(parsed.path, query)
            except SettingsError as error:
                self._send_json(error.status, {"ok": False, "error": error.message, **error.extra})
            except Exception:
                self._send_json(500, {"ok": False, "error": "internal error"})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in STATIC_FILES:
            self._discard_body()
            self._send_json(405, {"ok": False, "error": "method not allowed"})
            return
        if not parsed.path.startswith("/api/"):
            self._discard_body()
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._discard_body()
            self._send_json(403, {"ok": False, "error": "访问令牌无效"})
            return
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        try:
            body = self._read_json()
            self._handle_post(parsed.path, query, body)
        except SettingsError as error:
            self._send_json(error.status, {"ok": False, "error": error.message, **error.extra})
        except configlib.ConfigError as error:
            self._send_json(400, {"ok": False, "error": str(error)})
        except migration.MigrationConflict as error:
            self._send_json(409, {"ok": False, "error": str(error)})
        except migration.MigrationError as error:
            self._send_json(400, {"ok": False, "error": str(error)})
        except Exception:
            self._send_json(500, {"ok": False, "error": "internal error"})

    # ----------------------------------------------------------------- API

    def _handle_get(self, path: str, query: Dict[str, list[str]]) -> None:
        if path in POST_ROUTES and path not in GET_ROUTES:
            self._send_json(405, {"ok": False, "error": "method not allowed"})
            return
        if path not in GET_ROUTES:
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        host_id = self._host_from(query, None)
        self._send_json(200, build_state(host_id, self.server.workspace))

    def _handle_post(self, path: str, query: Dict[str, list[str]], body: Dict[str, Any]) -> None:
        if path in GET_ROUTES and path not in POST_ROUTES:
            self._send_json(405, {"ok": False, "error": "method not allowed"})
            return
        handler = {
            "/api/config": self._post_config,
            "/api/migration/plugin/prepare": self._post_plugin_prepare,
            "/api/migration/runtime/prepare": self._post_runtime_prepare,
            "/api/migration/legacy-import": self._post_legacy_import,
        }.get(path)
        if handler is None:
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        handler(query, body)

    def _post_config(self, query: Dict[str, list[str]], body: Dict[str, Any]) -> None:
        host_id = self._host_from(query, body)
        if body.get("reset") is True:
            cfg = configlib.reset(host_id)
            state = build_state(host_id, self.server.workspace)
            self._send_json(200, {"ok": True, "host": host_id, "reset": True, "config": cfg, "state": state})
            return
        payload = {key: value for key, value in body.items() if key in configlib.DEFAULTS}
        try:
            cfg = configlib.save(host_id, payload)
        except configlib.ConfigValidationError as error:
            self._send_json(400, {
                "ok": False,
                "error": error.describe(),
                "fields": error.errors,
            })
            return
        state = build_state(host_id, self.server.workspace)
        self._send_json(200, {"ok": True, "host": host_id, "config": cfg, "state": state})

    def _post_plugin_prepare(self, query: Dict[str, list[str]], body: Dict[str, Any]) -> None:
        host_id = self._host_from(query, body)
        target = body.get("targetRoot")
        if not isinstance(target, str) or not target.strip():
            raise SettingsError(400, "请填写第一阶段插件数据目标根", {"field": "pluginMigrationTargetRoot"})
        try:
            configlib.save(host_id, {"pluginMigrationTargetRoot": target})
        except configlib.ConfigValidationError as error:
            self._send_json(400, {"ok": False, "error": error.describe(), "fields": error.errors})
            return
        result = migration.prepare_plugin_migration(host_id, target)
        state = build_state(host_id, self.server.workspace)
        self._send_json(200, {"ok": True, "result": result, "state": state})

    def _post_runtime_prepare(self, query: Dict[str, list[str]], body: Dict[str, Any]) -> None:
        host_id = self._host_from(query, body)
        target = body.get("targetRoot")
        if target is not None and not isinstance(target, str):
            raise SettingsError(400, "targetRoot 必须是字符串", {"field": "runtimeMigrationTargetRoot"})
        updates: Dict[str, Any] = {}
        if isinstance(target, str) and target.strip():
            updates["runtimeMigrationTargetRoot"] = target
        tools = body.get("kimiMigrationTools")
        if isinstance(tools, str):
            updates["kimiMigrationTools"] = tools
        if updates:
            try:
                configlib.save(host_id, updates)
            except configlib.ConfigValidationError as error:
                self._send_json(400, {"ok": False, "error": error.describe(), "fields": error.errors})
                return
        result = migration.prepare_runtime_migration(host_id, target)
        state = build_state(host_id, self.server.workspace)
        self._send_json(200, {"ok": True, "result": result, "state": state})

    def _post_legacy_import(self, query: Dict[str, list[str]], body: Dict[str, Any]) -> None:
        host_id = self._host_from(query, body)
        source = body.get("source")
        if source is not None:
            if not isinstance(source, str):
                raise SettingsError(400, "source 必须是字符串")
            allowed = {os.path.normcase(os.path.abspath(str(item))) for item in migration.legacy_candidates(host_id)}
            if os.path.normcase(os.path.abspath(source)) not in allowed:
                raise SettingsError(400, "只能导入设置页列出的旧共享记忆目录")
        status = migration.legacy_status(host_id)
        if status.get("status") == "none":
            raise SettingsError(400, "没有找到旧共享记忆")
        result = migration.legacy_import(host_id, source=source, apply_now=True)
        state = build_state(host_id, self.server.workspace)
        if not result.get("ok") or result.get("status") == "conflict":
            self._send_json(409, {"ok": False, "error": "旧记忆与当前记忆不同，已生成冲突报告，未覆盖任何文件。", "result": result, "state": state})
            return
        self._send_json(200, {"ok": True, "result": result, "state": state})

    # -------------------------------------------------------------- helpers

    def _host_from(self, query: Dict[str, list[str]], body: Optional[Dict[str, Any]]) -> str:
        query_host = (query.get("host") or [None])[0]
        body_host = body.get("host") if isinstance(body, dict) else None
        if query_host and body_host:
            query_id = hosts.normalize_host(query_host)
            body_id = hosts.normalize_host(body_host)
            if query_id is None or body_id is None or query_id != body_id:
                raise SettingsError(400, f"unknown or mismatched host: {query_host} / {body_host}")
        raw = query_host if query_host else body_host
        if raw is None or not str(raw).strip():
            raise SettingsError(400, "host is required")
        host_id = hosts.normalize_host(raw)
        if host_id is None:
            raise SettingsError(400, f"unknown host: {raw}")
        return host_id

    def _authorized(self) -> bool:
        given = self.headers.get("X-Programmer-Workflow-Token", "")
        token = getattr(self.server, "token", "")
        return bool(token) and secrets.compare_digest(str(given), str(token))

    def _read_json(self) -> Dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise SettingsError(400, "POST 只接受 application/json")
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            raise SettingsError(400, "缺少 Content-Length")
        try:
            length = int(length_header)
        except (TypeError, ValueError):
            raise SettingsError(400, "Content-Length 无效")
        if length < 0:
            raise SettingsError(400, "Content-Length 无效")
        if length > MAX_BODY_BYTES:
            # Drain a bounded amount before answering. Closing while the client
            # is still writing turns a clean 400 into a connection reset.
            self._discard(min(length, MAX_BODY_BYTES + 1024 * 1024))
            raise SettingsError(400, "请求体过大")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise SettingsError(400, "请求体不完整")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise SettingsError(400, "请求体必须是合法的 JSON 对象")
        if not isinstance(data, dict):
            raise SettingsError(400, "请求体必须是 JSON 对象")
        return data

    def _discard(self, count: int) -> None:
        remaining = max(0, int(count))
        while remaining > 0:
            chunk = self.rfile.read(min(65536, remaining))
            if not chunk:
                return
            remaining -= len(chunk)

    def _discard_body(self) -> None:
        """Consume a small rejected body so the client reads the JSON error."""
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return
        try:
            length = int(length_header)
        except (TypeError, ValueError):
            return
        if 0 < length <= MAX_BODY_BYTES + 1024 * 1024:
            self._discard(length)

    def _quick_link(self, raw_query: str) -> None:
        """Loopback-only redirect that puts the per-server token in the fragment.

        The Kimi plugin's official ``interface.homepage`` link points here, so a
        user can open the settings page from plugin details without running a
        command or spending a model turn. The fragment never reaches the server
        or a Referer header.
        """
        peer = str(self.client_address[0] if self.client_address else "")
        if peer not in ("127.0.0.1", "::1"):
            self._send_json(403, {"ok": False, "error": "quick link is loopback-only"})
            return
        query = urllib.parse.parse_qs(raw_query, keep_blank_values=True)
        raw_host = (query.get("host") or ["kimi"])[0]
        host_id = hosts.normalize_host(raw_host)
        if host_id is None:
            self._send_json(400, {"ok": False, "error": f"unknown host: {raw_host}"})
            return
        token = str(getattr(self.server, "token", ""))
        location = "/?host=" + urllib.parse.quote(host_id) + "#token=" + urllib.parse.quote(token)
        self._redirect(location)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()

    def _serve_static(self, path: str) -> None:
        filename, content_type = STATIC_FILES[path]
        target = common.templates_dir() / filename
        try:
            data = target.read_bytes()
        except OSError:
            self._send_json(500, {"ok": False, "error": "static resource missing"})
            return
        self._send(200, data, content_type)

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._send(status, data, "application/json; charset=utf-8")

    def _send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


# --------------------------------------------------------------------------
# CLI entry
# --------------------------------------------------------------------------

def serve(host: str, workspace: Path | str, port: int = 0, open_browser: bool = False) -> int:
    """Print the URL and serve until interrupted; the host owns the task."""
    common.configure_stdout()
    server = create_server(host, workspace, port=port)
    label = hosts.host_spec(server.host_id)["label"]
    url = server.url
    print(f"Programmer Workflow settings · {label}")
    print(f"URL: {url}")
    print(f"host: {server.host_id}")
    print(f"workspace: {server.workspace}")
    print(f"config: {configlib.config_path(server.host_id)}")
    print("服务只监听 127.0.0.1；按 Ctrl+C 或结束该后台任务即可停止。", flush=True)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as error:  # pragma: no cover - environment dependent
            print(f"[warn] could not open the browser automatically: {error}", file=sys.stderr)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
