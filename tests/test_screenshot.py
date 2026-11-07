from __future__ import annotations

import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / ".tmp-tests"
TEST_TMP.mkdir(exist_ok=True)
SCRIPTS = ROOT / "skills" / "programmer-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib import screenshot  # noqa: E402


class ScreenshotTests(unittest.TestCase):
    def test_result_requires_model_and_copies_png_without_local_ocr(self) -> None:
        result = {
            "ok": True,
            "path": "shot.png",
            "window": "中文窗口",
            "width": 800,
            "height": 600,
            "recognition": "model",
            "clipboard": "image",
        }
        text = screenshot.format_result(result)
        self.assertIn("中文窗口", text)
        self.assertIn("大模型读取 PNG", text)
        self.assertIn("已复制截图图片", text)
        self.assertNotIn("tesseract", text.lower())

    def test_windows_helper_receives_no_ocr_argument(self) -> None:
        out = TEST_TMP / ("shot-" + uuid.uuid4().hex + ".png")
        response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"ok":true,"window":"中文窗口","recognition":"model","clipboard":"image"}\n',
            stderr="",
        )
        with mock.patch.object(screenshot, "_powershell", return_value="powershell"), \
             mock.patch.object(screenshot, "_run", return_value=response) as run:
            result = screenshot._capture_windows("中文窗口", out, "auto")
        args = run.call_args[0][0]
        self.assertNotIn("-Ocr", args)
        self.assertEqual(result["recognition"], "model")
        self.assertEqual(result["window"], "中文窗口")

    def test_output_path_stays_inside_workspace(self) -> None:
        workspace = TEST_TMP / ("workspace-" + uuid.uuid4().hex)
        workspace.mkdir()
        try:
            inside = screenshot.screenshot_path(workspace, "captures/shot.png")
            self.assertEqual(inside, (workspace / "captures" / "shot.png").resolve())
            for outside in ("../shot.png", str(TEST_TMP / "absolute.png")):
                with self.assertRaises(ValueError):
                    screenshot.screenshot_path(workspace, outside)
        finally:
            import shutil
            shutil.rmtree(workspace, ignore_errors=True)

    def test_helpers_do_not_contain_local_ocr_or_fullscreen_fallback(self) -> None:
        helper_path = SCRIPTS / "platform" / "windows_capture.ps1"
        helper = helper_path.read_text(encoding="utf-8")
        self.assertTrue(helper_path.read_bytes().startswith(b"\xef\xbb\xbf"), "Windows PowerShell 5 requires a UTF-8 BOM")
        self.assertNotIn("Windows.Media.Ocr", helper)
        self.assertNotIn("Get-PwfOcrText", helper)
        self.assertIn("未执行全屏截图", helper)
        self.assertIn("OutputEncoding", helper)
        linux_source = (SCRIPTS / "lib" / "screenshot.py").read_text(encoding="utf-8")
        self.assertNotIn("tesseract", linux_source.lower())


if __name__ == "__main__":
    unittest.main()
