from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
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

from lib import config as configlib  # noqa: E402
from lib import hosts, settings  # noqa: E402
from lib.common import load_plugin_config  # noqa: E402


class SettingsTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP / ("settings-" + uuid.uuid4().hex)
        self.tmp.mkdir()
        self.workspace = self.tmp / "workspace"
        self.workspace.mkdir()
        self.env = {}
        for key in (
            "PROGRAMMER_WORKFLOW_HOST", "PROGRAMMER_WORKFLOW_GLOBAL",
            "PROGRAMMER_WORKFLOW_HOME", "PROGRAMMER_WORKFLOW_LEGACY_HOME",
            "PROGRAMMER_WORKFLOW_CLI", "PROGRAMMER_WORKFLOW_SYSTEM_DRIVE",
            "PROGRAMMER_WORKFLOW_DSH_TOOLS", "KIMI_MIGRATION_TOOLS",
            "DSH_HOME", "KIMI_HOME", "CODEBUDDY_HOME",
        ):
            self.env[key] = os.environ.get(key)
            os.environ.pop(key, None)
        os.environ["PROGRAMMER_WORKFLOW_HOST"] = "kimi"
        os.environ["KIMI_HOME"] = str(self.tmp / "kimi-home")
        os.environ["DSH_HOME"] = str(self.tmp / "dsh-home")
        os.environ["CODEBUDDY_HOME"] = str(self.tmp / "codebuddy-home")
        os.environ["PROGRAMMER_WORKFLOW_LEGACY_HOME"] = str(self.tmp / "legacy-home")
        drive = self.tmp.drive.upper()
        if drive:
            os.environ["PROGRAMMER_WORKFLOW_SYSTEM_DRIVE"] = drive
        self.server = None
        self.thread = None
        self.token = "test-token"

    def tearDown(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=5)
            self.thread = None
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start_server(self, token: str | None = None) -> None:
        self.token = token or self.token
        self.server = settings.create_server("kimi", self.workspace, port=0, token=self.token)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.02},
            daemon=True,
        )
        self.thread.start()

    def request(
        self,
        method: str,
        path: str,
        body: object = None,
        *,
        token: bool = True,
        content_type: str = "application/json",
        raw_body: bytes | None = None,
        headers: dict | None = None,
    ) -> tuple[int, dict, dict]:
        assert self.server is not None
        port = self.server.server_address[1]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        request_headers = dict(headers or {})
        if token:
            request_headers["X-Programmer-Workflow-Token"] = self.token
        data: bytes | None = None
        if raw_body is not None:
            data = raw_body
            request_headers.setdefault("Content-Type", content_type)
        elif body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", content_type)
        connection.request(method, path, body=data, headers=request_headers)
        response = connection.getresponse()
        payload_raw = response.read().decode("utf-8", "replace")
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        connection.close()
        try:
            payload = json.loads(payload_raw)
        except ValueError:
            payload = {"raw": payload_raw}
        return response.status, payload, response_headers


class ConfigTests(SettingsTestBase):
    def test_defaults_include_migration_fields(self) -> None:
        cfg = configlib.read("kimi")
        for key in (
            "migrationActionEnabled", "migrationTarget", "kimiMigrationTarget",
            "kimiMigrationTools", "pluginMigrationTargetRoot", "runtimeMigrationTargetRoot",
        ):
            self.assertIn(key, cfg)
        self.assertTrue(cfg["migrationActionEnabled"])
        self.assertTrue(cfg["screenshotEnabled"])
        self.assertTrue(cfg["balanceDisplay"])
        self.assertEqual(cfg["balanceRefreshSeconds"], 60)
        self.assertEqual(cfg["workflowMode"], "plan")
        self.assertEqual(cfg["planFormat"], "md")

    def test_partial_save_merges_and_cli_reads_it(self) -> None:
        configlib.save("kimi", {"workflowMode": "full-authority", "planFormat": "html"})
        self.assertEqual(configlib.read("kimi")["workflowMode"], "full-authority")
        effective = load_plugin_config(self.workspace)
        self.assertEqual(effective["workflowMode"], "full-authority")
        self.assertEqual(effective["planFormat"], "html")

        configlib.save("kimi", {"docsDir": "out/docs"})
        cfg = configlib.read("kimi")
        self.assertEqual(cfg["docsDir"], "out/docs")
        self.assertEqual(cfg["workflowMode"], "full-authority", "a partial save must keep other fields")
        document = json.loads(configlib.config_path("kimi").read_text(encoding="utf-8"))
        self.assertEqual(document["host"], "kimi")
        self.assertEqual(document["name"], "Programmer Workflow")

        # DSH keeps its own defaults and file.
        self.assertFalse(configlib.config_path("dsh").exists())
        self.assertEqual(configlib.read("dsh")["workflowMode"], "plan")

    def test_strict_validation_rejects_bad_values_with_field_names(self) -> None:
        cases = [
            ({"workspaceDataDir": ""}, "workspaceDataDir"),
            ({"workspaceDataDir": "../escape"}, "workspaceDataDir"),
            ({"workspaceDataDir": "C:\\escape"}, "workspaceDataDir"),
            ({"workspaceDataDir": "\\\\server\\share"}, "workspaceDataDir"),
            ({"debugLogDir": "/tmp/logs"}, "debugLogDir"),
            ({"docsDir": "."}, "docsDir"),
            ({"prototypeFile": "a/../../b.html"}, "prototypeFile"),
            ({"userMemoryEnabled": "true"}, "userMemoryEnabled"),
            ({"satisfactionThreshold": 0}, "satisfactionThreshold"),
            ({"satisfactionThreshold": 11}, "satisfactionThreshold"),
            ({"satisfactionThreshold": 3.5}, "satisfactionThreshold"),
            ({"satisfactionThreshold": "3"}, "satisfactionThreshold"),
            ({"bugfixThreshold": True}, "bugfixThreshold"),
            ({"retentionDays": 0}, "retentionDays"),
            ({"retentionDays": 366}, "retentionDays"),
            ({"workflowMode": "auto"}, "workflowMode"),
            ({"planFormat": "pdf"}, "planFormat"),
            ({"language": ""}, "language"),
            ({"language": "x" * 21}, "language"),
            ({"migrationTarget": "relative\\target"}, "migrationTarget"),
            ({"pluginMigrationTargetRoot": "\\\\server\\share"}, "pluginMigrationTargetRoot"),
            ({"kimiMigrationTools": "tools"}, "kimiMigrationTools"),
        ]
        for payload, field in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(configlib.ConfigValidationError) as caught:
                    configlib.save("kimi", payload)
                self.assertIn(field, caught.exception.errors)
        self.assertFalse(
            configlib.config_path("kimi").exists(),
            "a rejected save must not create or replace config.json",
        )

    def test_absolute_and_empty_migration_targets_are_valid(self) -> None:
        configlib.save("kimi", {
            "migrationTarget": "D:\\AgentData",
            "kimiMigrationTarget": "D:/AgentData/Kimi",
            "pluginMigrationTargetRoot": "",
            "runtimeMigrationTargetRoot": "E:\\Target Root",
            "kimiMigrationTools": "D:\\tools\\kimi",
        })
        cfg = configlib.read("kimi")
        self.assertEqual(cfg["migrationTarget"], "D:\\AgentData")
        self.assertEqual(cfg["kimiMigrationTarget"], "D:\\AgentData\\Kimi")
        self.assertEqual(cfg["pluginMigrationTargetRoot"], "")
        self.assertEqual(cfg["runtimeMigrationTargetRoot"], "E:\\Target Root")

    def test_unknown_fields_from_a_newer_surface_are_preserved(self) -> None:
        path = configlib.config_path("kimi")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"futureSetting": {"enabled": True}}), encoding="utf-8")
        configlib.save("kimi", {"workflowMode": "full-authority"})
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["futureSetting"], {"enabled": True})
        self.assertEqual(document["workflowMode"], "full-authority")

    def test_concurrent_partial_saves_keep_both_fields(self) -> None:
        barrier = threading.Barrier(2)
        errors = []

        def worker(key: str, value: str) -> None:
            try:
                barrier.wait(timeout=10)
                for _ in range(8):
                    configlib.save("kimi", {key: value})
            except Exception as error:  # pragma: no cover - surfaced below
                errors.append(error)

        threads = [
            threading.Thread(target=worker, args=("docsDir", "out/docs")),
            threading.Thread(target=worker, args=("debugLogDir", "tmp/logs")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(errors, errors)
        cfg = configlib.read("kimi")
        self.assertEqual(cfg["docsDir"], "out/docs")
        self.assertEqual(cfg["debugLogDir"], "tmp/logs")

    def test_unknown_host_is_not_a_dsh_fallback(self) -> None:
        with self.assertRaises(hosts.HostResolutionError):
            configlib.read("not-a-host")
        with self.assertRaises(hosts.HostResolutionError):
            configlib.save("not-a-host", {"workflowMode": "plan"})

    def test_reset_touches_only_current_config_and_keeps_memory(self) -> None:
        configlib.save("kimi", {"workflowMode": "full-authority", "planFormat": "html"})
        configlib.save("dsh", {"workflowMode": "full-authority"})
        memory_root = hosts.memory_root("kimi")
        memory_root.mkdir(parents=True, exist_ok=True)
        memory_json = memory_root / "memory.json"
        memory_md = memory_root / "MEMORY.md"
        memory_json.write_text('{"entries": []}', encoding="utf-8")
        memory_md.write_text("# memory\n", encoding="utf-8")
        before_json = memory_json.read_bytes()
        before_md = memory_md.read_bytes()
        dsh_before = configlib.config_path("dsh").read_bytes()

        configlib.reset("kimi")
        self.assertEqual(configlib.read("kimi")["workflowMode"], "plan")
        self.assertEqual(memory_json.read_bytes(), before_json)
        self.assertEqual(memory_md.read_bytes(), before_md)
        self.assertEqual(configlib.config_path("dsh").read_bytes(), dsh_before)
        self.assertEqual(configlib.read("dsh")["workflowMode"], "full-authority")


class ServerTests(SettingsTestBase):
    def test_static_whitelist_token_and_security_headers(self) -> None:
        self.start_server()
        for path, content_type in (
            ("/", "text/html"),
            ("/settings.css", "text/css"),
            ("/settings.js", "javascript"),
        ):
            status, _, headers = self.request("GET", path, token=False)
            self.assertEqual(status, 200, path)
            self.assertIn(content_type, headers.get("content-type", ""))
            self.assertNotIn("access-control-allow-origin", headers)
        status, _, headers = self.request("GET", "/settings.html", token=False)
        self.assertEqual(status, 404)
        status, _, headers = self.request("GET", "/", token=False)
        self.assertEqual(headers.get("cache-control"), "no-store")
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertIn("default-src 'none'", headers.get("content-security-policy", ""))

        status, payload, _ = self.request("GET", "/api/status?host=kimi", token=False)
        self.assertEqual(status, 403)
        self.assertEqual(payload["ok"], False)
        status, payload, _ = self.request(
            "GET", "/api/status?host=kimi",
            token=False,
            headers={"X-Programmer-Workflow-Token": "wrong"},
        )
        self.assertEqual(status, 403)
        status, payload, _ = self.request("GET", "/api/status?host=kimi")
        self.assertEqual(status, 200)
        self.assertEqual(payload["host"], "kimi")

    def test_quick_link_redirects_token_without_api_access(self) -> None:
        self.start_server()
        status, _, headers = self.request("GET", "/quick?host=kimi", token=False)
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("location"), "/?host=kimi#token=" + self.token)
        self.assertNotIn("access-control-allow-origin", headers)
        self.assertEqual(headers.get("cache-control"), "no-store")
        status, payload, _ = self.request("GET", "/quick?host=not-a-host", token=False)
        self.assertEqual(status, 400)
        self.assertIn("unknown host", payload.get("error", ""))
        # The redirect itself must not grant API access without the token.
        status, _, _ = self.request("GET", "/api/status?host=kimi", token=False)
        self.assertEqual(status, 403)

    def test_host_argument_is_required_and_strict(self) -> None:
        self.start_server()
        status, payload, _ = self.request("GET", "/api/status")
        self.assertEqual(status, 400)
        self.assertEqual(payload["ok"], False)
        status, payload, _ = self.request("GET", "/api/status?host=not-a-host")
        self.assertEqual(status, 400)
        self.assertIn("unknown host", payload["error"])
        status, payload, _ = self.request("GET", "/api/status?host=dsh")
        self.assertEqual(status, 200)
        self.assertEqual(payload["host"], "dsh")
        self.assertEqual(Path(payload["paths"]["configPath"]), configlib.config_path("dsh"))
        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            body={"host": "dsh", "workflowMode": "plan"},
        )
        self.assertEqual(status, 400, payload)

    def test_methods_and_unknown_routes(self) -> None:
        self.start_server()
        self.assertEqual(self.request("PUT", "/api/config")[0], 405)
        self.assertEqual(self.request("OPTIONS", "/api/config")[0], 405)
        self.assertEqual(self.request("GET", "/api/migration/plugin/prepare")[0], 405)
        self.assertEqual(self.request("POST", "/api/status", body={})[0], 405)
        self.assertEqual(self.request("GET", "/api/nope")[0], 404)
        self.assertEqual(self.request("POST", "/api/nope", body={})[0], 404)
        self.assertEqual(self.request("POST", "/", body={})[0], 405)

    def test_post_body_rules(self) -> None:
        self.start_server()
        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            raw_body=b'{"host":"kimi"}', content_type="text/plain",
        )
        self.assertEqual(status, 400)
        self.assertIn("application/json", payload["error"])
        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            raw_body=b'[1,2,3]', content_type="application/json",
        )
        self.assertEqual(status, 400)
        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            raw_body=b'{not json', content_type="application/json",
        )
        self.assertEqual(status, 400)
        big = json.dumps({"host": "kimi", "padding": "x" * (settings.MAX_BODY_BYTES + 100)}).encode("utf-8")
        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            raw_body=big, content_type="application/json",
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["ok"], False)

    def test_config_save_errors_keep_file_and_boot_reads_saved_values(self) -> None:
        self.start_server()
        configlib.save("kimi", {"workflowMode": "plan", "planFormat": "md"})
        before = configlib.config_path("kimi").read_bytes()
        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            body={"host": "kimi", "workspaceDataDir": "C:\\outside"},
        )
        self.assertEqual(status, 400)
        self.assertIn("workspaceDataDir", payload.get("fields", {}))
        self.assertEqual(configlib.config_path("kimi").read_bytes(), before)

        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            body={"host": "kimi", "workflowMode": "full-authority", "planFormat": "html"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["config"]["workflowMode"], "full-authority")
        self.assertEqual(payload["config"]["planFormat"], "html")
        self.assertEqual(configlib.read("kimi")["planFormat"], "html")

        env = dict(os.environ)
        output = subprocess.run(
            [
                sys.executable, str(SCRIPTS / "companion.py"), "boot",
                "--host", "kimi", "--workspace", str(self.workspace), "--json",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env=env,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        boot = json.loads(output.stdout)
        self.assertEqual(boot["workflow"]["mode"], "full-authority")
        self.assertEqual(boot["workflow"]["planFormat"], "html")

    def test_state_includes_required_paths_and_hosts(self) -> None:
        self.start_server()
        status, payload, _ = self.request("GET", "/api/status?host=kimi")
        self.assertEqual(status, 200)
        for key in ("globalRoot", "realGlobalRoot", "memoryRoot", "configPath"):
            self.assertIn(key, payload["paths"])
            self.assertTrue(payload["paths"][key])
        self.assertIn("external", payload)
        self.assertEqual(set(payload["hosts"]), {"dsh", "kimi", "codebuddy"})
        self.assertIn("label", payload["migration"]["plugin"])
        self.assertIn("reason", payload["migration"]["runtime"])

    def test_internal_error_is_generic(self) -> None:
        self.start_server()
        with mock.patch.object(settings, "build_state", side_effect=RuntimeError("secret traceback")):
            status, payload, _ = self.request("GET", "/api/status?host=kimi")
        self.assertEqual(status, 500)
        self.assertEqual(payload["error"], "internal error")
        self.assertNotIn("secret", json.dumps(payload))

    def test_server_binds_loopback_only(self) -> None:
        self.start_server()
        assert self.server is not None
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertTrue(self.server.url.startswith("http://127.0.0.1:"))
        self.assertIn("#token=", self.server.url)
        self.assertIn("?host=kimi", self.server.url)


class SettingsResetHttpTests(SettingsTestBase):
    def test_reset_keeps_memory_and_only_resets_current_host(self) -> None:
        self.start_server()
        configlib.save("kimi", {"workflowMode": "full-authority"})
        configlib.save("dsh", {"workflowMode": "full-authority"})
        memory_root = hosts.memory_root("kimi")
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "memory.json").write_text('{"entries": [{"id": "u-1"}]}', encoding="utf-8")
        before = (memory_root / "memory.json").read_bytes()
        dsh_before = configlib.config_path("dsh").read_bytes()

        status, payload, _ = self.request(
            "POST", "/api/config?host=kimi",
            body={"host": "kimi", "reset": True},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["reset"])
        self.assertEqual(payload["config"]["workflowMode"], "plan")
        self.assertEqual((memory_root / "memory.json").read_bytes(), before)
        self.assertEqual(configlib.config_path("dsh").read_bytes(), dsh_before)


if __name__ == "__main__":
    unittest.main()
