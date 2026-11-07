from __future__ import annotations

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

from lib import hosts, migration  # noqa: E402


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP / ("migration-" + uuid.uuid4().hex)
        self.tmp.mkdir()
        self.env = {}
        for key in ("PROGRAMMER_WORKFLOW_HOST", "PROGRAMMER_WORKFLOW_GLOBAL", "PROGRAMMER_WORKFLOW_HOME",
                    "PROGRAMMER_WORKFLOW_LEGACY_HOME", "PROGRAMMER_WORKFLOW_CLI", "PROGRAMMER_WORKFLOW_DSH_TOOLS",
                    "PROGRAMMER_WORKFLOW_SYSTEM_DRIVE", "KIMI_MIGRATION_TOOLS", "KIMI_HOME", "DSH_HOME"):
            self.env[key] = os.environ.get(key)
            os.environ.pop(key, None)
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        # Treat the sandbox volume as the "system" drive so temp paths are not
        # mistaken for a relocated landing; relocation tests switch this.
        sandbox_drive = self.tmp.drive.upper()
        if sandbox_drive:
            os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = sandbox_drive
        os.environ["KIMI_HOME"] = str(self.tmp / "kimi-home")
        os.environ["PROGRAMMER_WORKFLOW_LEGACY_HOME"] = str(self.tmp / "legacy-home")
        self.source = hosts.plugin_root("kimi")
        self.memory = self.source / "memory"
        self.memory.mkdir(parents=True)
        (self.memory / "memory.json").write_text(json.dumps({
            "schema": 1, "scope": "user", "entries": [
                {"id": "u-active", "status": "active", "kind": "habit", "text": "active"},
                {"id": "u-proposed", "status": "proposed", "kind": "habit", "text": "proposed"},
            ],
        }), encoding="utf-8")
        (self.memory / "MEMORY.md").write_text("# memory\n", encoding="utf-8")
        (self.source / "config.json").write_text(json.dumps({"workflowMode": "plan"}), encoding="utf-8")
        self.target_root = self.tmp / "target-root"

    def tearDown(self) -> None:
        for path in (self.source, self.target_root):
            if path.exists() and path.is_dir():
                try:
                    if getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                        migration.remove_junction(path)
                    else:
                        shutil.rmtree(path, ignore_errors=True)
                except OSError:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_prepare_apply_and_rollback_preserve_statuses(self) -> None:
        prepared = migration.prepare("kimi", self.target_root)
        self.assertEqual(prepared["status"], "prepared")
        target = Path(prepared["target"])
        applied = migration.apply("kimi", self.target_root, assume_yes=True)
        self.assertEqual(applied["status"], "completed")
        self.assertTrue(self.source.is_dir())
        self.assertEqual(Path(os.path.realpath(self.source)), target)
        copied = json.loads((target / "memory" / "memory.json").read_text(encoding="utf-8"))
        statuses = {entry["id"]: entry["status"] for entry in copied["entries"]}
        self.assertEqual(statuses, {"u-active": "active", "u-proposed": "proposed"})
        rolled = migration.rollback("kimi")
        self.assertEqual(rolled["status"], "rolled-back")
        self.assertTrue((self.memory / "memory.json").exists())
        restored = json.loads((self.memory / "memory.json").read_text(encoding="utf-8"))
        self.assertEqual({entry["id"] for entry in restored["entries"]}, {"u-active", "u-proposed"})

    def test_target_existing_data_is_rejected(self) -> None:
        target = migration.plugin_target("kimi", self.target_root)
        target.mkdir(parents=True)
        (target / "unknown.txt").write_text("x", encoding="utf-8")
        report = migration.preflight("kimi", self.target_root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unrelated" in error for error in report["errors"]))

    def test_unc_target_is_rejected(self) -> None:
        with self.assertRaises(migration.MigrationError):
            migration.plugin_target("kimi", "\\\\server\\share")

    def test_legacy_conflict_does_not_overwrite(self) -> None:
        legacy = self.tmp / "legacy-home" / ".dsh" / "programmer-workflow" / "memory"
        legacy.mkdir(parents=True)
        (legacy / "memory.json").write_text(json.dumps({
            "schema": 1, "scope": "user", "entries": [{"id": "legacy", "status": "active", "text": "legacy"}],
        }), encoding="utf-8")
        before = (self.memory / "memory.json").read_bytes()
        result = migration.legacy_import("kimi")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "conflict")
        self.assertEqual((self.memory / "memory.json").read_bytes(), before)
        self.assertTrue(Path(result["report"]).exists())

    def test_legacy_import_preserves_proposed(self) -> None:
        legacy = self.tmp / "legacy-home" / ".dsh" / "programmer-workflow"
        (legacy / "memory").mkdir(parents=True)
        (legacy / "memory" / "memory.json").write_text(json.dumps({
            "schema": 1, "scope": "user", "entries": [
                {"id": "l-active", "status": "active", "text": "a"},
                {"id": "l-proposed", "status": "proposed", "text": "p"},
            ],
        }), encoding="utf-8")
        shutil.rmtree(self.memory)
        result = migration.legacy_import("kimi", apply_now=True)
        self.assertEqual(result["status"], "imported")
        entries = json.loads((self.memory / "memory.json").read_text(encoding="utf-8"))["entries"]
        self.assertEqual({entry["id"]: entry["status"] for entry in entries}, {"l-active": "active", "l-proposed": "proposed"})

    def test_plugin_target_is_host_scoped(self) -> None:
        self.assertEqual(migration.plugin_target("kimi", self.target_root), (self.target_root / ".kimi-code" / "programmer-workflow").resolve())
        self.assertEqual(migration.plugin_target("dsh", self.target_root), (self.target_root / ".dsh" / "programmer-workflow").resolve())
        self.assertEqual(migration.plugin_target("codebuddy", self.target_root), (self.target_root / ".codebuddy" / "programmer-workflow").resolve())
        self.assertNotEqual(migration.plugin_target("kimi", self.target_root), migration.plugin_target("codebuddy", self.target_root))

    def test_stage2_is_gated_and_codebuddy_is_unsupported(self) -> None:
        self.assertEqual(migration.runtime_status("kimi")["status"], "blocked")
        migration.apply("kimi", self.target_root, assume_yes=True)
        self.assertTrue(migration.runtime_status("kimi")["supported"])
        self.assertFalse(migration.runtime_status("codebuddy")["supported"])
        self.assertEqual(migration.runtime_status("codebuddy")["status"], "unavailable")

    def test_runtime_status_requires_a_real_migrate_and_rollback_pair(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        legacy = migration.LEGACY_TOOL_DIRS.get("kimi")
        migration.LEGACY_TOOL_DIRS["kimi"] = None
        try:
            status = migration.runtime_status("kimi")
            self.assertEqual(status["status"], "unavailable")
            self.assertFalse(status["adapterReady"])
            self.assertIn("migrate", status["reason"])

            tools = self.tmp / "kimi-tools"
            tools.mkdir()
            (tools / "migrate-kimi-data.bat").write_text("REM KIMI_MIG_SRC", encoding="utf-8")
            os.environ["KIMI_MIGRATION_TOOLS"] = str(tools)
            status = migration.runtime_status("kimi")
            self.assertEqual(status["status"], "unavailable", "a migrate-only directory is not ready")
            self.assertIn("rollback-kimi-data.bat", status["reason"])
            self.assertEqual(Path(status["detectedToolsPath"]), tools)
            self.assertEqual(Path(status["toolsPath"]), tools)

            # A custom KIMI_HOME needs an adapter that honors KIMI_MIG_SRC.
            (tools / "rollback-kimi-data.bat").write_text("REM rollback", encoding="utf-8")
            status = migration.runtime_status("kimi")
            self.assertEqual(status["status"], "ready", status["reason"])
            self.assertTrue(status["adapterReady"])
            self.assertEqual(Path(status["toolsPath"]), tools)
            self.assertEqual(Path(status["rollbackScript"]), tools / "rollback-kimi-data.bat")

            (tools / "migrate-kimi-data.bat").write_text("REM fixed USERPROFILE path", encoding="utf-8")
            status = migration.runtime_status("kimi")
            self.assertEqual(status["status"], "unavailable")
            self.assertIn("KIMI_MIG_SRC", status["reason"])

            # A rollback that calls a missing label would exit 0 without doing
            # anything; readiness must refuse it.
            (tools / "migrate-kimi-data.bat").write_text("REM KIMI_MIG_SRC", encoding="utf-8")
            (tools / "rollback-kimi-data.bat").write_text(
                "call :RollbackOne\r\npause\r\nexit /b 0\r\n", encoding="utf-8")
            status = migration.runtime_status("kimi")
            self.assertEqual(status["status"], "unavailable")
            self.assertIn("RollbackOne", status["reason"])
        finally:
            if legacy is None:
                migration.LEGACY_TOOL_DIRS.pop("kimi", None)
            else:
                migration.LEGACY_TOOL_DIRS["kimi"] = legacy

    def test_corrupt_real_memory_file_blocks_preflight_and_apply(self) -> None:
        real = self.memory / "memory.json"
        real.write_text("{ this is not json", encoding="utf-8")
        report = migration.preflight("kimi", self.target_root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("JSON object" in error for error in report["errors"]), report["errors"])
        with self.assertRaises(migration.MigrationError):
            migration.apply("kimi", self.target_root, assume_yes=True)
        self.assertTrue(real.exists(), "a rejected apply must leave the real memory file alone")
        self.assertFalse(migration.plugin_target("kimi", self.target_root).exists())

        real.write_text(json.dumps({"entries": {"not": "a list"}}), encoding="utf-8")
        report = migration.preflight("kimi", self.target_root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("entries array" in error for error in report["errors"]), report["errors"])

        # The same rule applies to a flat root memory.json (older/exported trees).
        real.unlink()
        flat = self.source / "memory.json"
        flat.write_text("[]", encoding="utf-8")
        report = migration.preflight("kimi", self.target_root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("JSON object" in error for error in report["errors"]), report["errors"])
        flat.unlink()

    def test_stage1_rollback_waits_for_stage2(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        runtime_state = migration.runtime_state_path("kimi")
        runtime_state.parent.mkdir(parents=True, exist_ok=True)
        for status in ("prepared", "active", "completed"):
            runtime_state.write_text(json.dumps({"host": "kimi", "status": status}), encoding="utf-8")
            with self.assertRaises(migration.MigrationError) as caught:
                migration.rollback("kimi")
            self.assertIn("stage 2", str(caught.exception))
            self.assertTrue((self.memory / "memory.json").exists(), "the failed gate must change nothing")
        # A completed stage 2 is recorded by the launcher marker too; it still blocks.
        (runtime_state.parent / "runtime-completed.txt").write_text("completed", encoding="utf-8")
        runtime_state.write_text(json.dumps({"host": "kimi", "status": "prepared"}), encoding="utf-8")
        with self.assertRaises(migration.MigrationError):
            migration.rollback("kimi")
        (runtime_state.parent / "runtime-completed.txt").unlink()
        # After the stage 2 rollback launcher ran, its marker wins over the stale
        # "prepared" JSON and stage 1 rollback becomes possible again.
        (runtime_state.parent / "runtime-rolled-back.txt").write_text("rolled back", encoding="utf-8")
        migrate_result = migration.rollback("kimi")
        self.assertEqual(migrate_result["status"], "rolled-back")
        self.assertEqual(migrate_result["stage2Status"], "rolled-back")
        self.assertTrue(migrate_result["oldSourceRestored"])

    def test_rollback_failure_restores_the_link_and_keeps_the_backup(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        state = migration.read_state("kimi")
        assert state is not None
        old = Path(state["oldSource"])
        target = Path(state["target"])
        original_rename = Path.rename

        def fail_restore(self_path, next_path):
            if self_path == old and Path(next_path) == Path(state["source"]):
                raise OSError("simulated restore failure")
            return original_rename(self_path, next_path)

        from unittest import mock
        with mock.patch.object(Path, "rename", fail_restore):
            with self.assertRaises(migration.MigrationError) as caught:
                migration.rollback("kimi")
        self.assertIn("recovery=junction-restored", str(caught.exception))
        self.assertTrue(migration._is_reparse(self.source), "the worker must be reachable again")
        self.assertEqual(Path(os.path.realpath(self.source)), target)
        self.assertTrue(old.exists(), "the .old backup must be preserved")
        self.assertNotEqual(migration.read_state("kimi")["status"], "rolled-back")

    def test_nested_junction_rebuild_is_reported_as_unsupported(self) -> None:
        report = migration.preflight("kimi", self.target_root)
        self.assertEqual(report["nestedJunctionRebuild"], "unsupported")

    def test_prepared_state_is_not_a_verified_stage1(self) -> None:
        migration.prepare("kimi", self.target_root)
        self.assertIsNone(migration.verified_stage1("kimi"))
        status = migration.runtime_status("kimi")
        self.assertFalse(status["stage1Completed"])
        self.assertEqual(status["status"], "blocked")

    def test_external_link_is_never_verified(self) -> None:
        external = self.tmp / "external-target"
        external.mkdir()
        shutil.rmtree(self.source)
        migration.create_junction(self.source, external)
        self.assertIsNone(migration.verified_stage1("kimi"))
        self.assertIsNone(migration.read_state("kimi"))
        summary = migration.stage1_summary("kimi")
        self.assertFalse(summary["completed"], "a link on the system drive is not a completed move")
        self.assertFalse(summary["relocated"])

    def test_relocated_landing_counts_as_completed_without_a_record(self) -> None:
        external = self.tmp / "moved-target"
        external.mkdir()
        shutil.rmtree(self.source)
        migration.create_junction(self.source, external)
        os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = "Q:"
        try:
            summary = migration.stage1_summary("kimi")
            self.assertTrue(summary["completed"])
            self.assertTrue(summary["relocated"])
            self.assertEqual(summary["completedVia"], "relocated")
            self.assertFalse(summary["verified"], "relocated must not fabricate a verified record")
            self.assertTrue(migration.runtime_status("kimi")["stage1Completed"])
        finally:
            os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = self.tmp.drive.upper()

    def test_stage2_relocated_counts_as_completed(self) -> None:
        moved_home = self.tmp / "moved-home"
        moved_target = self.tmp / "moved-home-target"
        moved_target.mkdir()
        migration.create_junction(moved_home, moved_target)
        previous_home = os.environ["KIMI_HOME"]
        os.environ["KIMI_HOME"] = str(moved_home)
        os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = "Q:"
        try:
            summary = migration.stage2_summary("kimi")
            self.assertTrue(summary["completed"])
            self.assertTrue(summary["relocated"])
            self.assertEqual(summary["completedVia"], "relocated")
            self.assertFalse(summary["verified"])
            self.assertEqual(Path(summary["actualLocation"]), moved_target.resolve())
        finally:
            os.environ["KIMI_HOME"] = previous_home
            os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = self.tmp.drive.upper()

    def test_second_migration_uses_live_data_not_the_old_backup(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        first_target = migration.plugin_target("kimi", self.target_root)
        data = json.loads((self.memory / "memory.json").read_text(encoding="utf-8"))
        data["entries"].append({"id": "u-latest", "status": "active", "kind": "habit", "text": "after first migration"})
        (self.memory / "memory.json").write_text(json.dumps(data), encoding="utf-8")

        second_root = self.tmp / "second-root"
        report = migration.preflight("kimi", second_root)
        self.assertTrue(report["ok"], report["errors"])
        applied = migration.apply("kimi", second_root, assume_yes=True)
        second_target = migration.plugin_target("kimi", second_root)
        self.assertEqual(Path(applied["target"]), second_target)
        entries = json.loads((second_target / "memory" / "memory.json").read_text(encoding="utf-8"))["entries"]
        self.assertIn("u-latest", {entry["id"] for entry in entries}, "the second move must copy the live data")
        # The previous target and the pre-migration backup are both preserved.
        self.assertTrue(first_target.exists())
        self.assertTrue(Path(applied["oldSource"]).exists())
        self.assertIsNotNone(migration.verified_stage1("kimi"))

    def test_failed_second_migration_keeps_the_previous_verified_record(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        first_target = migration.plugin_target("kimi", self.target_root)
        second_root = self.tmp / "second-fail"
        from unittest import mock
        with mock.patch.object(migration, "_copy_plugin", side_effect=migration.MigrationError("simulated copy failure")):
            with self.assertRaises(migration.MigrationError):
                migration.apply("kimi", second_root, assume_yes=True)
        verified = migration.verified_stage1("kimi")
        self.assertIsNotNone(verified, "the still-active first migration stays verified")
        self.assertEqual(Path(verified["target"]), first_target)
        self.assertEqual(migration.read_state("kimi")["status"], "failed")


    @unittest.skipUnless(os.name == "nt", "Windows .cmd launchers")
    def test_prepare_plugin_writes_target_bound_launchers(self) -> None:
        cli = self.tmp / "managed" / "programmer-workflow" / "scripts" / "companion.py"
        cli.parent.mkdir(parents=True)
        cli.write_text("# managed copy", encoding="utf-8")
        result = migration.prepare_plugin_migration("kimi", self.target_root, companion=cli)
        self.assertEqual(result["status"], "prepared")
        launcher = Path(result["launcher"])
        rollback = Path(result["rollbackLauncher"])
        self.assertTrue(launcher.is_file())
        self.assertTrue(rollback.is_file())
        text = launcher.read_bytes().decode("utf-8")
        self.assertIn(str(cli.resolve()), text)
        self.assertIn("--host kimi", text)
        self.assertIn("migrate-plugin apply", text)
        self.assertIn(str(self.target_root), text)
        self.assertIn('set "PROGRAMMER_WORKFLOW_HOST=kimi"', text)
        rollback_text = rollback.read_bytes().decode("utf-8")
        self.assertIn("migrate-plugin rollback --host kimi", rollback_text)
        self.assertIn("Roll stage 2 back first", rollback_text)
        state = migration.read_state("kimi")
        assert state is not None
        self.assertEqual(state["status"], "prepared")
        self.assertEqual(Path(state["launcher"]), launcher)
        self.assertFalse(migration.stage1_summary("kimi")["completed"])

    @unittest.skipUnless(os.name == "nt", "Windows .cmd launchers")
    def test_prepare_plugin_accepts_the_running_managed_cli(self) -> None:
        managed = (
            self.tmp / "kimi-home" / "plugins" / "managed" / "programmer-workflow"
            / "skills" / "programmer-workflow" / "scripts" / "companion.py"
        )
        managed.parent.mkdir(parents=True)
        managed.write_text("# managed copy", encoding="utf-8")
        with mock.patch.object(sys, "argv", [str(managed)]):
            result = migration.prepare_plugin_migration("kimi", self.target_root)
        self.assertEqual(Path(result["companion"]), managed.resolve())
        self.assertIn(str(managed.resolve()), Path(result["launcher"]).read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows .cmd launchers")
    def test_prepare_plugin_respects_the_action_switch(self) -> None:
        from lib import config as configlib
        configlib.save("kimi", {"migrationActionEnabled": False})
        cli = self.tmp / "managed" / "programmer-workflow" / "scripts" / "companion.py"
        cli.parent.mkdir(parents=True)
        cli.write_text("", encoding="utf-8")
        with self.assertRaises(migration.MigrationConflict):
            migration.prepare_plugin_migration("kimi", self.target_root, companion=cli)

    @unittest.skipUnless(os.name == "nt", "Windows .cmd launchers")
    def test_prepare_runtime_requires_stage1_adapter_and_nested_target(self) -> None:
        tools = self.tmp / "kimi-tools"
        tools.mkdir()
        (tools / "migrate-kimi-data.bat").write_text("REM KIMI_MIG_SRC", encoding="utf-8")
        (tools / "rollback-kimi-data.bat").write_text("REM rollback", encoding="utf-8")
        os.environ["KIMI_MIGRATION_TOOLS"] = str(tools)

        with self.assertRaises(migration.MigrationConflict):
            migration.prepare_runtime_migration("kimi", self.target_root)

        migration.apply("kimi", self.target_root, assume_yes=True)
        other_root = self.tmp / "other-root"
        with self.assertRaises(migration.MigrationConflict):
            migration.prepare_runtime_migration("kimi", other_root)
        with self.assertRaises(migration.MigrationError):
            migration.prepare_runtime_migration("kimi", "relative-root")

        result = migration.prepare_runtime_migration("kimi", self.target_root)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(Path(result["target"]), (self.target_root / ".kimi-code").resolve())
        launcher = Path(result["launcher"])
        rollback = Path(result["rollbackLauncher"])
        self.assertTrue(launcher.is_file())
        self.assertTrue(rollback.is_file())
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn(f'set "KIMI_MIG_DEST={self.target_root.resolve()}"', launcher_text)
        self.assertIn(f'set "KIMI_MIG_SRC={hosts.host_home("kimi")}"', launcher_text)
        self.assertIn(f'set "KIMI_MIGRATION_TOOLS={tools.resolve()}"', launcher_text)
        self.assertIn(f'call "{tools.resolve() / "migrate-kimi-data.bat"}"', launcher_text)
        self.assertIn("runtime-completed.txt", launcher_text)
        rollback_text = rollback.read_text(encoding="utf-8")
        self.assertIn("runtime-rolled-back.txt", rollback_text)
        self.assertIn("rollback-kimi-data.bat", rollback_text)
        state = migration.read_runtime_state("kimi")
        assert state is not None
        self.assertEqual(state["status"], "prepared")
        self.assertEqual(Path(state["targetRoot"]), self.target_root.resolve())
        status = migration.runtime_status("kimi")
        self.assertEqual(status["stage2Status"], "prepared")
        self.assertFalse(status["stage2Completed"], "prepared must never claim completed")

        # Turning the action switch off blocks stage 2 as well.
        from lib import config as configlib
        configlib.save("kimi", {"migrationActionEnabled": False})
        with self.assertRaises(migration.MigrationConflict):
            migration.prepare_runtime_migration("kimi", self.target_root)

    def test_prepare_runtime_unavailable_without_migrate_and_rollback_pair(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        with self.assertRaises(migration.MigrationError):
            migration.prepare_runtime_migration("kimi", self.target_root)


        nested_target = self.tmp / "nested-target"
        nested_target.mkdir()
        nested = self.source / "artifacts" / "nested"
        nested.parent.mkdir()
        migration.create_junction(nested, nested_target)
        try:
            report = migration.preflight("kimi", self.target_root)
            self.assertTrue(any("nested" in error for error in report["errors"]))
            self.assertTrue(migration.nested_links(self.source))
        finally:
            migration.remove_junction(nested)

    def test_rollback_requires_completed_state(self) -> None:
        with self.assertRaises(migration.MigrationError):
            migration.rollback("kimi")

    def test_latest_plugin_data_is_backed_up_before_rollback(self) -> None:
        migration.apply("kimi", self.target_root, assume_yes=True)
        data = json.loads((self.memory / "memory.json").read_text(encoding="utf-8"))
        data["entries"].append({"id": "u-new", "status": "active", "kind": "habit", "text": "new"})
        (self.memory / "memory.json").write_text(json.dumps(data), encoding="utf-8")
        result = migration.rollback("kimi")
        self.assertTrue(result["changed"])
        self.assertTrue(Path(result["latestBackup"]).exists())
        latest = json.loads((Path(result["latestBackup"]) / "memory" / "memory.json").read_text(encoding="utf-8"))
        self.assertIn("u-new", {entry["id"] for entry in latest["entries"]})
        restored = json.loads((self.memory / "memory.json").read_text(encoding="utf-8"))
        self.assertNotIn("u-new", {entry["id"] for entry in restored["entries"]})


if __name__ == "__main__":
    unittest.main()
