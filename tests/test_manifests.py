from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "programmer-workflow"
TEST_TMP = ROOT / ".tmp-tests"
TEST_TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TMP)


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing frontmatter: {path}")
    data = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


class ManifestTests(unittest.TestCase):
    def test_kimi_manifest(self) -> None:
        data = json.loads((ROOT / "kimi.plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "programmer-workflow")
        self.assertEqual(data["sessionStart"]["skill"], "programmer-workflow")
        self.assertTrue((ROOT / data["skills"]).exists())
        self.assertTrue((ROOT / data["systemPromptPath"]).exists())
        self.assertTrue((ROOT / data["commands"]).exists())
        self.assertLessEqual(len((ROOT / "SYSTEM.md").read_text(encoding="utf-8").encode("utf-8")), 32 * 1024)

    def test_claude_manifest(self) -> None:
        data = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "programmer-workflow")
        self.assertIn("description", data)
        self.assertTrue((ROOT / "skills").is_dir())
        self.assertTrue((ROOT / "commands").is_dir())
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(market["plugins"][0]["name"], "programmer-workflow")
        self.assertEqual(market["plugins"][0]["source"], "./")

    def test_skill_frontmatter(self) -> None:
        meta = read_frontmatter(SKILL / "SKILL.md")
        self.assertEqual(meta["name"], "programmer-workflow")
        self.assertRegex(meta["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertTrue(meta["description"])
        self.assertLessEqual(len(meta["description"]), 500, "DSH catalog description must fit 500 chars")
        for name in (
            "SKILL.md", "references/ask.md", "references/memory.md", "references/satisfaction.md",
            "references/debugging.md", "references/docs.md", "references/prototype.md",
            "references/hosts.md", "references/safety.md",
            "scripts/companion.py", "templates/docs.html", "templates/prototype.html",
        ):
            self.assertTrue((SKILL / name).exists(), name)

    def test_commands_have_description(self) -> None:
        for path in (ROOT / "commands").glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path)
            self.assertIn("description:", text, path)

    def test_no_unresolved_tokens_in_package_files(self) -> None:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".py", ".js", ".css", ".html", ".json", ".ps1", ".sh"}:
                continue
            if ".git" in path.parts or "demo-output" in path.parts or "templates" in path.parts or "tests" in path.parts or "scripts" in path.parts or path.name == "spec.json":
                continue
            if any(part.startswith(".tmp") for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            self.assertNotIn("{{WC_", text, f"unresolved template token in {path}")

    def test_dsh_plugin_manifest(self) -> None:
        plugin = ROOT / "dsh-plugin"
        pkg = json.loads((plugin / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["name"], "@local/programmer-workflow")
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(pkg["version"], version)
        self.assertEqual(pkg["dsh"]["bundle"]["patch"], "./cordis.patch.yml")
        self.assertEqual(pkg["dsh"]["client"]["platform"], "web")
        for name in ("index.js", "client.js", "migration.html", "cordis.patch.yml", "icon.svg", "locale/zh.json", "locale/en.json"):
            self.assertTrue((plugin / name).exists(), name)
        for name in ("migrate-dsh-data.bat", "rollback-dsh-data.bat", "README.md"):
            self.assertTrue((plugin / "dsh-migration-tools" / name).exists(), name)
        self.assertIn("dsh-migration-tools/**", pkg["files"])
        client = (plugin / "client.js").read_text(encoding="utf-8")
        self.assertIn("migrationTarget", client)
        self.assertIn("migrationActionEnabled", client)
        self.assertIn("workflowMode", client)
        self.assertIn("kimiMigrationTools", client)
        self.assertNotIn("requireRunConsent", client)
        self.assertIn("aria-label", client)
        self.check_dsh_client_contract(pkg, client)
        host = (plugin / "index.js").read_text(encoding="utf-8")
        self.assertIn("validateConfigInput", host)
        self.assertIn("plugin-migration/prepare", host)
        self.assertIn("runtimeMigrationSupported", host)
        # Stage 2 contract: paired scripts, rollback launcher, no host fallback.
        self.assertIn("STAGE2_ROLLBACK", host)
        self.assertIn("rollbackLauncher", host)
        self.assertIn("PROGRAMMER_WORKFLOW_CLI", host)
        self.assertIn("unknown host", host)
        patch = (plugin / "cordis.patch.yml").read_text(encoding="utf-8")
        self.assertIn("id: programmer-workflow", patch)
        self.assertIn("@local/programmer-workflow", patch)
        migration = (plugin / "migration.html").read_text(encoding="utf-8")
        self.assertIn("dsh-migration-tools", migration)
        self.assertNotIn("https://", migration)
        node = os.environ.get("WC_NODE")
        if node:
            proc = subprocess.run([node, "--check", str(plugin / "index.js")], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # The Client bundle is served as a classic browser script. `node --check
            # client.js` would parse it as ESM (package.json says "type": "module")
            # and accept `import`/`export`, which is exactly how an incompatible
            # bundle passed review: check a CommonJS copy so module syntax fails.
            classic = TEST_TMP / ("client-" + uuid.uuid4().hex + ".cjs")
            classic.write_text(client, encoding="utf-8")
            try:
                proc = subprocess.run([node, "--check", str(classic)], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            finally:
                classic.unlink(missing_ok=True)

    def check_dsh_client_contract(self, pkg: dict, client: str) -> None:
        """Assert the Client half uses DSH's real loading protocol.

        DSH serves `dsh.client` bundles as classic scripts into the page's
        `window.__ModuleLoader__` lazy-CJS facade: the script only registers a
        factory (`factory(require)` -> module exports) whose `apply(ctx)` owns
        the Slot registrations. ESM syntax and a plain-returned registration
        object both load "without registering" and the Plugins page reports a
        sync failure while the Host enable state stays unchanged.
        """
        self.assertEqual(pkg["dsh"]["client"]["platform"], "web")
        self.assertTrue(pkg["dsh"]["client"].get("immediately"), "client must load at boot")
        self.assertIn('"./client"', json.dumps(pkg["exports"]))
        self.assertTrue(client.startswith("window.__ModuleLoader__.load({"), "client bundle must register a factory")
        self.assertIn("id: '@local/programmer-workflow'", client)
        self.assertIn("factory(require)", client)
        self.assertIn("require('react')", client)
        self.assertNotIn("from 'react'", client)
        self.assertIsNone(
            re.search(r"^\s*(?:import|export)\b", client, re.MULTILINE),
            "classic script: no top-level import/export",
        )
        self.assertIn("inject: ['slots']", client)
        self.assertIn("ctx.slots.inject('settings.section'", client)
        self.assertIn("ctx.slots.register({", client)
        self.assertIn("name: 'settings.section'", client)
        # Restored settings-page features: reset and the migration prompt (its
        # `promptMigration` switch is a real setting again, not dead config).
        self.assertIn("reset: true", client)
        self.assertIn("恢复默认", client)
        self.assertIn("promptMigration", client)
        self.assertIn("shell.overlay", client)
        self.assertIn("ctx.slots.inject('shell.overlay'", client)

    def test_rollback_batch_initializes_variables_before_using_them(self) -> None:
        """`:RollbackOne` must not test `%SRC%` before `set "SRC=%~1"`.

        The tools bat is GBK (`chcp 936`); decoding with `gbk` also guards the
        encoding. An empty `%SRC%` made `if not exist "" if not exist ".old"`
        true, so the shipped DSH rollback always reported "Neither source nor
        backup exists" and returned 1.
        """
        text = (ROOT / "dsh-plugin" / "dsh-migration-tools" / "rollback-dsh-data.bat").read_text(encoding="gbk")
        block = text.split(":RollbackOne", 1)[1]
        set_index = block.index('set "SRC=%~1"')
        check_index = block.index('if not exist "%SRC%\\"')
        self.assertLess(set_index, check_index, "SRC must be assigned before the existence check")
        self.assertIn("rollback-dsh-log.txt", text)

    @unittest.skipUnless(os.name == "nt", "PowerShell installer is Windows-only")
    def test_installer_dry_run(self) -> None:
        pwsh = None
        for candidate in ("pwsh.exe", "powershell.exe"):
            from shutil import which
            found = which(candidate)
            if found:
                pwsh = found
                break
        if not pwsh:
            self.skipTest("PowerShell not available")
        tmp = TEST_TMP / ("install-" + uuid.uuid4().hex)
        tmp.mkdir()
        try:
            proc = subprocess.run(
                [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "install.ps1"),
                 "-DryRun", "-Targets", "agents", "-HomeDir", str(tmp), "-ProjectRoot", str(tmp)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, output)
            self.assertIn("would install", output.lower())
            proc = subprocess.run(
                [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "install.ps1"),
                 "-DryRun", "-Targets", "codebuddy", "-HomeDir", str(tmp), "-ProjectRoot", str(tmp)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, output)
            self.assertIn(".codebuddy", output)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "PowerShell installer is Windows-only")
    def test_installer_bootstrap_preserves_utf8(self) -> None:
        from shutil import which
        pwsh = which("pwsh.exe") or which("powershell.exe")
        if not pwsh:
            self.skipTest("PowerShell not available")
        tmp = TEST_TMP / ("bootstrap-" + uuid.uuid4().hex)
        tmp.mkdir()
        agents = tmp / "AGENTS.md"
        agents.write_text("# 中文标题\n\n项目约定：先给结论。\n", encoding="utf-8")
        try:
            install = subprocess.run(
                [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "install.ps1"),
                 "-Targets", "project", "-ProjectRoot", str(tmp), "-HomeDir", str(tmp), "-Bootstrap"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            text = agents.read_text(encoding="utf-8")
            self.assertIn("中文标题", text)
            self.assertEqual(text.count("<!-- programmer-workflow:start -->"), 1)
            uninstall = subprocess.run(
                [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "install.ps1"),
                 "-Targets", "project", "-ProjectRoot", str(tmp), "-HomeDir", str(tmp), "-Uninstall"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
            text = agents.read_text(encoding="utf-8")
            self.assertIn("中文标题", text)
            self.assertEqual(text.count("<!-- programmer-workflow:start -->"), 0)
            self.assertFalse((tmp / ".agents" / "skills" / "programmer-workflow").exists())
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
