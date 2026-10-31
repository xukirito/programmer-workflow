"""Render an execution plan as Markdown or a standalone HTML review page.

The plan is deliberately a **review artifact**, not an approval token. A plan in
`plan.md` / `plan.html` is shown to the user; only an explicit chat approval
starts execution. This keeps the same file usable by CodeBuddy, Kimi Code and DSH.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from .common import atomic_write_text

MAX_STEPS = 24
RISK_VALUES = ("low", "medium", "high")
RISK_LABELS = {"low": "低", "medium": "中", "high": "高"}


def _text(value: Any, limit: int = 8_000) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "\n".join(_text(item, limit) for item in value if item is not None)
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def _list(value: Any, limit: int = 40) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = [value]
    result: list[str] = []
    for item in items:
        text = _text(item, 2_000)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_plan(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("plan spec must be a JSON object")
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError("plan spec needs a non-empty steps array")
    steps: list[dict[str, str]] = []
    for index, raw in enumerate(steps_raw[:MAX_STEPS], 1):
        if isinstance(raw, str):
            raw = {"title": raw}
        if not isinstance(raw, dict):
            raise ValueError(f"step {index} must be an object or string")
        command = raw.get("command")
        if isinstance(command, (list, tuple)):
            command = " ".join(_text(item, 1_000) for item in command)
        risk = _text(raw.get("risk"), 16).lower() or "low"
        if risk not in RISK_VALUES:
            risk = "low"
        steps.append({
            "title": _text(raw.get("title"), 300) or f"步骤 {index}",
            "change": _text(raw.get("change"), 4_000),
            "command": _text(command, 4_000),
            "why": _text(raw.get("why"), 2_000),
            "risk": risk,
            "verify": _text(raw.get("verify"), 2_000),
        })
    return {
        "title": _text(data.get("title"), 300) or "执行计划",
        "goal": _text(data.get("goal"), 4_000),
        "context": _text(data.get("context"), 4_000),
        "mode": _text(data.get("mode"), 80) or "Plan mode / 待审核",
        "assumptions": _list(data.get("assumptions")),
        "steps": steps,
        "verification": _list(data.get("verification")),
        "rollback": _text(data.get("rollback"), 4_000),
        "questions": _list(data.get("questions")),
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# {plan['title']}",
        "",
        f"> 状态：{plan['mode']}",
        "> 这只是执行计划，不会自动执行。回复 `执行` 后才开始；回复 `修改：...` 或 `取消` 停止。",
        "",
    ]
    if plan.get("goal"):
        lines += ["## 目标", "", plan["goal"], ""]
    if plan.get("context"):
        lines += ["## 背景与假设", "", plan["context"], ""]
    if plan.get("assumptions"):
        lines += ["## 假设", ""]
        lines += [f"- {item}" for item in plan["assumptions"]]
        lines.append("")
    lines += ["## 执行步骤", ""]
    for index, step in enumerate(plan["steps"], 1):
        lines.append(f"### {index}. {step['title']}")
        lines.append("")
        if step.get("change"):
            lines.append(f"- **变更**：{step['change']}")
        if step.get("command"):
            command = step["command"]
            if "\n" in command:
                lines += ["- **命令**：", "", "  ```bash", *[f"  {line}" for line in command.splitlines()], "  ```", ""]
            else:
                lines.append(f"- **命令**：`{command}`")
        if step.get("why"):
            lines.append(f"- **原因**：{step['why']}")
        lines.append(f"- **风险**：{RISK_LABELS[step['risk']]}")
        if step.get("verify"):
            lines.append(f"- **验证**：{step['verify']}")
        lines += ["", f"- [ ] 已验证步骤 {index}", ""]
    if plan.get("verification"):
        lines += ["## 整体验证", ""]
        lines += [f"- [ ] {item}" for item in plan["verification"]]
        lines.append("")
    if plan.get("rollback"):
        lines += ["## 回滚", "", plan["rollback"], ""]
    if plan.get("questions"):
        lines += ["## 需要你确认", ""]
        lines += [f"- {item}" for item in plan["questions"]]
        lines.append("")
    lines += [
        "## 审核",
        "",
        "- [ ] 我批准执行",
        "- [ ] 需要修改（请在对话里说明）",
        "- [ ] 取消",
        "",
        "回复：`执行` / `修改：...` / `取消`",
        "",
    ]
    return "\n".join(lines)


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _render_list(items: list[str], empty: str = "无") -> str:
    if not items:
        return f'<p class="empty">{_e(empty)}</p>'
    return "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul>"


def render_html(plan: dict[str, Any]) -> str:
    plan_key = hashlib.sha256(
        json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    steps = []
    for index, step in enumerate(plan["steps"], 1):
        command = step.get("command", "")
        command_html = f'<pre><code>{_e(command)}</code></pre>' if command else '<p class="empty">无命令，仅编辑文件</p>'
        steps.append(
            f'''<article class="step" data-step="{index}">
  <div class="step-head">
    <label class="check"><input type="checkbox" data-check="{index}" aria-label="标记步骤 {index} 已验证"></label>
    <div><span class="index">{index:02d}</span><h3>{_e(step["title"])}</h3></div>
    <span class="risk {step["risk"]}">风险 {RISK_LABELS[step["risk"]]}</span>
  </div>
  <dl class="meta">
    {f'<div><dt>变更</dt><dd>{_e(step["change"])}</dd></div>' if step.get("change") else ""}
    {f'<div><dt>原因</dt><dd>{_e(step["why"])}</dd></div>' if step.get("why") else ""}
    {f'<div><dt>验证</dt><dd>{_e(step["verify"])}</dd></div>' if step.get("verify") else ""}
  </dl>
  <div class="command">
    <div class="command-head"><span>命令</span><button type="button" class="copy" data-copy="{_e(command)}">复制</button></div>
    {command_html}
  </div>
</article>'''
        )
    assumptions = _render_list(plan.get("assumptions", []))
    verification = _render_list(plan.get("verification", []), "无额外验证项")
    questions = _render_list(plan.get("questions", []), "无")
    context = f'<p>{_e(plan["context"])}</p>' if plan.get("context") else ""
    goal = f'<p>{_e(plan["goal"])}</p>' if plan.get("goal") else ""
    rollback = f'<p>{_e(plan["rollback"])}</p>' if plan.get("rollback") else '<p class="empty">未指定；执行前请补充回滚方式。</p>'
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="Programmer Workflow plan">
<title>{_e(plan["title"])} · 执行计划</title>
<style>
:root{{--bg:#f5f7fb;--card:#fff;--text:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#4f46e5;--green:#059669;--amber:#d97706;--red:#dc2626;--mono:ui-monospace,Consolas,"Cascadia Code",monospace;--sans:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.6 var(--sans)}}
.shell{{width:min(920px,100%);margin:0 auto;padding:30px 20px 80px}}
.top{{display:flex;align-items:flex-start;gap:14px;margin-bottom:18px}}h1{{margin:0;font-size:28px;line-height:1.2;letter-spacing:-.03em}}h2{{font-size:15px;margin:24px 0 8px}}h3{{margin:0;font-size:14px}}.sub{{margin:5px 0 0;color:var(--muted);font-size:12px}}
.badge{{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);background:var(--card);border-radius:999px;padding:2px 9px;color:var(--muted);font-size:10.5px;font-weight:600;white-space:nowrap}}
.badge.pending{{color:var(--amber);border-color:rgba(217,119,6,.35)}} .badge.ok{{color:var(--green);border-color:rgba(5,150,105,.35)}}
.card{{border:1px solid var(--line);border-radius:14px;background:var(--card);padding:18px 20px;margin-top:12px}}
.lead{{color:var(--muted);font-size:12.5px;margin:0}}.lead code{{font-family:var(--mono);font-size:.92em;background:rgba(15,23,42,.05);padding:1px 4px;border-radius:4px}}
ul{{margin:6px 0 0;padding-left:18px}}li{{margin:4px 0;color:#334155}}p{{margin:6px 0;color:#334155}}.empty{{color:var(--muted);font-size:12px}}
.steps{{display:flex;flex-direction:column;gap:10px;margin-top:12px}}
.step{{border:1px solid var(--line);border-radius:12px;background:var(--card);padding:14px 16px}}
.step-head{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}.step-head h3{{display:inline}}.index{{font-family:var(--mono);font-size:10.5px;color:var(--accent);margin-right:7px;font-weight:700}}
.check input{{width:16px;height:16px;accent-color:var(--accent)}}.risk{{font-size:10px;border-radius:999px;padding:1px 7px;border:1px solid var(--line);margin-left:auto;color:var(--muted)}}.risk.high{{color:var(--red);border-color:rgba(220,38,38,.35)}}.risk.medium{{color:var(--amber);border-color:rgba(217,119,6,.35)}}.risk.low{{color:var(--green);border-color:rgba(5,150,105,.35)}}
.meta{{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;margin:10px 0 0}}.meta div{{min-width:0}}.meta dt{{font-size:10.5px;color:var(--muted);font-weight:600}}.meta dd{{margin:1px 0 0;font-size:12px;color:#334155;overflow-wrap:anywhere}}
.command{{margin-top:10px;border:1px solid var(--line);border-radius:8px;background:#f8fafc;overflow:hidden}}.command-head{{display:flex;justify-content:space-between;align-items:center;padding:5px 8px;color:var(--muted);font-size:10px;border-bottom:1px solid var(--line)}}.command pre{{margin:0;padding:9px 10px;overflow:auto;font:11px/1.55 var(--mono);color:#1e293b;white-space:pre-wrap;word-break:break-word}}.copy{{border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--text);font:600 10px/1.5 var(--sans);padding:1px 7px;cursor:pointer}}
.approval{{border:1px solid rgba(79,70,229,.35);background:rgba(79,70,229,.06);border-radius:12px;padding:15px 17px;margin-top:18px}}.approval h2{{margin:0 0 4px;font-size:16px}}.approval p{{margin:3px 0;color:#334155}}.actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}.primary,.ghost{{border:1px solid var(--accent);border-radius:7px;padding:7px 11px;font:600 12px/1.2 var(--sans);cursor:pointer}}.primary{{background:var(--accent);color:#fff}}.ghost{{background:#fff;color:var(--accent)}}
.footer{{margin-top:26px;color:var(--muted);font-size:10.5px;text-align:center}}@media(max-width:640px){{.meta{{grid-template-columns:1fr}}h1{{font-size:23px}}.shell{{padding:18px 14px 50px}}}}@media print{{body{{background:#fff}}.copy,.actions{{display:none}}.card,.step{{break-inside:avoid}}}}
</style>
</head>
<body>
<main class="shell">
<header class="top"><div><h1>{_e(plan["title"])}</h1><p class="sub">Programmer Workflow · 执行计划 · 等待审核</p></div><span class="badge pending">PLAN / REVIEW</span></header>
<section class="card"><p class="lead"><strong>先审核，再执行。</strong> 此页面不会自动运行命令。确认后回到对话回复 <code>执行</code>；需要调整就回复 <code>修改：...</code>；要停止就回复 <code>取消</code>。</p></section>
<section class="card"><h2>目标</h2>{goal or '<p class="empty">未填写</p>'}{context}<h2>假设</h2>{assumptions}</section>
<section><div class="steps">{''.join(steps)}</div></section>
<section class="card"><h2>整体验证</h2>{verification}<h2>回滚</h2>{rollback}<h2>需要你确认</h2>{questions}</section>
<section class="approval" id="approval"><h2>等待你的决定</h2><p>回复“执行”后，Agent 才会按上面的步骤操作；高风险命令仍需单独确认。</p><div class="actions"><button type="button" class="primary" data-copy="执行">复制“执行”</button><button type="button" class="ghost" data-copy="修改：">复制“修改：”</button><button type="button" class="ghost" data-copy="取消">复制“取消”</button><button type="button" class="ghost" id="print">打印</button></div></section>
<footer class="footer">Programmer Workflow · {_e(plan["mode"])} · 本文件由插件生成，可重新生成覆盖</footer>
</main>
<script>
(function() {{
  var KEY = 'pwf-plan-checks-v1:{plan_key}';
  var state = {{}};
  try {{ state = JSON.parse(localStorage.getItem(KEY) || '{{}}') }} catch (e) {{ state = {{}} }}
  var boxes = Array.prototype.slice.call(document.querySelectorAll('[data-check]'));
  function paint() {{ boxes.forEach(function (box) {{ box.checked = !!state[box.getAttribute('data-check')]; }}); }}
  boxes.forEach(function (box) {{ box.addEventListener('change', function () {{ state[box.getAttribute('data-check')] = box.checked; try {{ localStorage.setItem(KEY, JSON.stringify(state)) }} catch (e) {{}} }}); }});
  paint();
  document.addEventListener('click', function (event) {{
    var target = event.target.closest('[data-copy]');
    if (!target) {{ if (event.target.id === 'print') window.print(); return; }}
    var text = target.getAttribute('data-copy');
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).catch(function () {{}});
    var old = target.textContent; target.textContent = '已复制'; setTimeout(function () {{ target.textContent = old; }}, 1100);
  }});
}})();
</script>
</body>
</html>'''


def render_plan(plan: dict[str, Any], fmt: str) -> str:
    if fmt == "md":
        return render_markdown(plan)
    if fmt == "html":
        return render_html(plan)
    raise ValueError("format must be md or html")


def write_plan(plan: dict[str, Any], out: Path, fmt: str) -> Path:
    text = render_plan(plan, fmt)
    atomic_write_text(out, text)
    return out


def load_plan_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return normalize_plan(data)
