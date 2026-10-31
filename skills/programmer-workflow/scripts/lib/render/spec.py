"""Normalization and validation for the HTML specs.

The schema is intentionally forgiving: the agent supplies evidence-rich JSON and
the renderer fills safe defaults. Errors are actionable because a wrong spec
should fail before any file is written.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..common import now_iso, sha256_text

STATUSES = {"implemented", "partial", "planned"}
SEVERITIES = {"high", "medium", "low"}
CONFIDENCE = {"high", "medium", "low"}
DEVICES = {"desktop", "tablet", "mobile"}


class SpecError(ValueError):
    pass


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_dict(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SpecError(f"{field} must be an object")
    return value


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _confidence(value: Any) -> str:
    value = _str(value, "medium").lower()
    return value if value in CONFIDENCE else "medium"


def _project(data: dict[str, Any], kind: str) -> dict[str, Any]:
    project = _as_dict(data.get("project"), "project")
    name = _str(project.get("name"), "未命名工程")
    return {
        "name": name,
        "tagline": _str(project.get("tagline"), ""),
        "summary": _str(project.get("summary"), ""),
        "version": _str(project.get("version"), ""),
        "commit": _str(project.get("commit"), ""),
        "generated_at": _str(project.get("generated_at"), now_iso()),
        "language": _str(project.get("language"), "zh-CN") or "zh-CN",
        "confidence": _confidence(project.get("confidence")),
        "scope": [str(x) for x in _as_list(project.get("scope"))][:20],
        "source": _str(project.get("source"), ""),
        "kind": kind,
    }


def _items(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = data.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError(f"{key} must be an array")
    if not all(isinstance(item, dict) for item in raw):
        raise SpecError(f"every item in {key} must be an object")
    return raw


def _require_id(item: dict[str, Any], key: str, index: int) -> str:
    value = _str(item.get("id"), "").strip()
    if not value:
        value = f"{key}-{index + 1}"
    if not re.match(r"^[A-Za-z0-9_.:-]+$", value):
        raise SpecError(f"{key}[{index}].id contains unsupported characters: {value!r}")
    return value


def _dedupe_ids(items: list[dict[str, Any]], field: str, label: str) -> None:
    seen = set()
    for item in items:
        value = item.get(field)
        if value in seen:
            raise SpecError(f"duplicate {label} id: {value}")
        seen.add(value)


def normalize_architecture(data: dict[str, Any]) -> dict[str, Any]:
    data = _as_dict(data, "architecture")
    project = _project({**data, "project": data.get("project")}, "architecture")
    layers = []
    for i, layer in enumerate(_items(data, "layers")):
        layers.append({
            "id": _require_id(layer, "layer", i),
            "name": _str(layer.get("name"), f"层 {i + 1}"),
            "description": _str(layer.get("description"), ""),
        })
    _dedupe_ids(layers, "id", "layer")
    modules = []
    for i, module in enumerate(_items(data, "modules")):
        path = _str(module.get("path"), "")
        modules.append({
            "id": _require_id(module, "module", i),
            "name": _str(module.get("name"), path or f"模块 {i + 1}"),
            "layer": _str(module.get("layer"), ""),
            "path": path,
            "role": _str(module.get("role"), ""),
            "responsibilities": [str(x) for x in _as_list(module.get("responsibilities"))][:12],
            "key_files": [
                {"path": _str(item.get("path"), ""), "purpose": _str(item.get("purpose"), "")}
                for item in _as_list(module.get("key_files")) if isinstance(item, dict)
            ][:15],
            "depends_on": [str(x) for x in _as_list(module.get("depends_on"))][:20],
            "used_by": [str(x) for x in _as_list(module.get("used_by"))][:20],
            "evidence": [str(x) for x in _as_list(module.get("evidence"))][:12],
            "confidence": _confidence(module.get("confidence")),
            "notes": _str(module.get("notes"), ""),
        })
    _dedupe_ids(modules, "id", "module")
    module_ids = {m["id"] for m in modules}
    for module in modules:
        module["depends_on"] = [d for d in module["depends_on"] if d in module_ids and d != module["id"]]
        module["used_by"] = [d for d in module["used_by"] if d in module_ids]
    flows = []
    for i, flow in enumerate(_items(data, "flows")):
        steps = []
        for step in _as_list(flow.get("steps")):
            if isinstance(step, dict):
                steps.append({
                    "actor": _str(step.get("actor"), "Agent"),
                    "action": _str(step.get("action"), ""),
                    "target": _str(step.get("target"), ""),
                    "detail": _str(step.get("detail"), ""),
                    "evidence": _str(step.get("evidence"), ""),
                })
            elif isinstance(step, str):
                steps.append({"actor": "", "action": step, "target": "", "detail": "", "evidence": ""})
        flows.append({
            "id": _require_id(flow, "flow", i),
            "name": _str(flow.get("name"), f"流程 {i + 1}"),
            "summary": _str(flow.get("summary"), ""),
            "steps": steps[:30],
            "artifacts": [str(x) for x in _as_list(flow.get("artifacts"))][:15],
            "failure_modes": [str(x) for x in _as_list(flow.get("failure_modes"))][:10],
        })
    _dedupe_ids(flows, "id", "flow")
    decisions = []
    for i, item in enumerate(_items(data, "decisions")):
        decisions.append({
            "id": _require_id(item, "decision", i),
            "title": _str(item.get("title"), f"决策 {i + 1}"),
            "choice": _str(item.get("choice"), ""),
            "why": [str(x) for x in _as_list(item.get("why"))][:12],
            "tradeoffs": [str(x) for x in _as_list(item.get("tradeoffs"))][:12],
            "alternatives": [str(x) for x in _as_list(item.get("alternatives"))][:12],
            "evidence": [str(x) for x in _as_list(item.get("evidence"))][:12],
            "status": _str(item.get("status"), "accepted"),
        })
    _dedupe_ids(decisions, "id", "decision")
    risks = []
    for i, item in enumerate(_items(data, "risks")):
        severity = _str(item.get("severity"), "medium").lower()
        risks.append({
            "id": _require_id(item, "risk", i),
            "title": _str(item.get("title"), f"风险 {i + 1}"),
            "severity": severity if severity in SEVERITIES else "medium",
            "impact": _str(item.get("impact"), ""),
            "likelihood": _str(item.get("likelihood"), ""),
            "mitigation": _str(item.get("mitigation"), ""),
            "owner": _str(item.get("owner"), ""),
            "evidence": [str(x) for x in _as_list(item.get("evidence"))][:10],
        })
    _dedupe_ids(risks, "id", "risk")
    questions = []
    for i, item in enumerate(_items(data, "questions")):
        questions.append({
            "id": _require_id(item, "question", i),
            "question": _str(item.get("question"), ""),
            "why": _str(item.get("why"), ""),
            "default": _str(item.get("default"), ""),
        })
    file_index = []
    for item in _items(data, "file_index"):
        file_index.append({
            "path": _str(item.get("path"), ""),
            "module": _str(item.get("module"), ""),
            "purpose": _str(item.get("purpose"), ""),
            "lines": int(item.get("lines") or 0),
        })
    glossary = [
        {"term": _str(item.get("term"), ""), "definition": _str(item.get("definition"), "")}
        for item in _items(data, "glossary")
    ]
    stats = _as_dict(data.get("stats"), "stats")
    normalized = {
        "schema": 1,
        "kind": "architecture",
        "project": project,
        "stats": {
            "modules": len(modules),
            "flows": len(flows),
            "decisions": len(decisions),
            "risks": len(risks),
            "files": int(stats.get("files") or len(file_index)),
            "loc": int(stats.get("loc") or 0),
            "questions": len(questions),
        },
        "stack": [
            {
                "name": _str(item.get("name"), ""),
                "version": _str(item.get("version"), ""),
                "role": _str(item.get("role"), ""),
                "evidence": _str(item.get("evidence"), ""),
            }
            for item in _items(data, "stack")
        ][:30],
        "layers": layers,
        "modules": modules,
        "flows": flows,
        "decisions": decisions,
        "risks": risks,
        "questions": questions,
        "file_index": file_index[:300],
        "glossary": glossary[:40],
    }
    if not normalized["modules"]:
        raise SpecError("architecture.modules must contain at least one module")
    return normalized


def normalize_features(data: dict[str, Any]) -> dict[str, Any]:
    data = _as_dict(data, "features")
    project = _project({**data, "project": data.get("project")}, "features")
    domains = []
    for i, item in enumerate(_items(data, "domains")):
        domains.append({
            "id": _require_id(item, "domain", i),
            "name": _str(item.get("name"), f"领域 {i + 1}"),
            "description": _str(item.get("description"), ""),
        })
    _dedupe_ids(domains, "id", "domain")
    domain_ids = {d["id"] for d in domains}
    features = []
    for i, item in enumerate(_items(data, "features")):
        status = _str(item.get("status"), "implemented").lower()
        if status not in STATUSES:
            status = "partial"
        domain = _str(item.get("domain"), "")
        if domain and domain not in domain_ids:
            domains.append({"id": domain, "name": domain, "description": ""})
            domain_ids.add(domain)
        features.append({
            "id": _require_id(item, "feature", i),
            "name": _str(item.get("name"), f"功能 {i + 1}"),
            "domain": domain,
            "status": status,
            "priority": _str(item.get("priority"), ""),
            "summary": _str(item.get("summary"), ""),
            "user_value": _str(item.get("user_value"), ""),
            "entry_points": [str(x) for x in _as_list(item.get("entry_points"))][:15],
            "user_flow": [str(x) for x in _as_list(item.get("user_flow"))][:15],
            "inputs": [str(x) for x in _as_list(item.get("inputs"))][:10],
            "outputs": [str(x) for x in _as_list(item.get("outputs"))][:10],
            "dependencies": [str(x) for x in _as_list(item.get("dependencies"))][:15],
            "tests": [str(x) for x in _as_list(item.get("tests"))][:10],
            "evidence": [str(x) for x in _as_list(item.get("evidence"))][:12],
            "confidence": _confidence(item.get("confidence")),
            "notes": _str(item.get("notes"), ""),
        })
    _dedupe_ids(features, "id", "feature")
    feature_ids = {f["id"] for f in features}
    for feature in features:
        feature["dependencies"] = [d for d in feature["dependencies"] if d in feature_ids]
    journeys = []
    for i, item in enumerate(_items(data, "journeys")):
        journeys.append({
            "id": _require_id(item, "journey", i),
            "name": _str(item.get("name"), f"路径 {i + 1}"),
            "feature_ids": [x for x in _as_list(item.get("feature_ids")) if x in feature_ids],
            "steps": [str(x) for x in _as_list(item.get("steps"))][:20],
        })
    questions = []
    for i, item in enumerate(_items(data, "questions")):
        questions.append({
            "id": _require_id(item, "question", i),
            "question": _str(item.get("question"), ""),
            "why": _str(item.get("why"), ""),
            "default": _str(item.get("default"), ""),
        })
    return {
        "schema": 1,
        "kind": "features",
        "project": project,
        "stats": {
            "features": len(features),
            "domains": len(domains),
            "implemented": sum(1 for f in features if f["status"] == "implemented"),
            "partial": sum(1 for f in features if f["status"] == "partial"),
            "planned": sum(1 for f in features if f["status"] == "planned"),
            "questions": len(questions),
        },
        "domains": domains,
        "features": features,
        "journeys": journeys,
        "questions": questions,
        "glossary": [
            {"term": _str(item.get("term"), ""), "definition": _str(item.get("definition"), "")}
            for item in _items(data, "glossary")
        ][:40],
    }


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_IFRAME_RE = re.compile(r"<iframe\b[^>]*>.*?</iframe\s*>", re.IGNORECASE | re.DOTALL)
_EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URL_RE = re.compile(r"(href|src)\s*=\s*(['\"])\s*javascript:[^'\"]*\2", re.IGNORECASE)


def sanitize_html(html: str) -> str:
    """Keep static screen markup; remove scripts, iframes and inline event handlers."""
    html = _SCRIPT_RE.sub("", html or "")
    html = _IFRAME_RE.sub("", html)
    html = _EVENT_ATTR_RE.sub("", html)
    html = _JS_URL_RE.sub(r"\1=\2#\2", html)
    return html


def normalize_prototype(data: dict[str, Any]) -> dict[str, Any]:
    data = _as_dict(data, "prototype")
    project = _project({**data, "project": data.get("project")}, "prototype")
    directions = []
    for i, item in enumerate(_items(data, "directions")):
        screens = []
        for j, screen in enumerate(_as_list(item.get("screens"))):
            if not isinstance(screen, dict):
                raise SpecError(f"directions[{i}].screens[{j}] must be an object")
            device = _str(screen.get("device"), "desktop").lower()
            screens.append({
                "id": _require_id(screen, "screen", j),
                "name": _str(screen.get("name"), f"界面 {j + 1}"),
                "device": device if device in DEVICES else "desktop",
                "html": sanitize_html(_str(screen.get("html"), "")),
                "notes": [str(x) for x in _as_list(screen.get("notes"))][:10],
            })
        if not screens:
            raise SpecError(f"directions[{i}].screens must not be empty")
        directions.append({
            "id": _require_id(item, "direction", i),
            "name": _str(item.get("name"), f"方向 {i + 1}"),
            "thesis": _str(item.get("thesis"), ""),
            "when_to_use": _str(item.get("when_to_use"), ""),
            "palette": [
                {"name": _str(p.get("name"), ""), "hex": _str(p.get("hex"), "#888888"), "role": _str(p.get("role"), "")}
                for p in _as_list(item.get("palette")) if isinstance(p, dict)
            ][:16],
            "typography": [
                {
                    "name": _str(t.get("name"), ""),
                    "family": _str(t.get("family"), ""),
                    "size": _str(t.get("size"), ""),
                    "weight": _str(t.get("weight"), ""),
                }
                for t in _as_list(item.get("typography")) if isinstance(t, dict)
            ][:10],
            "screens": screens[:12],
            "components": [str(x) for x in _as_list(item.get("components"))][:20],
            "motion": _str(item.get("motion"), ""),
            "risks": [str(x) for x in _as_list(item.get("risks"))][:10],
        })
    if not directions:
        raise SpecError("prototype.directions must contain at least one direction")
    _dedupe_ids(directions, "id", "direction")
    brief = _as_dict(data.get("brief"), "brief")
    return {
        "schema": 1,
        "kind": "prototype",
        "project": project,
        "brief": {
            "goal": _str(brief.get("goal"), ""),
            "audience": _str(brief.get("audience"), ""),
            "platform": _str(brief.get("platform"), ""),
            "constraints": [str(x) for x in _as_list(brief.get("constraints"))][:15],
            "success_criteria": [str(x) for x in _as_list(brief.get("success_criteria"))][:15],
        },
        "assumptions": [str(x) for x in _as_list(data.get("assumptions"))][:20],
        "directions": directions,
        "questions": [
            {
                "id": _require_id(item, "question", i),
                "question": _str(item.get("question"), ""),
                "options": [str(x) for x in _as_list(item.get("options"))][:8],
                "default": _str(item.get("default"), ""),
            }
            for i, item in enumerate(_items(data, "questions"))
        ],
        "review_prompts": [str(x) for x in _as_list(data.get("review_prompts"))][:15],
    }


def attach_hash(spec: dict[str, Any]) -> dict[str, Any]:
    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    spec["spec_hash"] = sha256_text(canonical)[:16]
    return spec


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise SpecError(f"spec not found: {path}")
    except json.JSONDecodeError as exc:
        raise SpecError(f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}")
    if not isinstance(data, dict):
        raise SpecError(f"spec root must be an object: {path}")
    return data


def load_docs_specs(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    data = load_json(path)
    if "architecture" in data or "features" in data:
        arch_raw = data.get("architecture")
        feat_raw = data.get("features")
        if not isinstance(arch_raw, dict) or not isinstance(feat_raw, dict):
            raise SpecError("a combined spec needs both 'architecture' and 'features' objects")
    else:
        raise SpecError(
            "spec must contain 'architecture' and 'features' objects; "
            "or pass separate --architecture and --features files"
        )
    arch = attach_hash(normalize_architecture(arch_raw))
    feat = attach_hash(normalize_features(feat_raw))
    return arch, feat
