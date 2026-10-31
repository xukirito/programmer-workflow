from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".tmp-tests"
TEST_TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TMP)
SCRIPTS = ROOT / "skills" / "programmer-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib import debug  # noqa: E402
from lib import scan as scanlib  # noqa: E402
from lib import stall as stalllib  # noqa: E402
from lib.memory import MemoryDataError, MemoryStore, boot_payload, boot_text, text_boot_block  # noqa: E402
from lib.common import load_plugin_config, workspace_output_path, workspace_state  # noqa: E402
import companion  # noqa: E402


class TempCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP / ("case-" + uuid.uuid4().hex)
        self.tmp.mkdir()
        self.home = self.tmp / "home"
        self.ws = self.tmp / "workspace"
        self.ws.mkdir()
        self._old_home = os.environ.get("PROGRAMMER_WORKFLOW_HOME")
        os.environ["PROGRAMMER_WORKFLOW_HOME"] = str(self.home)
        self._old_global = os.environ.get("PROGRAMMER_WORKFLOW_GLOBAL")
        os.environ["PROGRAMMER_WORKFLOW_GLOBAL"] = str(self.home / "global")
        self._old_host = os.environ.get("PROGRAMMER_WORKFLOW_HOST")
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "dsh"
        self._old_legacy = os.environ.get("PROGRAMMER_WORKFLOW_LEGACY_HOME")
        os.environ["PROGRAMMER_WORKFLOW_LEGACY_HOME"] = str(self.tmp / "legacy-home")

    def tearDown(self) -> None:
        if self._old_legacy is None:
            os.environ.pop("PROGRAMMER_WORKFLOW_LEGACY_HOME", None)
        else:
            os.environ["PROGRAMMER_WORKFLOW_LEGACY_HOME"] = self._old_legacy
        if self._old_host is None:
            os.environ.pop("PROGRAMMER_WORKFLOW_HOST", None)
        else:
            os.environ["PROGRAMMER_WORKFLOW_HOST"] = self._old_host
        if self._old_home is None:
            os.environ.pop("PROGRAMMER_WORKFLOW_HOME", None)
        else:
            os.environ["PROGRAMMER_WORKFLOW_HOME"] = self._old_home
        if self._old_global is None:
            os.environ.pop("PROGRAMMER_WORKFLOW_GLOBAL", None)
        else:
            os.environ["PROGRAMMER_WORKFLOW_GLOBAL"] = self._old_global
        shutil.rmtree(self.tmp, ignore_errors=True)


class MemoryTests(TempCase):
    def test_approval_gate_and_boot(self) -> None:
        store = MemoryStore("user", home=self.home)
        store.ensure()
        proposed, created = store.add(
            kind="habit",
            text="先给结论，再展开证据。",
            evidence=["用户多次打断长回答"],
            confidence=0.9,
            status="proposed",
        )
        self.assertTrue(created)
        self.assertEqual(proposed["status"], "proposed")
        markdown = store.md_path.read_text(encoding="utf-8")
        self.assertIn("待审核", markdown)
        self.assertIn(proposed["text"], markdown)
        # Proposed entries are never rendered as rules in the boot block.
        self.assertNotIn(proposed["text"], text_boot_block(store))
        store.set_status([proposed["id"]], "active")
        self.assertIn(proposed["text"], text_boot_block(store))
        payload = boot_payload(self.ws)
        self.assertGreaterEqual(payload["user"]["counts"]["active"], 1)

    def test_dedupe_and_reject(self) -> None:
        store = MemoryStore("workspace", workspace=self.ws)
        store.ensure()
        one, _ = store.add(kind="convention", text="使用 pnpm。", status="proposed")
        two, created = store.add(kind="convention", text="使用  pnpm。", status="proposed")
        self.assertFalse(created)
        self.assertEqual(one["id"], two["id"])
        store.set_status([one["id"]], "rejected")
        self.assertEqual(store.entries(status="rejected")[0]["id"], one["id"])
        self.assertNotIn("使用 pnpm。", store.md_path.read_text(encoding="utf-8").split("## 生效中")[1].split("## 待审核")[0])

    def test_edit_and_forget(self) -> None:
        store = MemoryStore("workspace", workspace=self.ws)
        store.ensure()
        entry, _ = store.add(kind="fact", text="旧文本", status="active")
        store.edit(entry["id"], text="新文本", tags=["a", "b"])
        self.assertEqual(store.entries(status="active")[0]["text"], "新文本")
        store.delete([entry["id"]])
        self.assertEqual(store.entries(status="active"), [])

    def test_promote_is_proposed(self) -> None:
        user = MemoryStore("user", home=self.home)
        user.ensure()
        local = MemoryStore("workspace", workspace=self.ws)
        local.ensure()
        entry, _ = local.add(kind="convention", text="接口返回 snake_case。", status="active")
        copied = local.promote([entry["id"]], user)
        self.assertEqual(len(copied), 1)
        self.assertEqual(copied[0]["status"], "proposed")
        self.assertEqual(copied[0]["source"], "promotion")

    def test_corrupt_memory_does_not_overwrite(self) -> None:
        store = MemoryStore("workspace", workspace=self.ws)
        store.json_path.parent.mkdir(parents=True, exist_ok=True)
        store.json_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(MemoryDataError):
            store.load()
        self.assertEqual(store.json_path.read_text(encoding="utf-8"), "{not json")

    def test_env_set_via_cli(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = companion.main(["env", "set", "--workspace", str(self.ws), "--dev-only", "--no-hardware", "--reason", "用户说明", "--json"])
        self.assertEqual(code, 0)
        store = MemoryStore("workspace", workspace=self.ws)
        entries = store.entries(status="active")
        self.assertTrue(any(e["kind"] == "environment" and "纯开发环境" in e["text"] for e in entries))
        payload = boot_payload(self.ws)
        self.assertTrue(any("没有可搭配的物理硬件" in e["text"] for e in payload["workspace_memory"]["entries"]))
        self.assertTrue(payload["workflow"]["devOnlyDirect"])

    def test_dev_only_requires_config_and_fact(self) -> None:
        store = MemoryStore("workspace", workspace=self.ws)
        store.ensure()
        store.add(kind="environment", text="纯开发环境，无硬件，直接加日志", status="active", source="user")
        global_dir = self.home / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "config.json").write_text(json.dumps({"devOnlyAutoInstrument": True}), encoding="utf-8")
        self.assertTrue(boot_payload(self.ws)["workflow"]["devOnlyDirect"])
        (global_dir / "config.json").write_text(json.dumps({"devOnlyAutoInstrument": False}), encoding="utf-8")
        self.assertFalse(boot_payload(self.ws)["workflow"]["devOnlyDirect"])
        self.assertIn("dev-only auto-instrument: disabled", boot_text(self.ws))


class ConfigTests(TempCase):
    def test_config_mirror(self) -> None:
        global_dir = self.home / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "config.json").write_text(json.dumps({
            "workspaceDataDir": ".pw-data",
            "debugLogDir": "dbg",
            "docsDir": "guide",
            "prototypeFile": "Mock.html",
            "satisfactionThreshold": 5,
            "bugfixThreshold": 4,
            "userMemoryEnabled": False,
            "planFormat": "html",
        }), encoding="utf-8")
        cfg = load_plugin_config(self.ws)
        self.assertEqual(cfg["workspaceDataDir"], ".pw-data")
        self.assertEqual(cfg["debugLogDir"], "dbg")
        self.assertEqual(cfg["docsDir"], "guide")
        self.assertEqual(cfg["satisfactionThreshold"], 5)
        self.assertEqual(cfg["bugfixThreshold"], 4)
        self.assertFalse(cfg["userMemoryEnabled"])
        self.assertEqual(cfg["planFormat"], "html")
        self.assertEqual(workspace_state(self.ws), (self.ws / ".pw-data").resolve())

    def test_workflow_mode_defaults_and_safe_migration(self) -> None:
        global_dir = self.home / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "config.json").write_text(json.dumps({
            "requireRunConsent": False,
        }), encoding="utf-8")
        cfg = load_plugin_config(self.ws)
        self.assertEqual(cfg["workflowMode"], "plan")
        (global_dir / "config.json").write_text(json.dumps({"workflowMode": "bogus"}), encoding="utf-8")
        self.assertEqual(load_plugin_config(self.ws)["workflowMode"], "plan")
        (global_dir / "config.json").write_text(json.dumps({"workflowMode": "full-authority"}), encoding="utf-8")
        self.assertEqual(load_plugin_config(self.ws)["workflowMode"], "full-authority")

    def test_boot_exposes_workflow_and_dev_only_policy(self) -> None:
        global_dir = self.home / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "config.json").write_text(json.dumps({
            "workflowMode": "full-authority",
            "devOnlyAutoInstrument": False,
            "planFormat": "html",
        }), encoding="utf-8")
        payload = boot_payload(self.ws)
        self.assertEqual(payload["workflow"]["mode"], "full-authority")
        self.assertEqual(payload["workflow"]["planFormat"], "html")
        self.assertFalse(payload["workflow"]["devOnlyDirect"])
        self.assertIn("dev-only auto-instrument: disabled", boot_text(self.ws))

    def test_path_safety(self) -> None:
        global_dir = self.home / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "config.json").write_text(json.dumps({
            "workspaceDataDir": "C:\\temp\\escape",
            "debugLogDir": "../outside",
            "docsDir": "docs/ok",
            "prototypeFile": "/absolute.html",
        }), encoding="utf-8")
        cfg = load_plugin_config(self.ws)
        self.assertEqual(cfg["workspaceDataDir"], ".programmer-workflow")
        self.assertEqual(cfg["debugLogDir"], "debug-logs")
        self.assertEqual(cfg["docsDir"], "docs/ok")
        self.assertEqual(cfg["prototypeFile"], "Prototype.html")
        self.assertTrue(str(workspace_state(self.ws)).startswith(str(self.ws)))


class PathOutputTests(TempCase):
    def test_output_path_rejects_absolute_and_parent(self) -> None:
        with self.assertRaises(ValueError):
            workspace_output_path(self.ws, str(self.tmp / "outside.html"), "Prototype.html")
        with self.assertRaises(ValueError):
            workspace_output_path(self.ws, "../outside.html", "Prototype.html")
        self.assertEqual(workspace_output_path(self.ws, "design/Prototype.html", "Prototype.html"), (self.ws / "design" / "Prototype.html").resolve())

    def test_plan_cli_rejects_escape(self) -> None:
        spec = self.ws / "plan.json"
        spec.write_text(json.dumps({"title": "T", "goal": "G", "steps": [{"title": "S", "change": "C"}]}), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = companion.main(["plan", "--host", "dsh", "--workspace", str(self.ws), "--spec", str(spec), "--out", "../escape.md"])
        self.assertEqual(code, 2)
        self.assertIn("must not contain", out.getvalue())


class ScanTests(TempCase):
    def test_style_and_project_map(self) -> None:
        (self.ws / ".editorconfig").write_text("root = true\n[*]\nindent_style = space\nindent_size = 4\n", encoding="utf-8")
        (self.ws / "README.md").write_text("# 示例工程\n\n这是一个中文项目。\n", encoding="utf-8")
        (self.ws / "src").mkdir()
        (self.ws / "src" / "main.py").write_text(
            "def main():\n    value = 1\n    if value:\n        return value\n    return 0\n",
            encoding="utf-8",
        )
        (self.ws / "tests").mkdir()
        (self.ws / "tests" / "test_main.py").write_text("def test_main():\n    pass\n", encoding="utf-8")
        (self.ws / "package.json").write_text(json.dumps({"name": "demo", "scripts": {"test": "pytest"}}), encoding="utf-8")
        result = scanlib.scan_project(self.ws, home=self.home)
        self.assertEqual(result["kind"], "habit-scan")
        self.assertEqual(result["style"]["indentation"]["dominant"], "4 spaces")
        self.assertEqual(result["docs"]["readme_language"], "中文")
        self.assertFalse(result["transcripts"]["enabled"])
        self.assertTrue(any(item["path"] == ".editorconfig" for item in result["tooling"]))
        project = scanlib.project_map(self.ws)
        self.assertEqual(project["kind"], "project-map")
        self.assertTrue(any(m["name"] == "src" for m in project["modules"]))
        self.assertTrue(any(e["path"] == "src/main.py" for e in project["entry_candidates"]))
        self.assertGreaterEqual(project["tests"]["test_files"], 1)

    def test_hardware_hint(self) -> None:
        (self.ws / "platformio.ini").write_text("[env:board]\nplatform = ststm32\n", encoding="utf-8")
        facts = scanlib.env_facts(self.ws)
        self.assertTrue(facts["hardware"]["likely_hardware"])


class StallTests(TempCase):
    def test_threshold_and_reset(self) -> None:
        with mock.patch.dict(os.environ, {"DSH_SESSION_ID": "test-session"}):
            stalllib.reset(workspace=self.ws)
            self.assertFalse(stalllib.status("satisfaction", workspace=self.ws)["triggered"])
            stalllib.bump("satisfaction", workspace=self.ws)
            stalllib.bump("satisfaction", workspace=self.ws)
            self.assertFalse(stalllib.status("satisfaction", workspace=self.ws)["triggered"])
            stalllib.bump("satisfaction", workspace=self.ws)
            self.assertTrue(stalllib.status("satisfaction", workspace=self.ws)["triggered"])
            stalllib.reset(workspace=self.ws)
            self.assertFalse(stalllib.status("satisfaction", workspace=self.ws)["triggered"])

    def test_bugfix_threshold(self) -> None:
        with mock.patch.dict(os.environ, {"DSH_SESSION_ID": "bug-session"}):
            stalllib.reset(workspace=self.ws)
            stalllib.bump("bugfix", workspace=self.ws)
            self.assertFalse(stalllib.status("bugfix", workspace=self.ws)["triggered"])
            stalllib.bump("bugfix", workspace=self.ws)
            self.assertTrue(stalllib.status("bugfix", workspace=self.ws)["triggered"])


class DebugTests(TempCase):
    def test_run_and_triage(self) -> None:
        target = self.ws / "target.py"
        target.write_text(
            'import sys\nprint("INFO starting")\nprint("ERROR: boom")\nsys.exit(3)\n',
            encoding="utf-8",
        )
        result = debug.run_command(
            self.ws,
            [sys.executable, str(target)],
            label="repro",
            timeout=15,
            assume_yes=True,
        )
        self.assertEqual(result["exit_code"], 3)
        self.assertFalse(result["timed_out"])
        log = Path(result["log"])
        self.assertTrue(log.exists())
        report = debug.triage_log(log)
        self.assertGreaterEqual(report["signature_count"], 1)
        self.assertTrue(report["hypotheses"])
        out = debug.write_triage(log, report)
        self.assertTrue(out.exists())
        self.assertIn("日志分诊报告", out.read_text(encoding="utf-8"))

    def test_timeout_kills(self) -> None:
        result = debug.run_command(
            self.ws,
            [sys.executable, "-c", "import time; time.sleep(10)"],
            label="timeout",
            timeout=1,
            assume_yes=True,
        )
        self.assertTrue(result["timed_out"])
        self.assertLess(result["duration_seconds"], 8)
        self.assertIsNotNone(result["exit_code"])

    def test_consent_required(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(debug.ConsentRequiredError):
                debug.run_command(self.ws, [sys.executable, "-c", "print(1)"], assume_yes=False)

    def test_full_authority_config_skips_consent(self) -> None:
        global_dir = self.home / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "config.json").write_text(json.dumps({"workflowMode": "full-authority"}), encoding="utf-8")
        result = debug.run_command(self.ws, [sys.executable, "-c", "print(1)"], assume_yes=False)
        self.assertEqual(result["exit_code"], 0)

    def test_both_authority_flags_rejected(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = companion.main([
                "run", "--host", "dsh", "--workspace", str(self.ws),
                "--yes", "--full-authority", "--", sys.executable, "-c", "print(1)",
            ])
        self.assertEqual(code, 2)
        self.assertIn("mutually exclusive", out.getvalue())

    def test_full_authority_bypasses_plan_consent(self) -> None:
        result = debug.run_command(
            self.ws,
            [sys.executable, "-c", "print(1)"],
            assume_yes=False,
            full_authority=True,
        )
        self.assertEqual(result["exit_code"], 0)

    def test_destructive_guard(self) -> None:
        with self.assertRaises(debug.DestructiveCommandError):
            debug.run_command(self.ws, ["rm", "-rf", "/"], assume_yes=True)

    def test_shell_preserves_argv_and_quotes(self) -> None:
        result = debug.run_command(
            self.ws, ["echo", "hello world"], shell=True, assume_yes=True, timeout=10,
        )
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello world", "\n".join(result["tail"]))
        self.assertEqual(result["command"], "echo \"hello world\"" if os.name == "nt" else "echo 'hello world'")

    def test_shell_timeout_and_full_authority(self) -> None:
        result = debug.run_command(
            self.ws,
            [sys.executable, "-c", "import time; time.sleep(5)"],
            shell=True, full_authority=True, timeout=1,
        )
        self.assertTrue(result["timed_out"])
        self.assertIn("time.sleep(5)", result["command"])
        self.assertFalse(result["command"].strip().startswith("["))


class CliSmokeTests(TempCase):
    def test_boot_and_doctor(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = companion.main(["boot", "--workspace", str(self.ws), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["tool"], "programmer-workflow")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = companion.main(["doctor", "--workspace", str(self.ws), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])

    def test_docs_check_and_prototype_check(self) -> None:
        spec = self.tmp / "spec.json"
        data = {
            "architecture": {
                "project": {"name": "Demo"},
                "modules": [{"id": "m1", "name": "M1", "path": "m1.py", "role": "demo"}],
            },
            "features": {
                "project": {"name": "Demo"},
                "domains": [{"id": "d1", "name": "D1"}],
                "features": [{"id": "f1", "name": "F1", "domain": "d1", "status": "implemented"}],
            },
        }
        spec.write_text(json.dumps(data), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = companion.main(["docs", "--host", "dsh", "--workspace", str(self.ws), "--spec", str(spec), "--out", "docs", "--check", "--json"])
        self.assertEqual(code, 0)
        proto = self.tmp / "proto.json"
        proto.write_text(json.dumps({
            "project": {"name": "Demo"},
            "directions": [{
                "id": "A", "name": "A", "thesis": "t",
                "screens": [{"id": "home", "name": "Home", "device": "desktop", "html": "<div>hi</div>", "notes": []}],
            }],
        }), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = companion.main(["prototype", "--host", "dsh", "--workspace", str(self.ws), "--spec", str(proto), "--out", "P.html", "--check", "--json"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
