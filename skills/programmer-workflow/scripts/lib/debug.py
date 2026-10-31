"""Instrumented debug runs and log triage.

The runner captures a command's combined output to a local log directory and
keeps a bounded tail for the agent. Triage turns noisy logs into a small set of
error signatures, first-occurrence context, and hypotheses to verify next.
"""
from __future__ import annotations

import collections
import json
import os
import platform
import queue
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .common import (
    atomic_write_json,
    atomic_write_text,
    debug_log_dir,
    ensure_dir,
    load_plugin_config,
    now_iso,
    now_stamp,
    read_text_limited,
    relative_posix,
    run_git,
    truncate,
)

DESTRUCTIVE_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)?(?:/|~|\$HOME|[A-Za-z]:\\)",
    r"\b(del|erase)\s+/[sf]",
    r"\bformat\s+[A-Za-z]:",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bgit\s+(clean\s+-[a-z]*f|reset\s+--hard)",
    r"\bReg\s+delete\b",
    r"\bRemove-Item\b.*\s-(Recurse|Force)",
]

ERROR_RE = re.compile(
    r"(?i)(?:\b(error|fatal|critical|exception|failed|failure|panic|assert(?:ion)?|"
    r"segmentation fault|access violation|traceback)\b|"
    r"\b(E\d{3,}|ERR_[A-Z_]+)\b)"
)
TIMESTAMP_RE = re.compile(
    r"^\s*(?:\[?\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\]?\s*|"
    r"\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\s*)"
)
NOISE_RE = re.compile(r"(?i)(0 errors?|no errors?|error[-_ ]?free|error handling)")

HYPOTHESES: list[tuple[str, str, str, str]] = [
    (r"(?i)\b(none|null|undefined|nil)\b|cannot read propert|attributeerror", "空值与边界", "某个输入或返回值在边界处为空。", "在取值处打印变量、调用方和输入来源，确认第一个 None 出现的位置。"),
    (r"(?i)timeout|timed out|deadline exceeded|ETIMEDOUT", "超时与阻塞", "调用等待超时，可能是下游慢、死锁或线程池耗尽。", "记录每个阶段耗时；检查锁顺序、连接池和重试次数。"),
    (r"(?i)connection refused|ECONNREFUSED|unreachable|no route to host", "连接失败", "目标服务未启动、端口错误或被防火墙拦截。", "确认监听端口、健康检查和启动顺序；打印实际连接地址。"),
    (r"(?i)permission denied|EACCES|access is denied", "权限问题", "进程无权访问文件、目录或设备。", "打印绝对路径、当前用户与权限；确认是否被沙箱/杀毒软件拦截。"),
    (r"(?i)not found|ENOENT|no such file|cannot find", "路径或依赖缺失", "文件、模块或命令不存在。", "打印解析后的绝对路径与工作目录；确认依赖安装和大小写。"),
    (r"(?i)address already in use|EADDRINUSE", "端口占用", "端口已被其他进程占用。", "列出占用该端口的进程，或改用可配置端口。"),
    (r"(?i)out of memory|OOM|bad_alloc|std::bad_alloc|memoryerror", "内存压力", "内存不足或存在泄漏/大对象。", "记录 RSS、对象数量和分配点；缩小输入复现。"),
    (r"(?i)segmentation fault|access violation|null pointer|SIGSEGV", "内存/指针", "非法内存访问，常见于生命周期、越界或空指针。", "用 AddressSanitizer/Valgrind 或崩溃转储定位栈；打印指针与索引边界。"),
    (r"(?i)syntaxerror|typeerror|valueerror|invalid argument|invalid input", "输入或类型", "输入不符合预期，或类型转换失败。", "打印原始输入、类型与校验规则；在入口加 schema 校验。"),
    (r"(?i)database|sql|deadlock|lock wait|constraint", "数据库/并发", "SQL、事务或锁冲突。", "打印 SQL、参数、事务边界与锁等待；检查索引和隔离级别。"),
    (r"(?i)ssl|certificate|TLS", "证书/TLS", "证书过期、域名不匹配或信任链缺失。", "打印证书 subject/有效期/链；确认系统时间。"),
    (r"(?i)module not found|modulenotfounderror|importerror|cannot import", "依赖/导入", "模块未安装或导入路径错误。", "打印 sys.path / NODE_PATH；确认虚拟环境与锁文件。"),
]


class DestructiveCommandError(RuntimeError):
    pass


class ConsentRequiredError(RuntimeError):
    pass


def _looks_destructive(cmd_text: str) -> str | None:
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, cmd_text, re.IGNORECASE):
            return pattern
    return None


def _slug(text: str, limit: int = 32) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", text, flags=re.UNICODE).strip("-._")
    return (text or "run")[:limit]


def run_command(
    workspace: Path,
    command: Sequence[str],
    *,
    label: str = "run",
    timeout: float = 120.0,
    shell: bool = False,
    assume_yes: bool = False,
    full_authority: bool = False,
    allow_destructive: bool = False,
    max_log_bytes: int = 50_000_000,
    tail_lines: int = 120,
) -> dict[str, Any]:
    if not command:
        raise ValueError("empty command")
    raw_command = list(command)
    if shell:
        command_text = raw_command[0] if len(raw_command) == 1 else (
            subprocess.list2cmdline(raw_command) if os.name == "nt" else shlex.join(raw_command)
        )
    else:
        command_text = shlex.join(raw_command)
    dangerous = _looks_destructive(command_text)
    if dangerous and not allow_destructive:
        raise DestructiveCommandError(
            "refusing a potentially destructive command; ask the user and rerun with --allow-destructive "
            f"(matched: {dangerous})"
        )
    if not assume_yes and not full_authority and load_plugin_config(workspace).get("workflowMode", "plan") == "plan":
        if not sys.stdin.isatty():
            raise ConsentRequiredError(
                "plan mode requires approval; ask the user and rerun with --yes after approval "
                "(or switch workflowMode=full-authority / pass --full-authority when the host is in Full authority)"
            )
        print("About to run:", command_text)
        print("Working directory:", workspace)
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            raise ConsentRequiredError("cancelled by user")

    workspace = workspace.resolve()
    stamp = now_stamp()
    log_root = debug_log_dir(workspace)
    log_dir = ensure_dir(log_root / f"{stamp}-{_slug(label)}")
    ensure_dir(log_root)
    gitignore = log_root / ".gitignore"
    if not gitignore.exists():
        atomic_write_text(gitignore, "*\n!.gitignore\n")
    combined_path = log_dir / "combined.log"
    meta_path = log_dir / "meta.json"
    started = datetime.now().astimezone()
    t0 = time.time()

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    popen_kwargs: dict[str, Any] = {
        "cwd": str(workspace),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": env,
        "bufsize": 1,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    tail: collections.deque[str] = collections.deque(maxlen=tail_lines)
    written = 0
    timed_out = False
    exit_code: int | None = None
    proc: subprocess.Popen | None = None
    lines: "queue.Queue[str | None]" = queue.Queue()

    def _reader(stream: Any) -> None:
        try:
            for raw in iter(stream.readline, ""):
                lines.put(raw)
        except (OSError, ValueError):
            pass
        finally:
            lines.put(None)

    try:
        proc = subprocess.Popen(command_text if shell else raw_command, shell=shell, **popen_kwargs)
        assert proc.stdout is not None
        reader = threading.Thread(target=_reader, args=(proc.stdout,), daemon=True)
        reader.start()
        with combined_path.open("w", encoding="utf-8", newline="\n") as log:
            deadline = t0 + timeout
            while True:
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    if proc.poll() is not None:
                        # Give the reader a moment to deliver the final lines.
                        try:
                            line = lines.get(timeout=0.5)
                        except queue.Empty:
                            break
                    elif time.time() > deadline:
                        timed_out = True
                        _kill_tree(proc)
                        deadline = time.time() + 5
                        continue
                    else:
                        continue
                if line is None:
                    break
                tail.append(line.rstrip("\r\n"))
                if written < max_log_bytes:
                    log.write(line if line.endswith("\n") else line + "\n")
                    written += len(line.encode("utf-8", errors="replace"))
                    if written >= max_log_bytes:
                        log.write("[programmer-workflow] log size cap reached; further output discarded\n")
                if time.time() > deadline and proc.poll() is None:
                    timed_out = True
                    _kill_tree(proc)
                    deadline = time.time() + 5
            try:
                exit_code = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                exit_code = proc.poll()
    finally:
        if proc is not None and proc.poll() is None:
            _kill_tree(proc)

    ended = datetime.now().astimezone()
    duration = round(time.time() - t0, 2)
    meta = {
        "schema": 1,
        "label": label,
        "command": command_text,
        "shell": shell,
        "cwd": str(workspace),
        "started_at": started.isoformat(timespec="seconds"),
        "ended_at": ended.isoformat(timespec="seconds"),
        "duration_seconds": duration,
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "log": str(combined_path),
        "log_bytes": combined_path.stat().st_size if combined_path.exists() else 0,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "git_commit": run_git(["rev-parse", "--short", "HEAD"], workspace),
    }
    atomic_write_json(meta_path, meta)
    return {**meta, "tail": list(tail), "meta_path": str(meta_path)}


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, check=False, timeout=10,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    # taskkill can be denied by a host sandbox; always try the direct child too.
    try:
        if proc.poll() is None:
            proc.kill()
    except OSError:
        pass


# --------------------------------------------------------------------------
# Triage
# --------------------------------------------------------------------------

def _normalize_signature(line: str) -> str:
    text = TIMESTAMP_RE.sub("", line.strip())
    text = re.sub(r"\b0x[0-9a-fA-F]+\b", "0xADDR", text)
    text = re.sub(r"\b\d{4,}\b", "N", text)
    text = re.sub(r"\s+", " ", text)
    return text[:400]


def _error_level(line: str) -> str:
    low = line.lower()
    if "fatal" in low or "panic" in low or "critical" in low:
        return "FATAL"
    if "segmentation fault" in low or "access violation" in low:
        return "CRASH"
    if "exception" in low or "traceback" in low:
        return "EXCEPTION"
    if "error" in low or "failed" in low or "failure" in low:
        return "ERROR"
    return "WARN"


def triage_log(log_path: Path, *, max_bytes: int = 8_000_000, context: int = 6) -> dict[str, Any]:
    text = read_text_limited(log_path, max_bytes=max_bytes)
    if text is None:
        raise ValueError(f"cannot read log (too large or binary): {log_path}")
    lines = text.splitlines()
    signatures: dict[str, dict[str, Any]] = {}
    markers: list[dict[str, Any]] = []
    stack_blocks: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        if "[DBG" in line or re.search(r"\bDBG[:\]]", line):
            marker = _normalize_signature(line)
            markers.append({"line": idx + 1, "text": line[:500], "key": marker[:160]})
        if not line.strip() or NOISE_RE.search(line):
            continue
        if ERROR_RE.search(line):
            key = _normalize_signature(line)
            item = signatures.setdefault(key, {
                "key": key,
                "level": _error_level(line),
                "count": 0,
                "first_line": idx + 1,
                "last_line": idx + 1,
                "sample": line[:600],
                "context": [],
            })
            item["count"] += 1
            item["last_line"] = idx + 1
            if not item["context"]:
                start = max(0, idx - context)
                end = min(len(lines), idx + context + 1)
                item["context"] = [
                    {"line": n + 1, "text": lines[n][:600]} for n in range(start, end)
                ]
        if re.match(r"^\s*(Traceback \(most recent call last\)|panic:|Unhandled exception|"
                    r"System\.(NullReference|InvalidOperation|Argument)|"
                    r"at [\w.$<>]+\(|Thread \d+ \"|Caused by:)", line):
            block = []
            for n in range(idx, min(len(lines), idx + 18)):
                if n > idx and lines[n].strip() and not lines[n].startswith((" ", "\t", "Caused by:")):
                    if not re.match(r"^(at |File |\w+Error|panic|Exception|\w+Exception)", lines[n]):
                        break
                block.append({"line": n + 1, "text": lines[n][:700]})
            if len(block) > 1:
                stack_blocks.append({"start_line": idx + 1, "text": block[0]["text"], "block": block})

    ordered = sorted(signatures.values(), key=lambda item: (-item["count"], item["first_line"]))
    hypotheses = _hypotheses("\n".join(item["sample"] for item in ordered[:20]) + "\n" + "\n".join(m["text"] for m in markers[:30]))
    marker_counts: dict[str, int] = {}
    for marker in markers:
        marker_counts[marker["key"]] = marker_counts.get(marker["key"], 0) + 1
    report = {
        "schema": 1,
        "kind": "log-triage",
        "log": str(log_path),
        "generated_at": now_iso(),
        "lines": len(lines),
        "bytes": log_path.stat().st_size if log_path.exists() else len(text.encode("utf-8")),
        "signatures": ordered[:30],
        "signature_count": len(ordered),
        "markers": {
            "count": len(markers),
            "unique": len(marker_counts),
            "first": markers[:40],
            "top": [
                {"key": key, "count": count}
                for key, count in sorted(marker_counts.items(), key=lambda kv: -kv[1])[:10]
            ],
        },
        "stack_blocks": stack_blocks[:8],
        "hypotheses": hypotheses,
        "disclaimer": "自动分诊只根据文本模式推断，必须结合代码与复现步骤验证，不能当作结论。",
    }
    return report


def _hypotheses(blob: str) -> list[dict[str, str]]:
    result = []
    for pattern, title, reasoning, next_step in HYPOTHESES:
        if re.search(pattern, blob):
            result.append({
                "title": title,
                "reasoning": reasoning,
                "next_step": next_step,
                "confidence": "medium" if len(result) == 0 else "low",
            })
    if not result:
        result.append({
            "title": "需要更多现场",
            "reasoning": "日志中没有命中常见错误模式，可能问题不在日志文本，或日志级别/覆盖点不足。",
            "next_step": "在关键分支、入口参数和状态转换处补充 [DBG-...] 标记后重跑；同时记录复现步骤和环境。",
            "confidence": "low",
        })
    return result[:6]


def triage_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 日志分诊报告",
        "",
        f"- 日志：`{report['log']}`",
        f"- 生成时间：{report['generated_at']}",
        f"- 行数：{report['lines']} · 大小：{report['bytes']} bytes",
        f"- 关键签名：{report['signature_count']} 类 · 调试标记：{report['markers']['count']} 条",
        "",
        "> 自动分诊只根据文本模式推断，必须结合代码与复现步骤验证。",
        "",
        "## 关键错误",
        "",
    ]
    if not report["signatures"]:
        lines.append("_没有识别到错误行。_")
    for index, sig in enumerate(report["signatures"][:12], 1):
        lines.extend([
            f"### {index}. [{sig['level']}] {truncate(sig['sample'], 180)}",
            "",
            f"- 出现 {sig['count']} 次，首次第 {sig['first_line']} 行，最后第 {sig['last_line']} 行",
        ])
        if sig.get("context"):
            lines.extend(["", "首次现场：", "", "```text"])
            lines.extend(item["text"] for item in sig["context"])
            lines.extend(["```", ""])
    if report["stack_blocks"]:
        lines.extend(["## 异常/崩溃栈", ""])
        for block in report["stack_blocks"][:5]:
            lines.extend([f"### 第 {block['start_line']} 行：{truncate(block['text'], 160)}", "", "```text"])
            lines.extend(item["text"] for item in block["block"])
            lines.extend(["```", ""])
    lines.extend(["## 调试标记", ""])
    if not report["markers"]["count"]:
        lines.append("_日志中没有 `[DBG-...]` 标记；考虑补充关键分支与变量快照。_")
    else:
        for item in report["markers"]["top"]:
            lines.append(f"- {item['count']}× `{truncate(item['key'], 180)}`")
        lines.extend(["", "最早出现的标记：", ""])
        for marker in report["markers"]["first"][:20]:
            lines.append(f"- L{marker['line']}: `{truncate(marker['text'], 220)}`")
    lines.extend(["", "## 假设与下一步", ""])
    for index, hyp in enumerate(report["hypotheses"], 1):
        lines.append(f"{index}. **{hyp['title']}**（置信度 {hyp['confidence']}）：{hyp['reasoning']}")
        lines.append(f"   - 下一步：{hyp['next_step']}")
    lines.extend([
        "",
        "## 建议的验证顺序",
        "",
        "1. 用最小输入复现，确认错误签名与日志一致。",
        "2. 在签名对应代码路径上补充一条 `[DBG-<ticket>]` 日志，打印输入、状态与分支。",
        "3. 重新运行 `companion.py run`，对比分诊报告中的首次现场。",
        "4. 修复后删除临时日志（或改为受 `DEBUG` 环境变量控制），并补一个回归测试。",
        "",
        f"_报告由 Programmer Workflow 生成：{report['generated_at']}_",
    ])
    return "\n".join(lines)


def write_triage(log_path: Path, report: dict[str, Any]) -> Path:
    out = log_path.parent / "TRIAGE.md"
    atomic_write_text(out, triage_markdown(report))
    atomic_write_json(log_path.parent / "TRIAGE.json", report)
    return out


def log_excerpt(log_path: Path, *, lines: int = 80) -> str:
    text = read_text_limited(log_path, max_bytes=2_000_000) or ""
    tail = text.splitlines()[-lines:]
    return "\n".join(tail)
