"""Assemble single-file, offline HTML deliverables from templates."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from ..common import atomic_write_text, ensure_dir, html_escape, now_iso, sha256_text, truncate

TOKEN_TITLE = "{{WC_TITLE}}"
TOKEN_KIND = "{{WC_KIND}}"
TOKEN_PROJECT = "{{WC_PROJECT}}"
TOKEN_STYLE = "{{WC_STYLE}}"
TOKEN_SCRIPT = "{{WC_SCRIPT}}"
TOKEN_DATA = "{{WC_DATA}}"
TOKEN_GENERATED = "{{WC_GENERATED}}"
TOKEN_VERSION = "{{WC_VERSION}}"


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"template asset missing: {path}")
    return path.read_text(encoding="utf-8")


def _json_for_script(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("<!--", "<\\!--")


def _inject(template: str, replacements: dict[str, str]) -> str:
    for token, value in replacements.items():
        template = template.replace(token, value)
    if "{{WC_" in template:
        raise ValueError("unresolved template token remains in output")
    return template


def render_docs(
    arch: dict[str, Any],
    features: dict[str, Any],
    out_dir: Path,
    *,
    template_dir: Path,
    version: str = "0.1.0",
) -> list[Path]:
    ensure_dir(out_dir)
    template = _read(template_dir / "docs.html")
    base_css = _read(template_dir / "base.css")
    page_css = _read(template_dir / "docs.css")
    review_js = _read(template_dir / "review.js")
    page_js = _read(template_dir / "docs.js")
    style = f"{base_css}\n{page_css}"
    script = f"{review_js}\n{page_js}"
    written: list[Path] = []
    for data, filename, label in (
        (arch, "Architecture.html", "工程架构"),
        (features, "Features.html", "功能地图"),
    ):
        project = data.get("project", {})
        title = f"{label} · {project.get('name', '')}".strip(" ·")
        page = {
            "kind": data.get("kind"),
            "title": title,
            "project": project,
            "data": data,
            "generated_at": data.get("project", {}).get("generated_at") or now_iso(),
            "version": version,
            "sibling": "Features.html" if data.get("kind") == "architecture" else "Architecture.html",
        }
        html_text = _inject(template, {
            TOKEN_TITLE: html_escape(title),
            TOKEN_KIND: html_escape(str(data.get("kind", ""))),
            TOKEN_PROJECT: html_escape(str(project.get("name", ""))),
            TOKEN_GENERATED: html_escape(str(page["generated_at"])),
            TOKEN_VERSION: html_escape(version),
            TOKEN_STYLE: style,
            TOKEN_SCRIPT: script,
            TOKEN_DATA: _json_for_script(page),
        })
        path = out_dir / filename
        atomic_write_text(path, html_text)
        written.append(path)
    return written


def render_prototype(
    spec: dict[str, Any],
    out_path: Path,
    *,
    template_dir: Path,
    version: str = "0.1.0",
) -> Path:
    ensure_dir(out_path.parent)
    template = _read(template_dir / "prototype.html")
    style = f"{_read(template_dir / 'base.css')}\n{_read(template_dir / 'prototype.css')}"
    script = f"{_read(template_dir / 'review.js')}\n{_read(template_dir / 'prototype.js')}"
    project = spec.get("project", {})
    title = f"设计原型 · {project.get('name', '')}".strip(" ·")
    page = {
        "kind": "prototype",
        "title": title,
        "project": project,
        "data": spec,
        "generated_at": project.get("generated_at") or now_iso(),
        "version": version,
    }
    html_text = _inject(template, {
        TOKEN_TITLE: html_escape(title),
        TOKEN_KIND: "prototype",
        TOKEN_PROJECT: html_escape(str(project.get("name", ""))),
        TOKEN_GENERATED: html_escape(str(page["generated_at"])),
        TOKEN_VERSION: html_escape(version),
        TOKEN_STYLE: style,
        TOKEN_SCRIPT: script,
        TOKEN_DATA: _json_for_script(page),
    })
    atomic_write_text(out_path, html_text)
    return out_path


def describe_output(path: Path) -> dict[str, Any]:
    size = path.stat().st_size if path.exists() else 0
    return {
        "path": str(path),
        "bytes": size,
        "sha256": sha256_text(path.read_text(encoding="utf-8"))[:16] if path.exists() else "",
    }
