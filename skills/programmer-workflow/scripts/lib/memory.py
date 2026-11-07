"""User-level and workspace-level memory with an approval gate.

Only entries whose status is ``active`` are rendered into MEMORY.md and into the
session boot block. Proposed entries wait for an explicit user decision. This is
the mechanism behind requirements 1, 4 and 7.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from .common import (
    SCHEMA_VERSION,
    atomic_write_json,
    atomic_write_text,
    ensure_dir,
    locked,
    md_escape,
    new_id,
    now_iso,
    read_json,
    truncate,
    user_home,
    load_plugin_config,
    normalize_workflow_mode,
    workspace_root,
    workspace_state,
)

SCOPES = ("user", "workspace")
STATUSES = ("proposed", "active", "rejected")
KINDS = ("workflow", "habit", "preference", "convention", "environment", "decision", "fact", "reminder")
SOURCES = ("user", "conversation", "files", "system", "promotion")

KIND_LABELS = {
    "workflow": "工作方式",
    "habit": "习惯",
    "preference": "偏好",
    "convention": "项目约定",
    "environment": "环境",
    "decision": "决策",
    "fact": "事实",
    "reminder": "提醒",
}
KIND_ORDER = {k: i for i, k in enumerate(KINDS)}
STATUS_LABELS = {"proposed": "待审核", "active": "生效中", "rejected": "已拒绝"}


class MemoryDataError(RuntimeError):
    pass


class AmbiguousIdError(RuntimeError):
    pass


def _norm_text(text: str) -> str:
    return re.sub(r"[\s，。；：、,.!?！？;:'\"（）()\[\]【】]+", "", text.lower())


def _coerce_list(value: Any, limit: int = 20) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        value = [str(value)]
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text[:800])
        if len(out) >= limit:
            break
    return out


class MemoryStore:
    def __init__(
        self,
        scope: str,
        *,
        workspace: Path | None = None,
        home: Path | None = None,
    ):
        if scope not in SCOPES:
            raise ValueError(f"unknown scope: {scope}")
        self.scope = scope
        self.workspace = (workspace or workspace_root()).resolve() if scope == "workspace" else None
        if scope == "user":
            self.root = (home or user_home()).resolve()
        else:
            self.root = workspace_state(self.workspace).resolve()
        self.json_path = self.root / "memory.json"
        self.md_path = self.root / "MEMORY.md"
        self.lock_path = self.root / "memory.lock"

    # -- io -------------------------------------------------------------
    def _default(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "scope": self.scope,
            "workspace": str(self.workspace) if self.workspace else None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "entries": [],
        }

    def ensure(self) -> None:
        try:
            ensure_dir(self.root)
        except PermissionError as exc:
            raise PermissionError(
                f"cannot create memory directory: {self.root}. "
                "On a sandboxed host (for example DSH workspace-write), choose full access for this "
                "write, or set PROGRAMMER_WORKFLOW_HOME to a writable directory."
            ) from exc
        if not self.json_path.exists():
            atomic_write_json(self.json_path, self._default())
        if not (self.root / "README.md").exists():
            atomic_write_text(self.root / "README.md", self._readme_text())
        self.render()

    def can_write(self) -> bool:
        """Best-effort, read-only check used by boot/doctor.

        ``os.access`` can be optimistic on Windows ACLs, so it is only a hint;
        the real write path returns an actionable PermissionError. Never probe by
        creating a file here: on sandboxed hosts that can block on approval.
        """
        import os
        probe = self.root if self.root.exists() else self.root.parent
        return probe.exists() and os.access(probe, os.W_OK)

    def load(self) -> dict[str, Any]:
        try:
            data = read_json(self.json_path)
        except Exception as exc:  # json.JSONDecodeError, OSError, UnicodeError
            raise MemoryDataError(
                f"memory file is not valid: {self.json_path} ({exc}). "
                "Move it aside or repair it; refusing to overwrite it silently."
            ) from exc
        if data is None:
            return self._default()
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise MemoryDataError(
                f"memory file is not valid: {self.json_path}. "
                "Move it aside or repair it; refusing to overwrite it silently."
            )
        data.setdefault("schema", SCHEMA_VERSION)
        data.setdefault("scope", self.scope)
        data.setdefault("entries", [])
        for entry in data["entries"]:
            entry.setdefault("status", "proposed")
            entry.setdefault("kind", "fact")
            entry.setdefault("confidence", 0.7)
            entry.setdefault("evidence", [])
            entry.setdefault("tags", [])
            entry.setdefault("source", "conversation")
        return data

    def _save(self, data: dict[str, Any]) -> None:
        data["schema"] = SCHEMA_VERSION
        data["scope"] = self.scope
        data["updated_at"] = now_iso()
        atomic_write_json(self.json_path, data)
        self.render(data)

    @contextmanager
    def transaction(self) -> Iterator[dict[str, Any]]:
        try:
            ensure_dir(self.root)
        except PermissionError as exc:
            raise PermissionError(
                f"cannot write memory directory: {self.root}. "
                "On a sandboxed host, choose full access for this write or set PROGRAMMER_WORKFLOW_HOME."
            ) from exc
        with locked(self.lock_path):
            data = self.load()
            yield data
            self._save(data)

    # -- mutation -------------------------------------------------------
    def add(
        self,
        *,
        kind: str,
        text: str,
        detail: str = "",
        evidence: Iterable[str] | None = None,
        confidence: float = 0.7,
        source: str = "conversation",
        status: str = "proposed",
        tags: Iterable[str] | None = None,
        dedupe: bool = True,
    ) -> tuple[dict[str, Any], bool]:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
        if status not in STATUSES:
            raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            raise ValueError("text must not be empty")
        if len(text) > 2000:
            raise ValueError("text is too long (max 2000 characters)")
        if source not in SOURCES:
            source = "conversation"
        confidence = max(0.0, min(1.0, float(confidence)))
        entry = {
            "id": new_id("u" if self.scope == "user" else "w"),
            "status": status,
            "kind": kind,
            "text": text,
            "detail": str(detail or "").strip()[:4000],
            "evidence": _coerce_list(evidence),
            "confidence": round(confidence, 2),
            "source": source,
            "tags": _coerce_list(tags, limit=12),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "approved_at": now_iso() if status == "active" else None,
            "promoted_from": None,
        }
        with self.transaction() as data:
            if dedupe:
                target = _norm_text(text)
                for existing in data["entries"]:
                    if existing.get("status") in ("active", "proposed") and _norm_text(existing.get("text", "")) == target:
                        return existing, False
            data["entries"].append(entry)
        return entry, True

    def _resolve(self, prefix: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
        prefix = prefix.strip()
        exact = [e for e in entries if e.get("id") == prefix]
        if len(exact) == 1:
            return exact[0]
        matches = [e for e in entries if str(e.get("id", "")).startswith(prefix)]
        if not matches:
            raise KeyError(f"no memory entry matches id: {prefix}")
        if len(matches) > 1:
            ids = ", ".join(str(e.get("id")) for e in matches[:8])
            raise AmbiguousIdError(f"id prefix is ambiguous: {prefix} ({ids})")
        return matches[0]

    def set_status(self, prefixes: Iterable[str], status: str) -> list[dict[str, Any]]:
        if status not in STATUSES:
            raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
        updated: list[dict[str, Any]] = []
        with self.transaction() as data:
            for prefix in prefixes:
                entry = self._resolve(prefix, data["entries"])
                entry["status"] = status
                entry["updated_at"] = now_iso()
                entry["approved_at"] = now_iso() if status == "active" else entry.get("approved_at")
                updated.append(entry)
        return updated

    def edit(self, prefix: str, **fields: Any) -> dict[str, Any]:
        allowed = {"text", "detail", "kind", "confidence", "tags", "evidence"}
        with self.transaction() as data:
            entry = self._resolve(prefix, data["entries"])
            for key, value in fields.items():
                if key not in allowed or value is None:
                    continue
                if key == "kind" and value not in KINDS:
                    raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
                if key == "confidence":
                    value = max(0.0, min(1.0, float(value)))
                if key in ("tags", "evidence"):
                    value = _coerce_list(value)
                if key == "text":
                    value = re.sub(r"\s+", " ", str(value)).strip()
                    if not value:
                        raise ValueError("text must not be empty")
                entry[key] = value
            entry["updated_at"] = now_iso()
        return entry

    def delete(self, prefixes: Iterable[str]) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        with self.transaction() as data:
            for prefix in prefixes:
                entry = self._resolve(prefix, data["entries"])
                data["entries"].remove(entry)
                removed.append(entry)
        return removed

    def promote(self, prefixes: Iterable[str], target: "MemoryStore") -> list[dict[str, Any]]:
        """Copy workspace entries into user memory as proposals (never auto-active)."""
        if self.scope != "workspace":
            raise ValueError("only workspace memory can be promoted")
        copied: list[dict[str, Any]] = []
        with self.transaction() as data:
            for prefix in prefixes:
                entry = self._resolve(prefix, data["entries"])
                new_entry, _ = target.add(
                    kind=entry.get("kind", "fact"),
                    text=entry.get("text", ""),
                    detail=entry.get("detail", ""),
                    evidence=[*entry.get("evidence", []), f"promoted from {self.workspace}"],
                    confidence=float(entry.get("confidence", 0.7)),
                    source="promotion",
                    status="proposed",
                    tags=entry.get("tags", []),
                )
                entry["promoted_to"] = new_entry["id"]
                entry["updated_at"] = now_iso()
                copied.append(new_entry)
        return copied

    # -- queries --------------------------------------------------------
    def entries(self, status: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        data = self.load()
        items = list(data.get("entries", []))
        if status and status != "all":
            items = [e for e in items if e.get("status") == status]
        if kind:
            items = [e for e in items if e.get("kind") == kind]
        items.sort(key=lambda e: (KIND_ORDER.get(e.get("kind", "fact"), 99), str(e.get("created_at", ""))))
        return items

    def counts(self) -> dict[str, int]:
        result = {s: 0 for s in STATUSES}
        for entry in self.entries():
            status = entry.get("status", "proposed")
            result[status] = result.get(status, 0) + 1
        result["total"] = sum(result.values())
        return result

    def render_markdown(self, data: dict[str, Any] | None = None) -> str:
        data = data or self.load()
        active = [e for e in data["entries"] if e.get("status") == "active"]
        proposed = [e for e in data["entries"] if e.get("status") == "proposed"]
        active.sort(key=lambda e: (KIND_ORDER.get(e.get("kind", "fact"), 99), str(e.get("created_at", ""))))
        proposed.sort(key=lambda e: (KIND_ORDER.get(e.get("kind", "fact"), 99), str(e.get("created_at", ""))))
        title = "用户记忆（全局）" if self.scope == "user" else "工作区记忆"
        lines = [
            f"# {title}",
            "",
            "> 由 Programmer Workflow 生成，请勿手工编辑。",
            f"> 作用域：`{self.scope}`" + (f" · 工作区：`{self.workspace}`" if self.workspace else " · 所有工作区"),
            f"> 更新时间：{data.get('updated_at', now_iso())}",
            "> 只有「生效中」的条目会被 Agent 遵守；「待审核」条目必须由用户定夺。",
            "",
            f"## 生效中（{len(active)}）",
            "",
        ]
        if not active:
            lines.append("_暂无生效条目。_")
        else:
            for kind in KINDS:
                group = [e for e in active if e.get("kind") == kind]
                if not group:
                    continue
                lines.extend([f"### {KIND_LABELS[kind]}", ""])
                for entry in group:
                    meta = f"`{entry.get('id')}` · 置信度 {entry.get('confidence', 0.7):.2f} · 来源 {entry.get('source', 'conversation')}"
                    line = f"- {md_escape(entry.get('text', ''))}"
                    if entry.get("detail"):
                        line += f" — {md_escape(entry.get('detail', ''))}"
                    lines.append(line)
                    lines.append(f"  <sub>{meta}</sub>")
                lines.append("")
        lines.extend([f"## 待审核（{len(proposed)}，不生效）", ""])
        if not proposed:
            lines.append("_没有待审核条目。_")
        else:
            for entry in proposed:
                lines.append(
                    f"- [ ] {md_escape(entry.get('text', ''))} "
                    f"`{entry.get('id')}` · {KIND_LABELS.get(entry.get('kind', 'fact'), entry.get('kind'))}"
                )
                if entry.get("evidence"):
                    lines.append(f"  - 证据：{'; '.join(md_escape(x) for x in entry['evidence'][:3])}")
        lines.append("")
        return "\n".join(lines)

    def render(self, data: dict[str, Any] | None = None) -> None:
        atomic_write_text(self.md_path, self.render_markdown(data))

    # -- boot -----------------------------------------------------------
    def boot_entries(self, limit: int = 40, exclude_tags: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        entries = self.entries(status="active")
        if exclude_tags:
            excluded = set(exclude_tags)
            entries = [entry for entry in entries if not excluded.intersection(entry.get("tags") or [])]
        return entries[:limit]

    def active_char_count(self) -> int:
        return sum(len(e.get("text", "")) + len(e.get("detail", "")) for e in self.entries(status="active"))

    def _readme_text(self) -> str:
        where = "全局（所有工作区）" if self.scope == "user" else f"当前工作区：`{self.workspace}`"
        return f"""# Programmer Workflow · {self.scope} memory

这个目录保存 {where} 的 Agent 记忆。请通过 skill 内的 CLI 读写，不要手工编辑 `memory.json`。

- `memory.json`：结构化记忆（包含待审核、已拒绝的审计记录）
- `MEMORY.md`：只包含「生效中」与「待审核」条目的可读版本
- `memory.lock`：并发写锁

常用命令（把 `<skill>` 换成 skill 目录）：

```bash
python <skill>/scripts/companion.py memory show --scope {self.scope}
python <skill>/scripts/companion.py memory propose --scope {self.scope} --kind habit --text "..." --evidence "..."
python <skill>/scripts/companion.py memory review --scope {self.scope}
python <skill>/scripts/companion.py memory accept <id> --scope {self.scope}
python <skill>/scripts/companion.py memory reject <id> --scope {self.scope}
```

原则：用户没有明确同意前，任何习惯/偏好只能以 `proposed` 状态存在；只有 `active` 会被遵守。
"""


def text_boot_block(store: MemoryStore, limit: int = 40, exclude_tags: tuple[str, ...] = ()) -> str:
    entries = store.boot_entries(limit, exclude_tags=exclude_tags)
    counts = store.counts()
    visible_active = len(store.boot_entries(100000, exclude_tags=exclude_tags)) if exclude_tags else counts.get("active", 0)
    label = "USER MEMORY (global)" if store.scope == "user" else f"WORKSPACE MEMORY ({store.workspace})"
    lines = [f"{label} — {visible_active} active, {counts.get('proposed', 0)} pending"]
    if not entries:
        lines.append("- (no active entries)")
    for entry in entries:
        detail = f" — {entry.get('detail')}" if entry.get("detail") else ""
        lines.append(f"- [{entry.get('kind')}] {entry.get('text')}{detail}")
    return "\n".join(lines)


def workspace_environment_flags(workspace: Path | None = None) -> dict[str, Any]:
    """Read active workspace environment facts relevant to instrumentation."""
    ws = (workspace or workspace_root()).resolve()
    store = MemoryStore("workspace", workspace=ws)
    flags = {"dev_only": False, "no_hardware": False, "evidence": []}
    if not store.json_path.exists():
        return flags
    try:
        entries = store.load().get("entries", [])
    except MemoryDataError:
        return flags
    for entry in entries:
        if entry.get("status") != "active" or entry.get("kind") != "environment":
            continue
        text = str(entry.get("text", "")).lower()
        dev = any(token in text for token in ("dev-only", "dev only", "纯开发", "开发环境", "无部署"))
        hardware = any(token in text for token in ("no-hardware", "no hardware", "无硬件", "没有硬件", "无实机", "没有可搭配", "物理硬件"))
        if dev or hardware:
            flags["evidence"].append(str(entry.get("id", "")))
        flags["dev_only"] = flags["dev_only"] or dev
        flags["no_hardware"] = flags["no_hardware"] or hardware
    return flags


def boot_payload(workspace: Path | None = None) -> dict[str, Any]:
    ws = (workspace or workspace_root()).resolve()
    cfg = load_plugin_config(ws)
    user = MemoryStore("user")
    local = MemoryStore("workspace", workspace=ws)
    user_enabled = bool(cfg.get("userMemoryEnabled", True))
    workspace_enabled = bool(cfg.get("workspaceMemoryEnabled", True))
    env_flags = workspace_environment_flags(ws)
    dev_auto = bool(cfg.get("devOnlyAutoInstrument", True))
    workflow_mode = normalize_workflow_mode(cfg.get("workflowMode"))
    # Reuse a cached probe; probe once on the first boot and then stay quiet.
    # Imported lazily so memory.py and environment.py do not form an import cycle.
    try:
        from . import environment as environmentlib

        cache = environmentlib.load_cached(ws)
        if cache is None:
            cache, _ = environmentlib.ensure_cached(ws, record=True)
        environment_info = environmentlib.summary(cache, ws)
        environment_line = environmentlib.boot_line(cache, ws)
    except (OSError, ValueError, KeyError) as error:
        environment_info = {"probed": False, "error": str(error)}
        environment_line = f"ENVIRONMENT — 探测失败：{error}"
    payload: dict[str, Any] = {
        "tool": "programmer-workflow",
        "workspace": str(ws),
        "host": cfg.get("host"),
        "globalRoot": cfg.get("globalRoot"),
        "workflow": {
            "mode": workflow_mode,
            "planFormat": cfg.get("planFormat", "md"),
            "devOnlyAutoInstrument": dev_auto,
            "devOnlyFact": bool(env_flags["dev_only"] and env_flags["no_hardware"]),
            "devOnlyDirect": bool(dev_auto and env_flags["dev_only"] and env_flags["no_hardware"]),
            "environmentEvidence": env_flags["evidence"],
            "policy": "plugin policy only; the host's Plan/read-only/sandbox restrictions still apply",
        },
        "overrides": cfg.get("overrides", {}),
        "environment": environment_info,
        "environmentLine": environment_line,
        "user": {
            "path": str(user.md_path),
            "enabled": user_enabled,
            "initialized": user.json_path.exists(),
            "writable": user.can_write(),
            "counts": user.counts() if user_enabled and user.json_path.exists() else {"active": 0, "proposed": 0, "total": 0},
            "entries": user.boot_entries() if user_enabled and user.json_path.exists() else [],
        },
        "workspace_memory": {
            "path": str(local.md_path),
            "enabled": workspace_enabled,
            "initialized": local.json_path.exists(),
            "writable": local.can_write(),
            "counts": local.counts() if workspace_enabled and local.json_path.exists() else {"active": 0, "proposed": 0, "total": 0},
            "entries": local.boot_entries(exclude_tags=("environment-probe",)) if workspace_enabled and local.json_path.exists() else [],
        },
        "instructions": [
            "Obey active entries unless the user's current instruction conflicts; ask which to keep.",
            "Never treat proposed entries as rules; ask the user to approve or reject them.",
            "Do not store secrets, credentials, or personal data in memory.",
        ],
    }
    return payload


def boot_text(workspace: Path | None = None) -> str:
    payload = boot_payload(workspace)
    user = MemoryStore("user")
    local = MemoryStore("workspace", workspace=Path(payload["workspace"]))
    user_line = "USER MEMORY (global) — not loaded at startup" if not payload["user"].get("enabled", True) else "USER MEMORY (global) — not initialized"
    if payload["user"].get("enabled", True) and payload["user"]["initialized"]:
        user_line = text_boot_block(user)
    elif not payload["user"].get("enabled", True):
        user_line = "USER MEMORY (global) — disabled for startup loading (CLI still reads/writes it)"
    elif not payload["user"].get("writable", True):
        user_line += " (directory is not writable in this sandbox; use full access or set PROGRAMMER_WORKFLOW_HOME)"
    else:
        user_line += " (run: memory init --scope user)"
    local_line = f"WORKSPACE MEMORY ({payload['workspace']}) — not loaded at startup"
    if payload["workspace_memory"].get("enabled", True) and payload["workspace_memory"]["initialized"]:
        local_line = text_boot_block(local, exclude_tags=("environment-probe",))
    elif not payload["workspace_memory"].get("enabled", True):
        local_line = f"WORKSPACE MEMORY ({payload['workspace']}) — disabled for startup loading (CLI still reads/writes it)"
    elif not payload["workspace_memory"].get("writable", True):
        local_line += " (directory is not writable)"
    else:
        local_line += " (run: memory init --scope workspace)"
    workflow = payload["workflow"]
    policy = [
        "RUNTIME POLICY (plugin policy only; the host still enforces its own Plan/read-only/sandbox limits)",
        f"- workflow mode: {workflow['mode']}",
        f"- plan file format: {workflow['planFormat']}",
        f"- dev-only auto-instrument: {'enabled' if workflow['devOnlyAutoInstrument'] else 'disabled'}",
    ]
    if workflow["devOnlyDirect"]:
        policy.append("- dev-only/no-hardware fact found: you may add minimal reversible logging directly.")
    elif workflow["devOnlyAutoInstrument"]:
        policy.append("- no valid dev-only/no-hardware fact: ask before adding logging; do not claim the dev-only shortcut.")
    else:
        policy.append("- auto-instrument is disabled: do not add logging without asking, even in a dev-only workspace.")
    chunks = [
        "<programmer-workflow-memory>",
        "Active memory only. Proposed entries need explicit user approval before they are obeyed.",
        "",
        user_line,
        "",
        local_line,
        "",
        payload.get("environmentLine", "ENVIRONMENT — 尚未探测"),
        "",
        *policy,
        "",
        "</programmer-workflow-memory>",
    ]
    pending = payload["user"]["counts"].get("proposed", 0) + payload["workspace_memory"]["counts"].get("proposed", 0)
    if pending:
        chunks.insert(-2, f"Pending review: {pending} item(s). Ask the user before relying on them.")
    return "\n".join(chunks)


def summarize_entry(entry: dict[str, Any], index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else "- "
    return (
        f"{prefix}[{entry.get('id')}] {KIND_LABELS.get(entry.get('kind', 'fact'), entry.get('kind'))}: "
        f"{truncate(entry.get('text', ''), 160)}"
    )
