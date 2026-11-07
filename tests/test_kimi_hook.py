from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".tmp-tests"
TEST_TMP.mkdir(exist_ok=True)
HOOK_PATH = ROOT / "scripts" / "kimi_settings_hook.py"
SPEC = importlib.util.spec_from_file_location("kimi_settings_hook", HOOK_PATH)
assert SPEC is not None and SPEC.loader is not None
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


class KimiSettingsHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = TEST_TMP / ("hook-" + uuid.uuid4().hex)
        self.workspace.mkdir()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_existing_server_is_reused_without_spawning(self) -> None:
        with mock.patch.object(hook, "_read_payload", return_value={}), \
             mock.patch.object(hook, "_server_ready", return_value=True), \
             mock.patch.object(hook.subprocess, "Popen") as popen:
            self.assertEqual(hook.main(), 0)
        popen.assert_not_called()

    def test_hook_payload_workspace_is_passed_to_detached_server(self) -> None:
        payload = {"hook_event_name": "SessionStart", "cwd": str(self.workspace)}
        with mock.patch.object(hook, "_read_payload", return_value=payload), \
             mock.patch.object(hook, "_server_ready", side_effect=[False, True]), \
             mock.patch.object(hook.subprocess, "Popen") as popen:
            self.assertEqual(hook.main(), 0)
        command = popen.call_args[0][0]
        kwargs = popen.call_args[1]
        self.assertEqual(command[command.index("--workspace") + 1], str(self.workspace.resolve()))
        self.assertEqual(kwargs["cwd"], str(self.workspace.resolve()))
        self.assertEqual(kwargs["stdout"], hook.subprocess.DEVNULL)
        self.assertNotIn("--open", command)

    def test_payload_parser_ignores_invalid_input(self) -> None:
        with mock.patch.object(hook.sys, "stdin", io.StringIO("not-json")):
            self.assertEqual(hook._read_payload(), {})
        with mock.patch.object(hook.sys, "stdin", io.StringIO(json.dumps({"cwd": "ok"}))):
            self.assertEqual(hook._read_payload(), {"cwd": "ok"})


if __name__ == "__main__":
    unittest.main()
