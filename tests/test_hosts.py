from __future__ import annotations

import json
import os
import shutil
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
sys.path.insert(0, str(SCRIPTS))

from lib import hosts  # noqa: E402
from lib.common import global_root, load_plugin_config, user_home  # noqa: E402
from lib.memory import MemoryStore  # noqa: E402


class HostIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP / ("hosts-" + uuid.uuid4().hex)
        self.tmp.mkdir()
        self.ws = self.tmp / "workspace"
        self.ws.mkdir()
        self.env = {}
        for key in ("PROGRAMMER_WORKFLOW_HOST", "PROGRAMMER_WORKFLOW_GLOBAL",
                    "PROGRAMMER_WORKFLOW_HOME", "PROGRAMMER_WORKFLOW_LEGACY_HOME",
                    "PROGRAMMER_WORKFLOW_CLI", "PROGRAMMER_WORKFLOW_SYSTEM_DRIVE",
                    "KIMI_MIGRATION_TOOLS", "DSH_HOME", "KIMI_HOME", "CODEBUDDY_HOME"):
            self.env[key] = os.environ.get(key)
            os.environ.pop(key, None)
        sandbox_drive = self.tmp.drive.upper()
        if sandbox_drive:
            os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = sandbox_drive
        self.env["PROGRAMMER_WORKFLOW_LEGACY_HOME"] = str(self.tmp / "legacy")
        os.environ["PROGRAMMER_WORKFLOW_LEGACY_HOME"] = str(self.tmp / "legacy")
        os.environ["DSH_HOME"] = str(self.tmp / "dsh-home")
        os.environ["KIMI_HOME"] = str(self.tmp / "kimi-home")
        os.environ["CODEBUDDY_HOME"] = str(self.tmp / "codebuddy-home")

    def tearDown(self) -> None:
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_roots_do_not_fall_back_to_dsh(self) -> None:
        self.assertEqual(hosts.resolve_host("dsh"), "dsh")
        self.assertEqual(hosts.plugin_root("dsh"), (self.tmp / "dsh-home" / "programmer-workflow").resolve())
        self.assertEqual(hosts.plugin_root("kimi"), (self.tmp / "kimi-home" / "programmer-workflow").resolve())
        self.assertEqual(hosts.plugin_root("codebuddy"), (self.tmp / "codebuddy-home" / "programmer-workflow").resolve())
        self.assertNotIn(".dsh", str(hosts.plugin_root("kimi")))
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        self.assertEqual(global_root(), (self.tmp / "kimi-home" / "programmer-workflow").resolve())
        self.assertNotEqual(global_root(), (self.tmp / "dsh-home" / "programmer-workflow").resolve())

    def test_unknown_host_requires_explicit_id(self) -> None:
        with self.assertRaises(hosts.HostResolutionError):
            hosts.resolve_host()
        with self.assertRaises(hosts.HostResolutionError):
            hosts.resolve_host("not-a-host")

    def test_config_and_memory_are_invisible_across_hosts(self) -> None:
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "dsh"
        dsh_root = global_root()
        dsh_root.mkdir(parents=True)
        (dsh_root / "config.json").write_text(json.dumps({"workflowMode": "full-authority"}), encoding="utf-8")
        dsh_store = MemoryStore("user")
        dsh_store.ensure()
        dsh_store.add(kind="habit", text="DSH only", status="active", source="user")
        self.assertEqual(load_plugin_config(self.ws)["workflowMode"], "full-authority")

        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        self.assertEqual(load_plugin_config(self.ws)["workflowMode"], "plan")
        kimi_store = MemoryStore("user")
        self.assertFalse(kimi_store.json_path.exists())
        kimi_store.ensure()
        self.assertFalse(any(e["text"] == "DSH only" for e in kimi_store.entries()))

        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "dsh"
        self.assertEqual([e["text"] for e in MemoryStore("user").entries()], ["DSH only"])

    def test_explicit_global_override_is_external(self) -> None:
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        external = self.tmp / "external-memory"
        os.environ["PROGRAMMER_WORKFLOW_GLOBAL"] = str(external)
        self.assertEqual(global_root(), external.resolve())
        info = hosts.external_overrides("kimi")
        self.assertTrue(info["pluginRootIsExternal"])
        self.assertEqual(info["globalOverride"], str(external.resolve()))
        self.assertNotIn(".dsh", str(user_home()))

    def test_programmer_workflow_home_is_exact_memory_override(self) -> None:
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        exact = self.tmp / "exact-memory"
        os.environ["PROGRAMMER_WORKFLOW_HOME"] = str(exact)
        self.assertEqual(user_home(), exact.resolve())
        info = hosts.external_overrides("kimi")
        self.assertTrue(info["memoryRootIsExternal"])

    def test_codebuddy_is_unavailable_until_its_cli_exists(self) -> None:
        capability = hosts.plugin_migration_capability("codebuddy")
        self.assertTrue(capability["supported"])
        self.assertFalse(capability["ready"], "CodeBuddy must not claim stage 1 without a CLI")
        self.assertIn("companion.py", capability["reason"])

        cli = hosts.host_home("codebuddy") / "skills" / "programmer-workflow" / "scripts" / "companion.py"
        cli.parent.mkdir(parents=True)
        cli.write_text("", encoding="utf-8")
        capability = hosts.plugin_migration_capability("codebuddy")
        self.assertTrue(capability["ready"])
        self.assertEqual(capability["cliPath"], str(cli.resolve()))

    def test_cli_override_serves_any_host(self) -> None:
        custom = self.tmp / "portable" / "companion.py"
        custom.parent.mkdir(parents=True)
        custom.write_text("", encoding="utf-8")
        os.environ["PROGRAMMER_WORKFLOW_CLI"] = str(custom)
        self.assertEqual(hosts.companion_cli("dsh"), custom.resolve())
        capability = hosts.plugin_migration_capability("cursor")
        self.assertTrue(capability["ready"])
        self.assertEqual(capability["cliPath"], str(custom.resolve()))
        self.assertIn("pluginMigrationReady", hosts.all_hosts()[0])

    def test_managed_plugin_cli_is_host_scoped(self) -> None:
        """A Kimi managed-plugin CLI may serve Kimi only, never another host."""
        managed = (
            self.tmp / "kimi-home" / "plugins" / "managed" / "programmer-workflow"
            / "skills" / "programmer-workflow" / "scripts" / "companion.py"
        )
        managed.parent.mkdir(parents=True)
        managed.write_text("# managed plugin copy", encoding="utf-8")
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        self.assertEqual(hosts.running_companion_cli(managed), managed.resolve())
        self.assertEqual(hosts.companion_cli("kimi", current=managed), managed.resolve())
        self.assertEqual(hosts.companion_cli("kimi"), None, "sys.argv is not companion.py in tests")

        old_argv = sys.argv
        try:
            sys.argv = [str(managed)]
            self.assertEqual(hosts.companion_cli("kimi"), managed.resolve())
            # The same running file must not be offered to DSH even though it is
            # a perfectly valid companion.py.
            os.environ["PROGRAMMER_WORKFLOW_HOST"] = "dsh"
            self.assertIsNone(hosts.companion_cli("dsh"))
            self.assertIsNone(hosts.companion_cli("codebuddy"))
        finally:
            sys.argv = old_argv

        # DSH's own installed CLI wins over the Kimi managed copy.
        dsh_cli = hosts.host_home("dsh") / "skills" / "programmer-workflow" / "scripts" / "companion.py"
        dsh_cli.parent.mkdir(parents=True)
        dsh_cli.write_text("# dsh copy", encoding="utf-8")
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        self.assertEqual(hosts.companion_cli("dsh", current=managed), dsh_cli.resolve())
        self.assertNotEqual(hosts.companion_cli("kimi", current=managed), dsh_cli.resolve())

    @unittest.skipUnless(os.environ.get("WC_NODE"), "Node is not configured (set WC_NODE)")
    def test_host_and_cli_resolve_the_same_override_roots(self) -> None:
        import subprocess

        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        os.environ["PROGRAMMER_WORKFLOW_GLOBAL"] = str(self.tmp / "global-override")
        os.environ["PROGRAMMER_WORKFLOW_HOME"] = str(self.tmp / "memory-override")
        # The Host plugin prepares the DSH layout when it loads; keep it in the
        # temporary home so no test ever writes into the real DSH data.
        child_env = dict(os.environ)
        child_env["DSH_HOME"] = str(self.tmp / "probe-dsh")
        child_env["CODEBUDDY_HOME"] = str(self.tmp / "probe-codebuddy")
        for host_id in ("kimi", "codebuddy"):
            # Write to a file instead of a PIPE: CPython 3.8's threaded
            # _communicate can raise IndexError for a large, fast-exiting child.
            out = self.tmp / f"probe-{host_id}.json"
            with out.open("w", encoding="utf-8") as handle:
                proc = subprocess.run(
                    [os.environ["WC_NODE"], str(ROOT / "tests" / "host_override_probe.mjs"), host_id],
                    cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT, text=True, timeout=60, env=child_env,
                )
            text = out.read_text(encoding="utf-8")
            self.assertEqual(proc.returncode, 0, text)
            payload = json.loads(text)
            self.assertEqual(Path(payload["paths"]["globalRoot"]).resolve(), hosts.plugin_root(host_id))
            self.assertEqual(Path(payload["paths"]["memory"]).resolve(), hosts.memory_root(host_id))
            self.assertEqual(Path(payload["pluginData"]["configPath"]).resolve(),
                             (hosts.plugin_root(host_id) / "config.json").resolve())
        self.assertFalse((self.tmp / "kimi-home" / "programmer-workflow").exists(), "no real host data is written")

    @unittest.skipUnless(os.environ.get("WC_NODE"), "Node is not configured (set WC_NODE)")
    def test_doctor_uses_host_registry_and_home_overrides(self) -> None:
        import subprocess

        kimi_skill = hosts.host_home("kimi") / "skills" / "programmer-workflow" / "SKILL.md"
        kimi_skill.parent.mkdir(parents=True)
        kimi_skill.write_text("---\nname: programmer-workflow\n---\n", encoding="utf-8")
        kimi_cli = kimi_skill.parent / "scripts" / "companion.py"
        kimi_cli.parent.mkdir(parents=True)
        kimi_cli.write_text("", encoding="utf-8")
        env = dict(os.environ)
        env["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        out = self.tmp / "doctor.json"
        with out.open("w", encoding="utf-8") as handle:
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "companion.py"), "doctor", "--host", "kimi",
                 "--workspace", str(self.ws), "--json"],
                cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT, text=True, timeout=120, env=env,
            )
        text = out.read_text(encoding="utf-8")
        self.assertIn(proc.returncode, (0, 1), text)
        payload = json.loads(text)
        self.assertTrue(payload["installed"]["kimi"], payload["installed"])
        self.assertTrue(payload["stage1Cli"]["kimi"]["ready"])
        self.assertFalse(payload["stage1Cli"]["codebuddy"]["ready"])



if __name__ == "__main__":
    unittest.main()
