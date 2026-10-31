"""Bounded project inspection used by memory harvesting, docs and debugging.

Nothing here uploads data. Transcript scanning is opt-in and metadata-only
unless the caller explicitly asks for user-text extraction.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .common import (
    IGNORED_DIRS,
    TEXT_EXTS,
    atomic_write_json,
    human_bytes,
    iter_project_files,
    language_for,
    line_count,
    now_iso,
    read_text_limited,
    redact_url,
    relative_posix,
    run_git,
    sha256_text,
    truncate,
    workspace_state,
)

MANIFEST_NAMES = {
    "package.json": "npm",
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "poetry.lock": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "CMakeLists.txt": "cmake",
    "Makefile": "make",
    "meson.build": "meson",
    "pubspec.yaml": "dart",
    "composer.json": "php",
    "Gemfile": "ruby",
    "*.csproj": "dotnet",
    "*.sln": "dotnet",
    "*.vcxproj": "msbuild",
    "platformio.ini": "platformio",
    "west.yml": "zephyr",
    "prj.conf": "zephyr",
    "sdkconfig": "esp-idf",
    "*.ioc": "stm32cube",
    "*.ino": "arduino",
}

ENTRY_NAMES = {
    "main.py", "app.py", "cli.py", "server.py", "__main__.py", "manage.py",
    "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts", "server.js",
    "server.ts", "main.go", "main.rs", "main.c", "main.cpp", "main.cc",
    "Program.cs", "Application.java", "main.dart", "index.html",
}

CONFIG_NAMES = [
    ".editorconfig", ".prettierrc", ".prettierrc.json", ".prettierrc.yaml",
    ".prettierrc.yml", ".eslintrc", ".eslintrc.json", ".eslintrc.js",
    ".gitattributes", ".gitmessage", "ruff.toml", ".ruff.toml", ".clang-format",
    ".clang-tidy", ".rustfmt.toml", "rustfmt.toml", ".golangci.yml",
    "tsconfig.json", "jsconfig.json", "CONTRIBUTING.md", "CODEOWNERS",
]

HARDWARE_HINTS = {
    "platformio.ini": "PlatformIO 嵌入式工程",
    "west.yml": "Zephyr 工程",
    "prj.conf": "Zephyr 配置",
    "sdkconfig": "ESP-IDF 配置",
    "*.ioc": "STM32CubeMX 工程",
    "*.ino": "Arduino 工程",
    "boards/": "板级支持目录",
    "firmware/": "固件目录",
}

HARDWARE_DEPENDENCIES = {
    "pyserial": "Python 串口依赖",
    "serialport": "Node 串口依赖",
    "johnny-five": "Arduino/JS 硬件依赖",
    "onoff": "GPIO 依赖",
    "rpi.gpio": "树莓派 GPIO 依赖",
    "smbus": "I2C 依赖",
    "spidev": "SPI 依赖",
}

HARDWARE_CONFIG_KEYS = {"openocd", "jlink", "st-link", "stlink", "cmsis-dap"}

FRAMEWORK_HINTS = {
    "react": "React", "next": "Next.js", "vue": "Vue", "nuxt": "Nuxt",
    "svelte": "Svelte", "angular": "Angular", "express": "Express",
    "fastify": "Fastify", "electron": "Electron", "tauri": "Tauri",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "pytorch": "PyTorch", "torch": "PyTorch", "tensorflow": "TensorFlow",
    "numpy": "NumPy", "pandas": "pandas", "pyqt": "PyQt", "pyside": "PySide",
    "cmake": "CMake", "qt": "Qt", "boost": "Boost", "opencv": "OpenCV",
    "pyserial": "串口", "serialport": "串口",
}

IGNORE_FILE_PATTERNS = re.compile(
    r"(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|Cargo\.lock|"
    r"\.min\.(js|css)$|\.map$|\.generated\.|__generated__|\.designer\.cs$)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _is_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    return cjk / max(1, len(re.findall(r"[\u4e00-\u9fffA-Za-z]", text)))


def _safe_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def _read_snippet(path: Path, limit: int = 1200) -> str:
    text = read_text_limited(path, max_bytes=200_000)
    if text is None:
        return ""
    return truncate(text.strip(), limit)


def _git_info(root: Path) -> dict[str, Any]:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    commit = run_git(["rev-parse", "--short", "HEAD"], root)
    remote = run_git(["remote", "get-url", "origin"], root)
    status = run_git(["status", "--porcelain"], root)
    subjects_raw = run_git(["log", "-n", "50", "--pretty=format:%s"], root)
    subjects = [s for s in (subjects_raw or "").splitlines() if s.strip()]
    conventional = sum(1 for s in subjects if re.match(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?:", s))
    cjk = sum(1 for s in subjects if _is_cjk(s))
    return {
        "branch": branch,
        "commit": commit,
        "remote": redact_url(remote) if remote else None,
        "dirty_files": len(status.splitlines()) if status else 0,
        "recent_subjects": subjects[:20],
        "commit_style": {
            "conventional": conventional,
            "chinese": cjk,
            "total": len(subjects),
            "average_length": round(sum(len(s) for s in subjects) / max(1, len(subjects)), 1),
        },
    }


def _module_candidates(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    code_files = [p for p in files if p.suffix.lower() in TEXT_EXTS and language_for(p)]
    buckets: dict[str, list[Path]] = defaultdict(list)
    for path in code_files:
        rel = path.relative_to(root)
        parts = rel.parts
        if len(parts) >= 2:
            key = parts[0]
            if key == "src" and len(parts) >= 3:
                key = f"src/{parts[1]}"
        else:
            key = "(root)"
        buckets[key].append(path)
    result = []
    for name, items in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:40]:
        result.append({
            "name": name,
            "path": name,
            "code_files": len(items),
            "examples": [relative_posix(p, root) for p in items[:5]],
        })
    return result


def _entry_candidates(root: Path) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for path in iter_project_files(root, max_files=2500):
        name = path.name
        rel = relative_posix(path, root)
        if name in ENTRY_NAMES:
            found.append({"path": rel, "reason": f"常见入口文件名 {name}"})
        elif name == "package.json":
            data = read_text_limited(path, 300_000)
            if data:
                try:
                    pkg = json.loads(data)
                except json.JSONDecodeError:
                    continue
                for key in ("main", "module", "bin"):
                    value = pkg.get(key)
                    if isinstance(value, str):
                        found.append({"path": value, "reason": f"package.json {key}"})
                    elif isinstance(value, dict):
                        for k, v in list(value.items())[:3]:
                            if isinstance(v, str):
                                found.append({"path": v, "reason": f"package.json bin.{k}"})
        elif name == "pyproject.toml":
            text = read_text_limited(path, 300_000) or ""
            for match in re.finditer(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]+:[^"]+)"', text, re.MULTILINE):
                found.append({"path": match.group(1), "reason": "pyproject scripts"})
        if len(found) >= 25:
            break
    seen: set[str] = set()
    unique = []
    for item in found:
        if item["path"] not in seen:
            seen.add(item["path"])
            unique.append(item)
    return unique[:20]


def _manifests(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in files:
        name = path.name
        kind = None
        for pattern, label in MANIFEST_NAMES.items():
            if pattern.startswith("*."):
                if name.endswith(pattern[1:]):
                    kind = label
                    break
            elif name == pattern:
                kind = label
                break
        if not kind:
            continue
        info: dict[str, Any] = {
            "path": relative_posix(path, root),
            "type": kind,
            "bytes": path.stat().st_size if path.exists() else 0,
        }
        if name == "package.json":
            text = read_text_limited(path, 300_000)
            if text:
                try:
                    pkg = json.loads(text)
                except json.JSONDecodeError:
                    pkg = {}
                info["name"] = pkg.get("name")
                info["version"] = pkg.get("version")
                info["scripts"] = list((pkg.get("scripts") or {}).keys())[:12]
                deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
                info["dependencies"] = list(deps.keys())[:30]
        elif name in ("pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "CMakeLists.txt", "platformio.ini", "prj.conf"):
            info["snippet"] = _read_snippet(path, 700)
        result.append(info)
    return result[:20]


def _tooling(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    names = {p.name: p for p in files}
    result: list[dict[str, Any]] = []
    for name in CONFIG_NAMES:
        path = names.get(name) or (root / name if (root / name).exists() else None)
        if path and path.is_file():
            result.append({"path": relative_posix(path, root), "snippet": _read_snippet(path, 900)})
    for directory in (".github/workflows", ".vscode", ".devcontainer"):
        base = root / directory
        if base.is_dir():
            entries = sorted(base.iterdir())[:8]
            result.append({
                "path": directory,
                "snippet": ", ".join(e.name for e in entries),
            })
    return result[:20]


def _style_profile(root: Path, files: list[Path]) -> dict[str, Any]:
    candidates = [
        p for p in files
        if p.suffix.lower() in TEXT_EXTS
        and not IGNORE_FILE_PATTERNS.search(p.name)
        and _safe_stat(p)
        and _safe_stat(p).st_size <= 300_000  # type: ignore[union-attr]
    ]
    # Prefer source files, then docs/configs.
    candidates.sort(key=lambda p: (p.suffix.lower() not in {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".java",
    }, str(p)))
    sample = candidates[:45]
    indent = Counter()
    endings = Counter()
    encoding = Counter()
    naming = Counter()
    comments = Counter()
    quote = Counter()
    analyzed = 0
    for path in sample:
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:2048]:
            continue
        analyzed += 1
        if raw.startswith(b"\xef\xbb\xbf"):
            encoding["utf-8-bom"] += 1
        else:
            encoding["utf-8"] += 1
        if b"\r\n" in raw:
            endings["crlf"] += 1
        else:
            endings["lf"] += 1
        text = raw.decode("utf-8-sig", errors="replace")
        stem = path.stem
        if re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$", stem):
            naming["snake_case"] += 1
        elif re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$", stem):
            naming["kebab-case"] += 1
        elif re.match(r"^[A-Z][a-zA-Z0-9]*$", stem):
            naming["PascalCase"] += 1
        elif re.match(r"^[a-z][a-zA-Z0-9]*$", stem) and re.search(r"[A-Z]", stem):
            naming["camelCase"] += 1
        else:
            naming["other"] += 1
        seen_indent = False
        for line in text.splitlines()[:2500]:
            if not line.strip():
                continue
            match = re.match(r"^([ \t]+)\S", line)
            if match:
                lead = match.group(1)
                if "\t" in lead:
                    indent["tabs"] += 1
                    seen_indent = True
                else:
                    count = len(lead)
                    if count in (2, 4, 8):
                        indent[f"spaces_{count}"] += 1
                        seen_indent = True
            comment = line.lstrip()
            if comment.startswith(("#", "//", "/*", "*", "--")):
                if _is_cjk(comment):
                    comments["cjk"] += 1
                elif re.search(r"[A-Za-z]", comment):
                    comments["latin"] += 1
            if path.suffix.lower() in {".js", ".ts", ".jsx", ".tsx"}:
                quote["single"] += len(re.findall(r"'[^'\n]{2,}'", line))
                quote["double"] += len(re.findall(r'"[^"\n]{2,}"', line))
    dominant_indent = "unknown"
    if indent:
        key = indent.most_common(1)[0][0]
        dominant_indent = {"tabs": "tabs", "spaces_2": "2 spaces", "spaces_4": "4 spaces", "spaces_8": "8 spaces"}.get(key, key)
    dominant_naming = naming.most_common(1)[0][0] if naming else "unknown"
    comment_language = "unknown"
    if comments:
        comment_language = "中文" if comments["cjk"] > comments["latin"] else "英文"
    return {
        "sampled_files": analyzed,
        "indentation": {"counts": dict(indent), "dominant": dominant_indent},
        "line_endings": {"counts": dict(endings), "dominant": "CRLF" if endings["crlf"] > endings["lf"] else "LF"},
        "encoding": dict(encoding),
        "file_naming": {"counts": dict(naming), "dominant": dominant_naming},
        "comments": {"counts": dict(comments), "dominant_language": comment_language},
        "js_quotes": dict(quote),
    }


def _docs_signals(root: Path, files: list[Path]) -> dict[str, Any]:
    readmes = [p for p in files if p.name.lower() in {"readme.md", "readme.rst", "readme.txt", "readme"}]
    docs_dir = root / "docs"
    headings: list[str] = []
    language = "unknown"
    readme_path = readmes[0] if readmes else None
    if readme_path:
        text = read_text_limited(readme_path, 400_000) or ""
        headings = [re.sub(r"^#+\s*", "", line).strip() for line in text.splitlines() if re.match(r"^#{1,4}\s+", line)][:15]
        language = "中文" if _cjk_ratio(text) >= 0.15 else "英文"
    return {
        "readme": relative_posix(readme_path, root) if readme_path else None,
        "readme_headings": headings,
        "readme_language": language,
        "docs_dir": docs_dir.is_dir(),
        "docs_files": len(list(docs_dir.glob("*"))) if docs_dir.is_dir() else 0,
        "agent_instructions": [
            relative_posix(p, root) for p in files
            if p.name in {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules"}
        ][:10],
    }


def _hardware_signals(root: Path, files: list[Path]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    names = {p.name for p in files}
    for filename, label in HARDWARE_HINTS.items():
        if filename.startswith("*."):
            for p in files:
                if p.name.endswith(filename[1:]):
                    hits.append({"path": relative_posix(p, root), "reason": label})
                    break
        elif filename.endswith("/"):
            directory = root / filename.rstrip("/")
            if directory.is_dir():
                hits.append({"path": filename, "reason": label})
        elif filename in names:
            path = next(p for p in files if p.name == filename)
            hits.append({"path": relative_posix(path, root), "reason": label})

    # Dependencies are stronger evidence than a passing mention in documentation.
    for name in ("requirements.txt", "pyproject.toml", "package.json", "Pipfile", "environment.yml"):
        path = root / name
        if not path.exists():
            continue
        text = (read_text_limited(path, 300_000) or "").lower()
        for dependency, label in HARDWARE_DEPENDENCIES.items():
            if dependency in text:
                hits.append({"path": name, "reason": label})
                break

    # Debug-probe configs often name the adapter even when no board file exists.
    for p in files:
        if p.suffix.lower() not in {".json", ".yaml", ".yml", ".toml", ".cfg", ".conf", ".ini"}:
            continue
        if p.stat().st_size > 300_000 or IGNORE_FILE_PATTERNS.search(p.name):
            continue
        text = (read_text_limited(p, 300_000) or "").lower()
        for key in HARDWARE_CONFIG_KEYS:
            if key in text:
                hits.append({"path": relative_posix(p, root), "reason": f"调试探针配置：{key}"})
                break

    unique: list[dict[str, str]] = []
    seen = set()
    for hit in hits:
        if hit["path"] not in seen:
            seen.add(hit["path"])
            unique.append(hit)
    return {
        "likely_hardware": bool(unique),
        "hits": unique[:20],
        "note": "这些只是线索，不代表当前机器连接了硬件；需要用户确认。",
    }


def _test_signals(root: Path, files: list[Path]) -> dict[str, Any]:
    test_files = [
        p for p in files
        if re.search(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*\.|_test\.|\.test\.|\.spec\.|Tests?\.(cs|java|kt)$", relative_posix(p, root))
    ]
    frameworks = []
    text_blob = ""
    for name in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml"):
        path = root / name
        if path.exists():
            text_blob += (read_text_limited(path, 200_000) or "").lower()
    for key, label in {
        "pytest": "pytest", "unittest": "unittest", "jest": "Jest", "vitest": "Vitest",
        "mocha": "Mocha", "playwright": "Playwright", "cypress": "Cypress",
        "xunit": "xUnit", "nunit": "NUnit", "junit": "JUnit", "cargo test": "cargo test",
        "gtest": "GoogleTest", "catch2": "Catch2", "doctest": "doctest",
    }.items():
        if key in text_blob:
            frameworks.append(label)
    return {
        "test_files": len(test_files),
        "examples": [relative_posix(p, root) for p in test_files[:10]],
        "frameworks": frameworks,
    }


def _signals(root: Path, files: list[Path], manifests: list[dict[str, Any]]) -> dict[str, Any]:
    deps_blob = " ".join(
        " ".join(str(d) for d in m.get("dependencies", [])) for m in manifests
    ).lower()
    frameworks = []
    for key, label in FRAMEWORK_HINTS.items():
        if key in deps_blob:
            frameworks.append(label)
    # File-based hints.
    for pattern, label in {
        "CMakeLists.txt": "CMake", "package.json": "Node.js", "pyproject.toml": "Python",
        "Cargo.toml": "Rust", "go.mod": "Go", "*.sln": ".NET", "*.csproj": ".NET",
        "platformio.ini": "PlatformIO", "*.ioc": "STM32", "electron": "Electron",
    }.items():
        if pattern.startswith("*."):
            if any(p.name.endswith(pattern[1:]) for p in files):
                frameworks.append(label)
        elif (root / pattern).exists():
            frameworks.append(label)
    ci = []
    for path in (".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci"):
        if (root / path).exists():
            ci.append(path)
    package_managers = []
    for name, label in {
        "package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "Yarn",
        "poetry.lock": "Poetry", "Pipfile.lock": "Pipenv", "uv.lock": "uv",
        "Cargo.lock": "Cargo", "go.sum": "Go modules", "pom.xml": "Maven",
        "build.gradle": "Gradle", "requirements.txt": "pip",
    }.items():
        if (root / name).exists():
            package_managers.append(label)
    return {
        "frameworks": sorted(set(frameworks)),
        "package_managers": sorted(set(package_managers)),
        "ci": ci,
        "has_tests": _test_signals(root, files),
    }


# --------------------------------------------------------------------------
# public: project map
# --------------------------------------------------------------------------

def project_map(root: Path, max_files: int = 6000) -> dict[str, Any]:
    root = root.resolve()
    files: list[Path] = []
    total_bytes = 0
    truncated = False
    for path in iter_project_files(root, max_files=max_files):
        files.append(path)
        st = _safe_stat(path)
        if st:
            total_bytes += st.st_size
    if len(files) >= max_files:
        truncated = True
    by_ext: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "bytes": 0, "lines": 0})
    for path in files:
        ext = path.suffix.lower() or "(none)"
        entry = by_ext[ext]
        entry["count"] += 1
        st = _safe_stat(path)
        if st:
            entry["bytes"] += st.st_size
        if ext in TEXT_EXTS and (st is None or st.st_size <= 400_000):
            entry["lines"] += line_count(path, 400_000)
    languages = Counter()
    for ext, info in by_ext.items():
        if ext in TEXT_EXTS:
            sample = next((p for p in files if p.suffix.lower() == ext), None)
            if sample:
                lang = language_for(sample) or ext
                languages[lang] += info["count"]
    manifests = _manifests(root, files)
    return {
        "schema": 1,
        "kind": "project-map",
        "root": str(root),
        "generated_at": now_iso(),
        "git": _git_info(root),
        "files": {
            "total": len(files),
            "bytes": total_bytes,
            "human_bytes": human_bytes(total_bytes),
            "truncated": truncated,
            "by_ext": dict(sorted(by_ext.items(), key=lambda kv: -kv[1]["count"])[:30]),
        },
        "languages": dict(languages.most_common(15)),
        "modules": _module_candidates(root, files),
        "manifests": manifests,
        "entry_candidates": _entry_candidates(root),
        "tooling": _tooling(root, files),
        "docs": _docs_signals(root, files),
        "tests": _test_signals(root, files),
        "signals": _signals(root, files, manifests),
        "hardware": _hardware_signals(root, files),
        "top_files": [
            {"path": relative_posix(p, root), "lines": line_count(p, 400_000)}
            for p in sorted(files, key=lambda p: (_safe_stat(p).st_size if _safe_stat(p) else 0), reverse=True)[:20]
            if p.suffix.lower() in TEXT_EXTS
        ],
    }


# --------------------------------------------------------------------------
# public: habit scan
# --------------------------------------------------------------------------

def _transcript_roots(home: Path) -> list[dict[str, Any]]:
    return [
        {"source": "dsh", "root": home / ".dsh" / "sessions", "pattern": "**/*.jsonl"},
        {"source": "kimi", "root": home / ".kimi-code" / "sessions", "pattern": "**/wire.jsonl"},
        {"source": "claude", "root": home / ".claude" / "projects", "pattern": "**/*.jsonl"},
        {"source": "codex", "root": home / ".codex" / "sessions", "pattern": "**/*.jsonl"},
        {"source": "cursor", "root": home / ".cursor" / "projects", "pattern": "**/*.jsonl"},
    ]


def list_transcripts(home: Path, *, max_files: int = 80) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for spec in _transcript_roots(home):
        root: Path = spec["root"]
        if not root.exists():
            continue
        try:
            candidates = list(root.glob(spec["pattern"]))
        except OSError:
            continue
        for path in candidates[:max_files]:
            st = _safe_stat(path)
            if not st or st.st_size == 0:
                continue
            found.append({
                "source": spec["source"],
                "path": str(path),
                "bytes": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
            })
    found.sort(key=lambda item: item["modified"], reverse=True)
    return found[:max_files]


def _message_text(obj: Any) -> tuple[str | None, str | None]:
    """Best-effort (role, text) from a transcript JSON object. Never raises."""
    if not isinstance(obj, dict):
        return None, None
    role = obj.get("role")
    if role is None and isinstance(obj.get("message"), dict):
        role = obj["message"].get("role")
    if role is None:
        kind = obj.get("type")
        if kind in ("user", "human", "user_message"):
            role = "user"
        elif kind in ("assistant", "ai", "assistant_message"):
            role = "assistant"
    if role not in ("user", "human"):
        return None, None
    content = obj.get("content")
    if content is None and isinstance(obj.get("message"), dict):
        content = obj["message"].get("content")
    if content is None:
        content = obj.get("text")
    if isinstance(content, str):
        return "user", content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif item.get("type") == "text" and isinstance(item.get("content"), str):
                    parts.append(item["content"])
        text = "\n".join(parts).strip()
        return ("user", text) if text else (None, None)
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return "user", content["text"]
    return None, None


def extract_user_texts(
    home: Path,
    out_path: Path,
    *,
    max_files: int = 40,
    max_messages: int = 400,
    max_chars: int = 1200,
) -> dict[str, Any]:
    """Opt-in extraction of user messages for habit analysis. Writes JSONL locally."""
    rows: list[dict[str, Any]] = []
    scanned = 0
    for meta in list_transcripts(home, max_files=max_files):
        path = Path(meta["path"])
        if meta["bytes"] > 30_000_000:
            continue
        scanned += 1
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line_no, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line or len(line) > 2_000_000:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    role, text = _message_text(obj)
                    if role != "user" or not text:
                        continue
                    text = re.sub(r"\s+", " ", text).strip()
                    if len(text) < 4:
                        continue
                    rows.append({
                        "source": meta["source"],
                        "path": str(path),
                        "line": line_no,
                        "text": truncate(text, max_chars),
                    })
                    if len(rows) >= max_messages:
                        break
        except OSError:
            continue
        if len(rows) >= max_messages:
            break
    payload = {
        "generated_at": now_iso(),
        "files_scanned": scanned,
        "messages": rows,
        "privacy": "Local-only excerpts of user messages. Review before sharing; may contain secrets.",
    }
    atomic_write_json(out_path, payload)
    return {"path": str(out_path), "files_scanned": scanned, "messages": len(rows)}


def scan_project(
    root: Path,
    *,
    include_transcripts: bool = False,
    extract_user_text: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    home = (home or Path.home()).resolve()
    mapping = project_map(root)
    files = list(iter_project_files(root, max_files=4000))
    tooling = _tooling(root, files)
    docs = _docs_signals(root, files)
    hardware = _hardware_signals(root, files)
    transcripts_meta: dict[str, Any] = {
        "enabled": False,
        "note": "对话记录默认不读取。需要用户明确同意后，用 --include-transcripts 只列元数据，或用 --extract-user-text 提取用户发言。",
    }
    extraction = None
    if include_transcripts or extract_user_text:
        found = list_transcripts(home)
        transcripts_meta = {
            "enabled": True,
            "count": len(found),
            "sources": Counter(item["source"] for item in found),
            "items": found[:40],
            "privacy": "路径与时间戳属于敏感元数据，分享前请脱敏。",
        }
        if extract_user_text:
            out = workspace_state(root) / "transcripts-user-text.json"
            extraction = extract_user_texts(home, out)
    return {
        "schema": 1,
        "kind": "habit-scan",
        "root": str(root),
        "generated_at": now_iso(),
        "project": {
            "name": root.name,
            "git": mapping["git"],
            "languages": mapping["languages"],
            "files": mapping["files"],
            "modules": mapping["modules"][:15],
            "entry_candidates": mapping["entry_candidates"][:10],
        },
        "style": _style_profile(root, files),
        "tooling": tooling,
        "manifests": mapping["manifests"],
        "docs": docs,
        "tests": mapping["tests"],
        "signals": mapping["signals"],
        "hardware": hardware,
        "conventions": _derive_conventions(root, mapping, files),
        "transcripts": transcripts_meta,
        "extraction": extraction,
        "privacy": {
            "local_only": True,
            "excluded": ["secrets", "credentials", "personal data", "binary files", "vendored dependencies"],
            "note": "scan 只产生候选证据，不自动写记忆；必须由 Agent 汇总并经用户审核。",
        },
    }


def _derive_conventions(root: Path, mapping: dict[str, Any], files: list[Path]) -> list[dict[str, str]]:
    conventions: list[dict[str, str]] = []
    docs = mapping["docs"]
    if docs.get("readme_language") and docs["readme_language"] != "unknown":
        conventions.append({
            "key": "文档语言",
            "value": docs["readme_language"],
            "evidence": docs.get("readme") or "README",
        })
    tooling = {item["path"]: item.get("snippet", "") for item in mapping["tooling"]}
    for name, snippet in tooling.items():
        if name == ".editorconfig":
            conventions.append({"key": "编辑器约定", "value": "见 .editorconfig", "evidence": name})
        if "prettier" in name:
            conventions.append({"key": "前端格式化", "value": "Prettier", "evidence": name})
        if "eslint" in name:
            conventions.append({"key": "前端静态检查", "value": "ESLint", "evidence": name})
        if "ruff" in name or "pyproject.toml" in name and "[tool.ruff" in snippet:
            conventions.append({"key": "Python 静态检查", "value": "Ruff", "evidence": name})
        if "clang-format" in name:
            conventions.append({"key": "C/C++ 格式化", "value": "clang-format", "evidence": name})
    commit = mapping["git"].get("commit_style") or {}
    if commit.get("total", 0) >= 5:
        if commit.get("conventional", 0) / max(1, commit["total"]) > 0.5:
            conventions.append({"key": "提交信息", "value": "Conventional Commits", "evidence": "git log"})
        if commit.get("chinese", 0) / max(1, commit["total"]) > 0.5:
            conventions.append({"key": "提交信息语言", "value": "中文", "evidence": "git log"})
    if docs.get("agent_instructions"):
        conventions.append({
            "key": "已有 Agent 指令",
            "value": ", ".join(docs["agent_instructions"][:3]),
            "evidence": docs["agent_instructions"][0],
        })
    return conventions[:12]


def env_facts(root: Path) -> dict[str, Any]:
    mapping = project_map(root)
    return {
        "workspace": str(root.resolve()),
        "generated_at": now_iso(),
        "hardware": mapping["hardware"],
        "signals": mapping["signals"],
        "entry_candidates": mapping["entry_candidates"],
        "tests": mapping["tests"],
        "note": "hardware.likely_hardware 只是工程线索；是否连接硬件、是否部署环境必须由用户确认。",
    }
