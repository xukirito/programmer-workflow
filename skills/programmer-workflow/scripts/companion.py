#!/usr/bin/env python3
"""Programmer Workflow CLI.

Run from any directory. The skill folder is resolved from this file's location,
so the same command works for every agent that can execute Python.

Examples:
    python companion.py boot --workspace .
    python companion.py memory propose --scope user --kind habit --text "..."
    python companion.py scan --workspace . --out .programmer-workflow/scan.json
    python companion.py run --label repro --yes -- python app.py
    python companion.py triage debug-logs/20261031-120000-repro/combined.log
    python companion.py docs --spec docs/spec.json --out docs
    python companion.py prototype --spec design.json --out Prototype.html
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib import debug as debuglib  # noqa: E402
from lib import hosts as hostslib  # noqa: E402
from lib import migration as migrationlib  # noqa: E402
from lib import plan as planlib  # noqa: E402
from lib import scan as scanlib  # noqa: E402
from lib import stall as stalllib  # noqa: E402
from lib.common import (  # noqa: E402
    SCHEMA_VERSION,
    SKILL_NAME,
    atomic_write_json,
    configure_stdout,
    docs_dir,
    emit,
    emit_json,
    ensure_dir,
    fail,
    global_root,
    line_count,
    load_plugin_config,
    now_iso,
    now_stamp,
    prototype_path,
    relative_posix,
    safe_workspace_relative,
    skill_root,
    templates_dir,
    user_home,
    warn,
    workspace_root,
    workspace_state,
    workspace_output_path,
)
from lib.memory import (  # noqa: E402
    AmbiguousIdError,
    KIND_LABELS,
    KINDS,
    MemoryDataError,
    MemoryStore,
    boot_payload,
    boot_text,
)
from lib.render import pages as pagelib  # noqa: E402
from lib.render import spec as speclib  # noqa: E402

VERSION = "0.1.0"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _ws(args: argparse.Namespace) -> Path:
    return (Path(args.workspace) if getattr(args, "workspace", None) else Path.cwd()).resolve()


def _root(args: argparse.Namespace) -> Path:
    if getattr(args, "workspace", None):
        return Path(args.workspace).expanduser().resolve()
    return workspace_root(Path.cwd())


def _path_arg(value: str, args: argparse.Namespace) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_ws(args) / path).resolve()


def _store(scope: str, args: argparse.Namespace) -> MemoryStore:
    return MemoryStore(scope, workspace=_root(args))


def _print(data: Any, as_json: bool) -> None:
    if as_json:
        emit_json(data)


def _scope_from_ids(ids: list[str], explicit: str | None, args: argparse.Namespace) -> MemoryStore:
    if explicit:
        return _store(explicit, args)
    prefixes = {value.split("-", 1)[0] for value in ids}
    if prefixes == {"u"}:
        return _store("user", args)
    if prefixes == {"w"}:
        return _store("workspace", args)
    raise ValueError("cannot infer memory scope from those ids; pass --scope user or --scope workspace")


def _open_path(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        warn(f"could not open {path}: {exc}")


def _memory_show(store: MemoryStore, status: str, as_json: bool) -> dict[str, Any]:
    entries = store.entries(status=None if status == "all" else status)
    data = {
        "scope": store.scope,
        "path": str(store.json_path),
        "markdown": str(store.md_path),
        "counts": store.counts(),
        "entries": entries,
    }
    if as_json:
        emit_json(data)
    else:
        emit(store.render_markdown())
        if not store.json_path.exists():
            emit("_记忆尚未初始化；运行 memory init 创建。_")
    return data


def _memory_review(scope: str, args: argparse.Namespace, as_json: bool) -> dict[str, Any]:
    stores = []
    if scope in ("user", "all"):
        stores.append(MemoryStore("user"))
    if scope in ("workspace", "all"):
        stores.append(MemoryStore("workspace", workspace=_root(args)))
    result: dict[str, Any] = {"scopes": []}
    for store in stores:
        proposed = store.entries(status="proposed")
        result["scopes"].append({
            "scope": store.scope,
            "path": str(store.md_path),
            "count": len(proposed),
            "entries": proposed,
        })
        if not as_json:
            emit(f"## {('用户记忆（全局）' if store.scope == 'user' else '工作区记忆')} — {len(proposed)} 条待审核")
            if not proposed:
                emit("_没有待审核条目。_")
            for index, entry in enumerate(proposed, 1):
                emit(f"{index}. `{entry['id']}` [{KIND_LABELS.get(entry.get('kind'), entry.get('kind'))}] {entry.get('text')}")
                if entry.get("evidence"):
                    emit(f"   证据：{'; '.join(str(x) for x in entry['evidence'][:3])}")
                emit(f"   置信度 {entry.get('confidence')} · 来源 {entry.get('source')}")
            emit("")
    if as_json:
        emit_json(result)
    return result


def _init_scope(scope: str, args: argparse.Namespace) -> None:
    if scope == "all":
        for item in ("user", "workspace"):
            store = _store(item, args)
            store.ensure()
            emit(f"initialized {item}: {store.md_path}")
        return
    store = _store(scope, args)
    store.ensure()
    emit(f"initialized {store.scope}: {store.md_path}")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_boot(args: argparse.Namespace) -> int:
    if args.json:
        emit_json(boot_payload(_root(args)))
    else:
        emit(boot_text(_root(args)))
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    action = args.memory_action
    if action == "init":
        _init_scope(args.scope, args)
        return 0
    if action == "show":
        if args.scope == "all":
            for scope in ("user", "workspace"):
                _memory_show(_store(scope, args), args.status, args.json)
        else:
            _memory_show(_store(args.scope, args), args.status, args.json)
        return 0
    if action == "propose" or action == "add":
        store = _store(args.scope, args)
        store.ensure()
        entry, created = store.add(
            kind=args.kind,
            text=args.text,
            detail=args.detail or "",
            evidence=args.evidence or [],
            confidence=args.confidence,
            source=args.source,
            status="proposed" if action == "propose" else "active",
            tags=args.tags or [],
            dedupe=not args.force,
        )
        payload = {
            "scope": store.scope,
            "created": created,
            "status": entry.get("status"),
            "entry": entry,
            "markdown": str(store.md_path),
        }
        if args.json:
            emit_json(payload)
        else:
            verb = "新增" if created else "已存在"
            emit(f"{verb} {store.scope} 记忆：`{entry['id']}` [{KIND_LABELS.get(entry.get('kind'), entry.get('kind'))}] {entry.get('text')}")
            emit(f"状态：{entry.get('status')} · 文件：{store.md_path}")
            if action == "propose":
                emit("提醒：待审核条目不会生效，必须请用户 accept/reject。")
        return 0
    if action == "review":
        _memory_review(args.scope, args, args.json)
        return 0
    if action in ("accept", "reject"):
        status = "active" if action == "accept" else "rejected"
        store = _scope_from_ids(args.ids, args.scope, args)
        updated = store.set_status(args.ids, status)
        payload = {"scope": store.scope, "status": status, "updated": updated}
        if args.json:
            emit_json(payload)
        else:
            emit(f"{store.scope}: {len(updated)} 条 → {status}")
            for entry in updated:
                emit(f"- `{entry['id']}` {entry.get('text')}")
        return 0
    if action == "forget":
        store = _scope_from_ids(args.ids, args.scope, args)
        removed = store.delete(args.ids)
        payload = {"scope": store.scope, "removed": removed}
        if args.json:
            emit_json(payload)
        else:
            emit(f"{store.scope}: 已删除 {len(removed)} 条记忆")
        return 0
    if action == "edit":
        store = _store(args.scope, args)
        entry = store.edit(
            args.id,
            text=args.text,
            detail=args.detail,
            kind=args.kind,
            confidence=args.confidence,
            tags=args.tags,
            evidence=args.evidence,
        )
        payload = {"scope": store.scope, "entry": entry}
        if args.json:
            emit_json(payload)
        else:
            emit(f"已更新 `{entry['id']}`：{entry.get('text')}")
        return 0
    if action == "promote":
        source = MemoryStore("workspace", workspace=_root(args))
        target = MemoryStore("user")
        target.ensure()
        copied = source.promote(args.ids, target)
        payload = {"from": source.scope, "to": target.scope, "copied": copied}
        if args.json:
            emit_json(payload)
        else:
            emit(f"已复制 {len(copied)} 条到用户记忆，状态为待审核：")
            for entry in copied:
                emit(f"- `{entry['id']}` {entry.get('text')}")
            emit("请让用户审核后再生效。")
        return 0
    if action == "render":
        for scope in (("user", "workspace") if args.scope == "all" else (args.scope,)):
            store = _store(scope, args)
            store.ensure()
            emit(f"rendered {store.md_path}")
        return 0
    if action == "status":
        result = {}
        for scope in ("user", "workspace"):
            store = _store(scope, args)
            result[scope] = {
                "path": str(store.json_path),
                "initialized": store.json_path.exists(),
                "counts": store.counts(),
            }
        if args.json:
            emit_json(result)
        else:
            for scope, info in result.items():
                emit(f"{scope}: {info['counts']} · {info['path']} · {'ok' if info['initialized'] else 'not initialized'}")
        return 0
    raise ValueError(f"unknown memory action: {action}")


def cmd_scan(args: argparse.Namespace) -> int:
    root = _root(args)
    result = scanlib.scan_project(
        root,
        include_transcripts=args.include_transcripts,
        extract_user_text=args.extract_user_text,
        home=Path.home(),
    )
    out = workspace_output_path(root, args.out, str(workspace_state(root).relative_to(root) / "scan.json")) if args.out else workspace_state(root) / "scan.json"
    ensure_dir(out.parent)
    atomic_write_json(out, result)
    if args.json:
        emit_json({**result, "out": str(out)})
    else:
        style = result["style"]
        emit(f"scan 完成：{out}")
        emit(f"- 语言：{', '.join(f'{k}({v})' for k, v in result['project']['languages'].items()) or '未知'}")
        emit(f"- 缩进：{style['indentation']['dominant']} · 换行：{style['line_endings']['dominant']} · 命名：{style['file_naming']['dominant']} · 注释：{style['comments']['dominant_language']}")
        emit(f"- 文件：{result['project']['files']['total']} · 测试：{result['tests']['test_files']} · 硬件线索：{'有' if result['hardware']['likely_hardware'] else '无'}")
        emit(f"- 对话记录：{'已扫描元数据' if result['transcripts'].get('enabled') else '未读取'}")
        emit("下一步：由 Agent 汇总成候选习惯，用 memory propose 写入，再请用户逐条审核。")
    if args.extract_user_text:
        warn("已提取用户发言到本地文件，可能包含敏感信息；分享前请审阅。")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    root = _root(args)
    result = scanlib.project_map(root)
    out = workspace_output_path(root, args.out, str(workspace_state(root).relative_to(root) / "project-map.json")) if args.out else workspace_state(root) / "project-map.json"
    ensure_dir(out.parent)
    atomic_write_json(out, result)
    if args.json:
        emit_json({**result, "out": str(out)})
    else:
        emit(f"project map：{out}")
        emit(f"- 文件 {result['files']['total']} · {result['files']['human_bytes']} · 截断：{result['files']['truncated']}")
        emit(f"- 语言：{', '.join(f'{k}({v})' for k, v in result['languages'].items()) or '未知'}")
        emit(f"- 模块候选：{', '.join(m['name'] for m in result['modules'][:10])}")
        emit(f"- 入口候选：{', '.join(e['path'] for e in result['entry_candidates'][:8])}")
        emit(f"- 框架：{', '.join(result['signals']['frameworks']) or '未识别'}")
        emit(f"- 硬件线索：{'有' if result['hardware']['likely_hardware'] else '无'}")
    return 0


def cmd_env(args: argparse.Namespace) -> int:
    root = _root(args)
    if args.env_action == "show":
        facts = scanlib.env_facts(root)
        store = MemoryStore("workspace", workspace=root)
        env_entries = [e for e in store.entries(status="active") if e.get("kind") == "environment"]
        payload = {"facts": facts, "memory": env_entries}
        if args.json:
            emit_json(payload)
        else:
            emit(f"工作区：{root}")
            emit(f"硬件线索：{'有' if facts['hardware']['likely_hardware'] else '无'}")
            for hit in facts["hardware"]["hits"][:10]:
                emit(f"- {hit['path']} — {hit['reason']}")
            emit("")
            emit("已记录的环境事实：")
            if not env_entries:
                emit("_暂无。用户明确说明纯开发/无硬件后，运行 env set --dev-only --no-hardware。_")
            for entry in env_entries:
                emit(f"- `{entry['id']}` {entry.get('text')}")
        return 0
    if args.env_action == "hints":
        facts = scanlib.env_facts(root)
        if args.json:
            emit_json(facts)
        else:
            emit(f"硬件线索：{'有' if facts['hardware']['likely_hardware'] else '无'}")
            for hit in facts["hardware"]["hits"][:15]:
                emit(f"- {hit['path']} — {hit['reason']}")
            emit("注意：工程里有嵌入式/硬件文件，不代表当前机器连接了硬件，必须问用户。")
        return 0
    if args.env_action == "set":
        if not (args.dev_only or args.no_hardware):
            raise ValueError("env set needs --dev-only and/or --no-hardware")
        store = MemoryStore("workspace", workspace=root)
        store.ensure()
        parts = []
        if args.dev_only:
            parts.append("该工作区是纯开发环境，不是部署环境")
        if args.no_hardware:
            parts.append("没有可搭配的物理硬件")
        text = "；".join(parts) + "。"
        text += "调试代码时直接加入可回滚的排查日志并说明定位步骤，不要等待硬件或部署环境；如仍需实机验证，明确提示用户操作。"
        if args.reason:
            text += f"（用户说明：{args.reason}）"
        entry, created = store.add(
            kind="environment",
            text=text,
            detail="由 env set 自动写入；后续会话必须遵守。",
            evidence=[f"workspace={root}", f"recorded_at={now_iso()}"],
            confidence=1.0,
            source="user",
            status="active",
            tags=["dev-only", "no-hardware"] if args.no_hardware else ["dev-only"],
            dedupe=False,
        )
        payload = {"workspace": str(root), "created": created, "entry": entry}
        if args.json:
            emit_json(payload)
        else:
            emit(f"已写入工作区记忆：`{entry['id']}`")
            emit(entry["text"])
            emit("后续调试不再询问是否加日志，直接加最小可回滚日志并给出定位命令。")
        return 0
    raise ValueError(f"unknown env action: {args.env_action}")


def cmd_stall(args: argparse.Namespace) -> int:
    if args.stall_action == "bump":
        result = stalllib.bump(args.track, note=args.note or "", session=args.session, workspace=_root(args))
    elif args.stall_action == "status":
        result = stalllib.status(args.track, session=args.session, workspace=_root(args))
    elif args.stall_action == "reset":
        result = stalllib.reset(session=args.session, workspace=_root(args), track=args.track)
    else:
        raise ValueError(f"unknown stall action: {args.stall_action}")
    if args.json:
        emit_json(result)
    else:
        emit(f"{result['track']}: {result['current']}/{result['threshold']} · triggered={str(result['triggered']).lower()}")
        if result["triggered"]:
            emit("已到触发阈值：按协议暂停继续试错，向用户提出行业做法/调试方案供选择。")
        if result.get("state_path"):
            emit(f"state: {result['state_path']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.yes and args.full_authority:
        return fail("--yes and --full-authority are mutually exclusive; pass only one")
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("run needs a command after --")
    result = debuglib.run_command(
        _root(args),
        command,
        label=args.label,
        timeout=args.timeout,
        shell=args.shell,
        assume_yes=args.yes,
        full_authority=args.full_authority,
        allow_destructive=args.allow_destructive,
    )
    if args.json:
        emit_json(result)
    else:
        emit(f"exit={result['exit_code']} duration={result['duration_seconds']}s timed_out={result['timed_out']}")
        emit(f"log: {result['log']}")
        if result["tail"]:
            emit("--- tail ---")
            emit("\n".join(result["tail"]))
        emit(f"下一步：python companion.py triage \"{result['log']}\"")
    if args.propagate_exit and result.get("exit_code") is not None:
        return int(result["exit_code"])
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = (_ws(args) / log_path).resolve()
    report = debuglib.triage_log(log_path)
    out = debuglib.write_triage(log_path, report)
    if args.json:
        emit_json({**report, "report": str(out)})
    else:
        emit(f"分诊完成：{out}")
        emit(f"- 行数 {report['lines']} · 错误签名 {report['signature_count']} 类 · DBG 标记 {report['markers']['count']} 条")
        for index, sig in enumerate(report["signatures"][:5], 1):
            emit(f"{index}. [{sig['level']}] ×{sig['count']} L{sig['first_line']}: {sig['sample'][:160]}")
        emit("假设：")
        for hyp in report["hypotheses"][:4]:
            emit(f"- {hyp['title']}（{hyp['confidence']}）：{hyp['next_step']}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    root = _root(args)
    cfg = load_plugin_config(root)
    fmt = (args.format or cfg.get("planFormat", "md")).lower()
    if fmt not in ("md", "html"):
        return fail("plan format must be md or html")
    spec_path = _path_arg(args.spec, args)
    try:
        plan = planlib.load_plan_spec(spec_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return fail(f"cannot read plan spec: {error}")
    if args.check:
        payload = {"ok": True, "title": plan["title"], "steps": len(plan["steps"]), "format": fmt}
        if args.json:
            emit_json(payload)
        else:
            emit(f"plan 校验通过：{plan['title']}（{len(plan['steps'])} 步，{fmt}）")
        return 0
    default_name = "plan.html" if fmt == "html" else "plan.md"
    out = workspace_output_path(root, args.out, default_name)
    planlib.write_plan(plan, out, fmt)
    payload = {
        "ok": True,
        "file": str(out),
        "format": fmt,
        "title": plan["title"],
        "steps": len(plan["steps"]),
        "approval": "回复“执行”后开始；修改请回复“修改：...”；取消请回复“取消”。",
    }
    if args.json:
        emit_json(payload)
    else:
        emit(f"已生成计划：{out}")
        emit("这是待审核计划，不会自动执行。回复“执行”后才开始操作。")
    return 0


def _load_docs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    if args.spec:
        return speclib.load_docs_specs(_path_arg(args.spec, args))
    if not args.architecture or not args.features:
        raise ValueError("pass --spec combined.json, or both --architecture and --features")
    arch_raw = speclib.load_json(_path_arg(args.architecture, args))
    feat_raw = speclib.load_json(_path_arg(args.features, args))
    return (
        speclib.attach_hash(speclib.normalize_architecture(arch_raw)),
        speclib.attach_hash(speclib.normalize_features(feat_raw)),
    )


def _enrich_docs(arch: dict[str, Any], features: dict[str, Any], root: Path) -> None:
    """Fill line counts and apply the settings-page default language."""
    total_lines = 0
    existing = 0
    lang = load_plugin_config(root).get("language")
    for data in (arch, features):
        if lang and data.get("project", {}).get("language") in ("", "zh-CN"):
            data["project"]["language"] = lang
    for item in arch.get("file_index", []):
        path = (root / item.get("path", "")).resolve()
        if path.is_file():
            lines = line_count(path)
            item["lines"] = lines
            total_lines += lines
            existing += 1
    if total_lines:
        arch["stats"]["loc"] = total_lines
    if not arch["stats"].get("files"):
        arch["stats"]["files"] = existing
    feature_count = len(features.get("features", []))
    if feature_count:
        features["stats"]["features"] = feature_count
        features["stats"]["implemented"] = sum(1 for f in features["features"] if f.get("status") == "implemented")
        features["stats"]["partial"] = sum(1 for f in features["features"] if f.get("status") == "partial")
        features["stats"]["planned"] = sum(1 for f in features["features"] if f.get("status") == "planned")


def cmd_docs(args: argparse.Namespace) -> int:
    root = _root(args)
    cfg = load_plugin_config(root)
    if not cfg.get("docsEnabled", True):
        return fail("docs generation is disabled in the Programmer Workflow settings page")
    arch, features = _load_docs(args)
    _enrich_docs(arch, features, root)
    out_dir = workspace_output_path(root, args.out, "docs") if args.out else docs_dir(root)
    if args.check:
        payload = {
            "ok": True,
            "architecture": {"modules": len(arch["modules"]), "flows": len(arch["flows"]), "hash": arch["spec_hash"]},
            "features": {"features": len(features["features"]), "domains": len(features["domains"]), "hash": features["spec_hash"]},
            "out": str(out_dir),
        }
        if args.json:
            emit_json(payload)
        else:
            emit(f"spec 校验通过：{len(arch['modules'])} 个模块，{len(features['features'])} 个功能")
            emit(f"将输出到：{out_dir}")
        return 0
    paths = pagelib.render_docs(arch, features, out_dir, template_dir=templates_dir(), version=VERSION)
    payload = {
        "ok": True,
        "files": [pagelib.describe_output(path) for path in paths],
        "open_hint": "用浏览器打开这两个文件；页面里可以搜索、筛选、查看依赖图，并在底部提交评审意见。",
    }
    if args.json:
        emit_json(payload)
    else:
        for path in paths:
            emit(f"已生成：{path}")
        emit("用浏览器打开（双击或拖进浏览器）即可查看；页面底部可提交评审并导出 review JSON。")
    if args.open:
        for path in paths:
            _open_path(path)
    return 0


def cmd_prototype(args: argparse.Namespace) -> int:
    root = _root(args)
    cfg = load_plugin_config(root)
    if not cfg.get("prototypeEnabled", True):
        return fail("prototype generation is disabled in the Programmer Workflow settings page")
    raw = speclib.load_json(_path_arg(args.spec, args))
    spec = speclib.attach_hash(speclib.normalize_prototype(raw))
    out = workspace_output_path(root, args.out, "Prototype.html") if args.out else prototype_path(root)
    if args.check:
        payload = {
            "ok": True,
            "directions": len(spec["directions"]),
            "screens": sum(len(d["screens"]) for d in spec["directions"]),
            "hash": spec["spec_hash"],
            "out": str(out),
        }
        if args.json:
            emit_json(payload)
        else:
            emit(f"spec 校验通过：{payload['directions']} 个方向，{payload['screens']} 个界面")
            emit(f"将输出：{out}")
        return 0
    pagelib.render_prototype(spec, out, template_dir=templates_dir(), version=VERSION)
    payload = {
        "ok": True,
        "file": pagelib.describe_output(out),
        "open_hint": "用浏览器打开 Prototype.html；可切换方向/视口、在画布上标注，并导出评审 JSON。",
    }
    if args.json:
        emit_json(payload)
    else:
        emit(f"已生成：{out}")
        emit("用浏览器打开即可；切换方向、视口，在画布上点击可加标注，底部可提交评审。")
    if args.open:
        _open_path(out)
    return 0


def cmd_migrate_plugin(args: argparse.Namespace) -> int:
    action = args.migration_action
    host = args.host or ""
    try:
        if action == "status":
            payload = {
                "plugin": migrationlib.read_state(host),
                "stage1": migrationlib.stage1_summary(host),
                "stage2": migrationlib.stage2_summary(host),
                "pluginData": migrationlib.inventory(user_home()),
                "coverage": {
                    "pluginRoot": str(global_root()),
                    "memoryRoot": str(user_home()),
                    "externalOverride": bool(os.environ.get("PROGRAMMER_WORKFLOW_GLOBAL") or os.environ.get("PROGRAMMER_WORKFLOW_HOME")),
                    "workspaceMemoryMigrates": False,
                },
                "legacy": migrationlib.legacy_status(host),
                "runtime": migrationlib.runtime_status(host),
                "statePath": str(migrationlib.state_path(host)),
            }
        elif action == "preflight":
            if not args.target_root:
                return fail("preflight requires --target-root")
            payload = migrationlib.preflight(host, args.target_root)
        elif action == "prepare":
            if not args.target_root:
                return fail("prepare requires --target-root")
            payload = migrationlib.prepare(host, args.target_root)
        elif action == "apply":
            if not args.target_root:
                return fail("apply requires the same --target-root used for preflight")
            payload = migrationlib.apply(host, args.target_root, assume_yes=args.yes)
        elif action == "rollback":
            payload = migrationlib.rollback(host)
        elif action == "legacy-import":
            payload = migrationlib.legacy_import(host, source=args.source, apply_now=args.apply)
        elif action == "runtime":
            payload = migrationlib.runtime_status(host)
        else:
            return fail(f"unknown migration action: {action}")
    except migrationlib.MigrationError as exc:
        if args.json:
            emit_json({"ok": False, "host": host, "error": str(exc)})
        else:
            emit(f"[error] {exc}", file=sys.stderr)
        return 2
    if args.json:
        emit_json(payload)
    else:
        emit(f"{action}: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    return 0 if payload.get("ok", True) else 2


def cmd_doctor(args: argparse.Namespace) -> int:
    home = user_home()
    skill = skill_root()
    checks = []
    checks.append({"name": "python", "ok": sys.version_info >= (3, 8), "detail": sys.version.split()[0]})
    checks.append({"name": "skill_dir", "ok": (skill / "SKILL.md").exists(), "detail": str(skill)})
    for name in ("base.css", "docs.css", "prototype.css", "docs.js", "prototype.js", "review.js", "docs.html", "prototype.html"):
        checks.append({"name": f"template:{name}", "ok": (templates_dir() / name).exists(), "detail": str(templates_dir() / name)})
    user_store = MemoryStore("user")
    checks.append({"name": "user_memory", "ok": True, "detail": f"{user_store.md_path} ({'initialized' if user_store.json_path.exists() else 'not initialized'})"})
    ws = _root(args)
    cfg = load_plugin_config(ws)
    checks.append({"name": "config", "ok": True, "detail": f"{global_root() / 'config.json'} · workflowMode={cfg['workflowMode']} · workspaceDataDir={cfg['workspaceDataDir']}"})
    checks.append({"name": "global_data", "ok": True, "detail": f"{cfg.get('host')} → {global_root()}"})
    checks.append({"name": "host_home", "ok": True, "detail": str(cfg.get("hostHome", ""))})
    local_store = MemoryStore("workspace", workspace=ws)
    checks.append({"name": "workspace_memory", "ok": True, "detail": f"{local_store.md_path} ({'initialized' if local_store.json_path.exists() else 'not initialized'})"})
    install_paths = {"project": ws / ".agents" / "skills" / SKILL_NAME / "SKILL.md"}
    for host_id in hostslib.HOSTS:
        install_paths[host_id] = hostslib.host_home(host_id) / "skills" / SKILL_NAME / "SKILL.md"
    install_paths["agents"] = Path.home() / ".agents" / "skills" / SKILL_NAME / "SKILL.md"
    # CodeBuddy installs project-level by default; keep it visible without
    # pretending the user-level host home is the only location.
    install_paths["codebuddy"] = ws / ".codebuddy" / "skills" / SKILL_NAME / "SKILL.md"
    installed = {key: value.exists() for key, value in install_paths.items()}
    checks.append({"name": "installed", "ok": any(installed.values()), "detail": installed})
    capability = {host_id: hostslib.plugin_migration_capability(host_id) for host_id in hostslib.HOSTS}
    checks.append({
        "name": "stage1_cli",
        "ok": any(item["ready"] for item in capability.values()),
        "detail": {
            host_id: (item["cliPath"] or item["reason"])
            for host_id, item in capability.items()
        },
    })
    ok = all(item["ok"] for item in checks if item["name"] != "installed")
    payload = {
        "ok": ok,
        "version": VERSION,
        "skill": str(skill),
        "python": sys.executable,
        "platform": platform.platform(),
        "workspace": str(ws),
        "user_home": str(home),
        "global_root": str(global_root()),
        "config": cfg,
        "checks": checks,
        "installed": installed,
        "hosts": hostslib.all_hosts(),
        "stage1Cli": capability,
    }
    if args.json:
        emit_json(payload)
    else:
        emit(f"Programmer Workflow {VERSION} · {'OK' if ok else 'NEEDS ATTENTION'}")
        emit(f"skill: {skill}")
        emit(f"workspace: {ws}")
        for item in checks:
            emit(f"[{'ok' if item['ok'] else '!!'}] {item['name']}: {item['detail']}")
        emit(f"installed: {', '.join(k for k, v in installed.items() if v) or 'none detected'}")
    return 0 if ok else 1


def cmd_version(args: argparse.Namespace) -> int:
    if args.json:
        emit_json({"name": SKILL_NAME, "version": VERSION, "skill": str(skill_root())})
    else:
        emit(f"{SKILL_NAME} {VERSION}")
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def add_workspace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--workspace", help="workspace directory (default: nearest .git/.programmer-workflow or cwd)")
    parser.add_argument(
        "--host",
        choices=["dsh", "kimi", "codebuddy", "claude", "cursor", "codex", "generic"],
        help="host whose independent plugin-data root is used (or set PROGRAMMER_WORKFLOW_HOST)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="programmer-workflow",
        description="Memory, stall escalation, instrumented debugging, architecture docs and UI prototypes for coding agents.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("boot", help="print active memory for session start")
    add_workspace(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_boot)

    p = sub.add_parser("memory", help="read/write user and workspace memory")
    mem_sub = p.add_subparsers(dest="memory_action", required=True)
    for name in ("init",):
        q = mem_sub.add_parser(name, help="create memory files")
        add_workspace(q)
        q.add_argument("--scope", choices=["user", "workspace", "all"], default="all")
        q.set_defaults(func=cmd_memory)
    q = mem_sub.add_parser("show", help="show memory")
    add_workspace(q)
    q.add_argument("--scope", choices=["user", "workspace", "all"], default="all")
    q.add_argument("--status", choices=["active", "proposed", "rejected", "all"], default="all")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_memory)
    for name, status in (("propose", "proposed"), ("add", "active")):
        q = mem_sub.add_parser(name, help=f"add a {status} entry")
        add_workspace(q)
        q.add_argument("--scope", choices=["user", "workspace"], required=True)
        q.add_argument("--kind", choices=list(KINDS), required=True)
        q.add_argument("--text", required=True)
        q.add_argument("--detail", default="")
        q.add_argument("--evidence", action="append", default=[])
        q.add_argument("--confidence", type=float, default=0.7)
        q.add_argument("--source", choices=["user", "conversation", "files", "system", "promotion"], default="conversation")
        q.add_argument("--tags", action="append", default=[])
        q.add_argument("--force", action="store_true", help="skip duplicate detection")
        q.add_argument("--json", action="store_true")
        q.set_defaults(func=cmd_memory)
    q = mem_sub.add_parser("review", help="list proposed entries")
    add_workspace(q)
    q.add_argument("--scope", choices=["user", "workspace", "all"], default="all")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_memory)
    for name in ("accept", "reject", "forget"):
        q = mem_sub.add_parser(name, help=f"{name} entries by id prefix")
        add_workspace(q)
        q.add_argument("--scope", choices=["user", "workspace"])
        q.add_argument("ids", nargs="+")
        q.add_argument("--json", action="store_true")
        q.set_defaults(func=cmd_memory)
    q = mem_sub.add_parser("edit", help="edit one entry")
    add_workspace(q)
    q.add_argument("--scope", choices=["user", "workspace"], required=True)
    q.add_argument("id")
    q.add_argument("--text")
    q.add_argument("--detail")
    q.add_argument("--kind", choices=list(KINDS))
    q.add_argument("--confidence", type=float)
    q.add_argument("--tags", action="append")
    q.add_argument("--evidence", action="append")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_memory)
    q = mem_sub.add_parser("promote", help="copy workspace entries to user memory as proposals")
    add_workspace(q)
    q.add_argument("ids", nargs="+")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_memory)
    q = mem_sub.add_parser("render", help="regenerate MEMORY.md")
    add_workspace(q)
    q.add_argument("--scope", choices=["user", "workspace", "all"], default="all")
    q.set_defaults(func=cmd_memory)
    q = mem_sub.add_parser("status", help="show counts and paths")
    add_workspace(q)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_memory)

    p = sub.add_parser("scan", help="collect habit evidence (does not write memory)")
    add_workspace(p)
    p.add_argument("--out")
    p.add_argument("--include-transcripts", action="store_true", help="list conversation logs metadata only (opt-in)")
    p.add_argument("--extract-user-text", action="store_true", help="extract user messages locally (sensitive, opt-in)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("map", help="build a bounded project map for docs/debugging")
    add_workspace(p)
    p.add_argument("--out")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_map)

    p = sub.add_parser("env", help="inspect or record workspace environment facts")
    env_sub = p.add_subparsers(dest="env_action", required=True)
    q = env_sub.add_parser("show")
    add_workspace(q)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_env)
    q = env_sub.add_parser("hints")
    add_workspace(q)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_env)
    q = env_sub.add_parser("set", help="record dev-only/no-hardware in workspace memory")
    add_workspace(q)
    q.add_argument("--dev-only", action="store_true")
    q.add_argument("--no-hardware", action="store_true")
    q.add_argument("--reason", default="")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_env)

    p = sub.add_parser("stall", help="track repeated failed rounds")
    stall_sub = p.add_subparsers(dest="stall_action", required=True)
    for name in ("bump", "status", "reset"):
        q = stall_sub.add_parser(name)
        add_workspace(q)
        q.add_argument("--track", choices=["satisfaction", "bugfix"], default="satisfaction")
        q.add_argument("--session")
        q.add_argument("--note", default="")
        q.add_argument("--json", action="store_true")
        q.set_defaults(func=cmd_stall)

    p = sub.add_parser("run", help="run a command with consent, timeout and log capture")
    add_workspace(p)
    p.add_argument("--label", default="run")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--yes", action="store_true", help="confirm the user approved this run")
    p.add_argument("--full-authority", action="store_true", help="host is in Full authority; skip plan-mode consent")
    p.add_argument("--allow-destructive", action="store_true")
    p.add_argument("--shell", action="store_true")
    p.add_argument("--propagate-exit", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("plan", help="render plan.md or plan.html for user review")
    add_workspace(p)
    p.add_argument("--spec", required=True, help="plan spec JSON")
    p.add_argument("--format", choices=["md", "html"], help="default from settings planFormat")
    p.add_argument("--out", default="", help="workspace-relative output, default plan.md/plan.html")
    p.add_argument("--check", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("triage", help="summarize a captured log")
    add_workspace(p)
    p.add_argument("log")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_triage)

    p = sub.add_parser("docs", help="render Architecture.html and Features.html")
    add_workspace(p)
    p.add_argument("--spec", help="combined spec with architecture + features")
    p.add_argument("--architecture", help="architecture-only spec")
    p.add_argument("--features", help="features-only spec")
    p.add_argument("--out", default="")
    p.add_argument("--check", action="store_true")
    p.add_argument("--open", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_docs)

    p = sub.add_parser("prototype", help="render Prototype.html")
    add_workspace(p)
    p.add_argument("--spec", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--check", action="store_true")
    p.add_argument("--open", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_prototype)

    p = sub.add_parser("migrate-plugin", help="two-stage, host-scoped plugin/runtime data migration")
    mp = p.add_subparsers(dest="migration_action", required=True)
    for name in ("status", "preflight", "prepare", "apply", "rollback", "legacy-import", "runtime"):
        q = mp.add_parser(name)
        q.add_argument("--host", required=True, choices=["dsh", "kimi", "codebuddy", "claude", "cursor", "codex", "generic"])
        q.add_argument("--target-root")
        q.add_argument("--source")
        q.add_argument("--yes", action="store_true", help="confirm stage 1 after user approval")
        q.add_argument("--apply", action="store_true", help="apply a legacy import instead of previewing it")
        q.add_argument("--json", action="store_true")
        q.set_defaults(func=cmd_migrate_plugin)

    p = sub.add_parser("doctor", help="check installation and templates")
    add_workspace(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("version", help="print version")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        selected_host = getattr(args, "host", None)
        if selected_host:
            os.environ["PROGRAMMER_WORKFLOW_HOST"] = selected_host
        # Resolve before dispatch so every command fails with one actionable host error.
        if hasattr(args, "func") and args.func is not cmd_version:
            from lib.hosts import resolve_host
            os.environ["PROGRAMMER_WORKFLOW_HOST"] = resolve_host()
        return int(args.func(args))
    except (speclib.SpecError, MemoryDataError, AmbiguousIdError, migrationlib.MigrationError) as exc:
        return fail(str(exc))
    except (ValueError, KeyError, FileNotFoundError, TimeoutError) as exc:
        return fail(str(exc))
    except PermissionError as exc:
        return fail(str(exc))
    except OSError as exc:
        return fail(str(exc))
    except debuglib.ConsentRequiredError as exc:
        return fail(str(exc))
    except debuglib.DestructiveCommandError as exc:
        return fail(str(exc))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
