from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HostPluginTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("WC_NODE"), "Node is not configured (set WC_NODE)")
    def test_per_host_config_and_strict_rejection(self) -> None:
        proc = subprocess.run(
            [os.environ["WC_NODE"], str(ROOT / "tests" / "host_plugin_test.mjs")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    @unittest.skipUnless(os.environ.get("WC_NODE"), "Node is not configured (set WC_NODE)")
    def test_client_bundle_registers_through_module_loader(self) -> None:
        proc = subprocess.run(
            [os.environ["WC_NODE"], str(ROOT / "tests" / "client_plugin_test.mjs")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
