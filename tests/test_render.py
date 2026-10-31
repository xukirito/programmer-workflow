from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".tmp-tests"
TEST_TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TMP)
SCRIPTS = ROOT / "skills" / "programmer-workflow" / "scripts"
TEMPLATES = ROOT / "skills" / "programmer-workflow" / "templates"
sys.path.insert(0, str(SCRIPTS))

from lib.render import pages as pagelib  # noqa: E402
from lib.render import spec as speclib  # noqa: E402


def minimal_arch() -> dict:
    return {
        "project": {"name": "Demo", "summary": "A demo project.", "confidence": "high"},
        "stack": [{"name": "Python", "version": "3.12", "role": "runtime"}],
        "layers": [{"id": "core", "name": "Core", "description": "core modules"}],
        "modules": [{
            "id": "core",
            "name": "Core",
            "layer": "core",
            "path": "src/core.py",
            "role": "does core things",
            "key_files": [{"path": "src/core.py", "purpose": "core"}],
            "evidence": ["src/core.py"],
        }],
        "flows": [{
            "id": "run",
            "name": "Run",
            "summary": "run it",
            "steps": [{"actor": "User", "action": "invoke", "target": "core"}],
        }],
        "decisions": [{"id": "d1", "title": "Use Python", "choice": "Python", "why": ["simple"]}],
        "risks": [{"id": "r1", "title": "None", "severity": "low", "impact": "none", "mitigation": "none"}],
        "questions": [{"id": "q1", "question": "Scope?", "default": "all"}],
        "file_index": [{"path": "src/core.py", "module": "core", "purpose": "core"}],
        "glossary": [{"term": "core", "definition": "the core"}],
    }


def minimal_features() -> dict:
    return {
        "project": {"name": "Demo", "summary": "A demo project.", "confidence": "high"},
        "domains": [{"id": "core", "name": "Core", "description": "core features"}],
        "features": [{
            "id": "f1",
            "name": "Run",
            "domain": "core",
            "status": "implemented",
            "summary": "runs",
            "entry_points": ["src/core.py"],
            "tests": ["tests/test_core.py"],
            "evidence": ["src/core.py"],
        }],
        "journeys": [{"id": "j1", "name": "First run", "feature_ids": ["f1"], "steps": ["invoke"]}],
        "questions": [],
        "glossary": [],
    }


class SpecTests(unittest.TestCase):
    def test_sanitize_html(self) -> None:
        dirty = '<div onclick="evil()"><script>alert(1)</script><iframe src="x"></iframe>' \
                '<a href="javascript:alert(1)">x</a><img src=x onerror=alert(1)></div>'
        clean = speclib.sanitize_html(dirty)
        self.assertNotIn("<script", clean.lower())
        self.assertNotIn("<iframe", clean.lower())
        self.assertNotIn("onclick", clean.lower())
        self.assertNotIn("onerror", clean.lower())
        self.assertNotIn("javascript:", clean.lower())

    def test_duplicate_module_id_rejected(self) -> None:
        data = minimal_arch()
        data["modules"].append(dict(data["modules"][0]))
        with self.assertRaises(speclib.SpecError):
            speclib.normalize_architecture(data)

    def test_dangling_dependencies_dropped(self) -> None:
        data = minimal_arch()
        data["modules"][0]["depends_on"] = ["missing", "core"]
        normalized = speclib.normalize_architecture(data)
        self.assertEqual(normalized["modules"][0]["depends_on"], [])

    def test_defaults_for_minimal_prototype(self) -> None:
        data = {
            "project": {"name": "Demo"},
            "directions": [{
                "id": "A", "name": "A",
                "screens": [{"id": "s1", "name": "S1", "device": "mobile", "html": "<b>hi</b>"}],
            }],
        }
        normalized = speclib.normalize_prototype(data)
        self.assertEqual(normalized["directions"][0]["screens"][0]["device"], "mobile")
        self.assertEqual(normalized["directions"][0]["screens"][0]["html"], "<b>hi</b>")


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP / ("render-" + uuid.uuid4().hex)
        self.tmp.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_docs_render(self) -> None:
        arch = speclib.attach_hash(speclib.normalize_architecture(minimal_arch()))
        feats = speclib.attach_hash(speclib.normalize_features(minimal_features()))
        paths = pagelib.render_docs(arch, feats, self.tmp, template_dir=TEMPLATES)
        self.assertEqual([p.name for p in paths], ["Architecture.html", "Features.html"])
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("{{WC_", text)
            self.assertNotIn("<script src=", text)
            self.assertNotIn("https://", text)
            match = re.search(r'<script id="wc-data" type="application/json">(.*?)</script>', text, re.S)
            self.assertIsNotNone(match)
            payload = json.loads(match.group(1))
            self.assertIn(payload["data"]["kind"], ("architecture", "features"))
            script = re.search(r"<script>\s*(.*?)\s*</script>", text, re.S)
            self.assertIsNotNone(script)
            js_path = self.tmp / "inline.js"
            js_path.write_text(script.group(1), encoding="utf-8")
            node = shutil.which("node") or os.environ.get("WC_NODE")
            if node:
                proc = subprocess.run([node, "--check", str(js_path)], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_prototype_render_and_sanitize(self) -> None:
        data = {
            "project": {"name": "Demo", "summary": "x"},
            "directions": [{
                "id": "A", "name": "Direction A", "thesis": "test",
                "palette": [{"name": "Ink", "hex": "#111111"}],
                "screens": [{
                    "id": "home", "name": "Home", "device": "desktop",
                    "html": '<script>alert(1)</script><div onclick="x()">Hello</div>',
                }],
            }],
        }
        spec = speclib.attach_hash(speclib.normalize_prototype(data))
        out = self.tmp / "Prototype.html"
        pagelib.render_prototype(spec, out, template_dir=TEMPLATES)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertNotIn("onclick=", text)
        match = re.search(r'<script id="wc-data" type="application/json">(.*?)</script>', text, re.S)
        payload = json.loads(match.group(1))
        self.assertEqual(payload["data"]["kind"], "prototype")
        self.assertIn("Hello", payload["data"]["directions"][0]["screens"][0]["html"])

    def test_render_docs_with_missing_template(self) -> None:
        arch = speclib.attach_hash(speclib.normalize_architecture(minimal_arch()))
        feats = speclib.attach_hash(speclib.normalize_features(minimal_features()))
        with self.assertRaises(FileNotFoundError):
            pagelib.render_docs(arch, feats, self.tmp, template_dir=self.tmp / "nope")


if __name__ == "__main__":
    unittest.main()
