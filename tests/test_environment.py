from __future__ import annotations

import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".tmp-tests"
TEST_TMP.mkdir(exist_ok=True)
SCRIPTS = ROOT / "skills" / "programmer-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib import environment  # noqa: E402
from lib.memory import MemoryStore  # noqa: E402


class EnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP / ("env-" + uuid.uuid4().hex)
        self.tmp.mkdir()
        self.workspace = self.tmp / "workspace"
        self.workspace.mkdir()
        self.env = {}
        for key in ("PROGRAMMER_WORKFLOW_HOST", "PROGRAMMER_WORKFLOW_GLOBAL", "PROGRAMMER_WORKFLOW_HOME", "DSH_HOME"):
            self.env[key] = os.environ.get(key)
            os.environ.pop(key, None)
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "dsh"
        os.environ["DSH_HOME"] = str(self.tmp / "dsh-home")

    def tearDown(self) -> None:
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_probe_and_command_check(self) -> None:
        cache = environment.probe(self.workspace)
        self.assertEqual(cache["os"], environment.local_os())
        self.assertIn("commands", cache)
        self.assertTrue(cache["probedAt"])
        self.assertEqual(cache["recognition"], "model")
        self.assertNotIn("ocr", cache)
        self.assertNotIn("tesseract", cache["commands"])
        found = environment.check_command("python", self.workspace)
        self.assertTrue(found["found"], found)
        missing = environment.check_command("definitely-not-a-real-command-pwf", self.workspace)
        self.assertFalse(missing["found"])
        self.assertIn("未在 PATH", missing["hint"])

    def test_cross_os_target_refuses(self) -> None:
        other = "linux" if environment.local_os() != "linux" else "windows"
        with self.assertRaises(environment.CrossOsTargetError):
            environment.assert_local_target(other)
        environment.assert_local_target(environment.local_os())
        result = environment.check_command("python", self.workspace, target_os=other)
        self.assertTrue(result.get("deferred"))
        self.assertEqual(result.get("targetOs"), other)

    def test_cache_and_active_memory_entry(self) -> None:
        cache, probed = environment.ensure_cached(self.workspace, force=True, record=True)
        self.assertTrue(probed)
        self.assertTrue(environment.workspace_cache_path(self.workspace).is_file())
        store = MemoryStore("workspace", workspace=self.workspace)
        entries = [e for e in store.entries(status="active") if "environment-probe" in (e.get("tags") or [])]
        self.assertEqual(len(entries), 1, entries)
        first_id = entries[0]["id"]
        again, probed_again = environment.ensure_cached(self.workspace, record=True)
        self.assertFalse(probed_again)
        entries = [e for e in store.entries(status="active") if "environment-probe" in (e.get("tags") or [])]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], first_id)
        self.assertIn("ENVIRONMENT", environment.boot_line(again, self.workspace))


if __name__ == "__main__":
    unittest.main()
