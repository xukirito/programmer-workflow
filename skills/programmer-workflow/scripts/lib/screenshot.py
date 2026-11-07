"""Cross-platform screenshot capture for model-based visual recognition.

Windows uses a PowerShell/GDI helper; Linux uses the first available native
capture tool. The module captures and copies the PNG only. A host Agent reads
the image with its own multimodal capability; no local OCR engine is invoked.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from . import common, environment

SCREEN_WORDS = {"screen", "desktop", "full", "all", "屏幕", "全屏", "桌面", "整个屏幕", "整个桌面"}


def _powershell() -> str:
    if os.name != "nt":
        return ""
    return shutil.which("powershell") or shutil.which("pwsh") or ""


def _run(args: List[str], *, input_text: str | None = None, timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _run_bytes(args: List[str], *, data: bytes | None = None, timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        input=data,
        capture_output=True,
        timeout=timeout,
    )


def _image_size(path: Path) -> tuple[int, int]:
    try:
        raw = path.read_bytes()[:32]
    except OSError:
        return 0, 0
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        import struct

        width, height = struct.unpack(">II", raw[16:24])
        return int(width), int(height)
    return 0, 0


def _tail(text: str, limit: int = 1500) -> str:
    text = (text or "").strip()
    return text[-limit:]


def _parse_json(text: str) -> Dict[str, Any] | None:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def screenshot_path(workspace: Path, explicit: str | None = None) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if explicit:
        base = Path(workspace).resolve()
        target = (base / Path(explicit)).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"screenshot output must stay inside the workspace: {explicit}") from exc
        return target
    return common.workspace_state(workspace) / "screenshots" / f"{stamp}.png"


def list_windows(workspace: Path) -> Dict[str, Any]:
    os_id = environment.local_os()
    if os_id == "windows":
        ps = _powershell()
        script = Path(__file__).resolve().parents[1] / "platform" / "windows_capture.ps1"
        if not ps or not script.is_file():
            return {"ok": False, "error": "PowerShell helper not found", "windows": []}
        try:
            proc = _run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File", str(script), "-ListMode", "1"], timeout=60)
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"ok": False, "error": str(error), "windows": []}
        data = _parse_json(proc.stdout) or {}
        return {"ok": bool(data.get("ok")), "windows": data.get("windows") or [], "error": data.get("error") or _tail(proc.stderr)}
    if os_id in ("linux", "macos"):
        names: List[Dict[str, str]] = []
        wmctrl = shutil.which("wmctrl")
        if wmctrl:
            try:
                proc = _run([wmctrl, "-l"], timeout=20)
                for line in proc.stdout.splitlines():
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        names.append({"title": parts[3], "process": "", "id": parts[0]})
            except (OSError, subprocess.TimeoutExpired):
                pass
        if not names:
            xdotool = shutil.which("xdotool")
            if xdotool:
                try:
                    proc = _run([xdotool, "search", "--onlyvisible", "--name", "."], timeout=20)
                    for window_id in proc.stdout.split():
                        title = ""
                        try:
                            title = _run([xdotool, "getwindowname", window_id], timeout=10).stdout.strip()
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                        if title:
                            names.append({"title": title, "process": "", "id": window_id})
                except (OSError, subprocess.TimeoutExpired):
                    pass
        return {"ok": True, "windows": names[:60]}
    return {"ok": False, "error": f"unsupported OS: {os_id}", "windows": []}


def _capture_windows(target: str, out: Path, copy_mode: str) -> Dict[str, Any]:
    ps = _powershell()
    script = Path(__file__).resolve().parents[1] / "platform" / "windows_capture.ps1"
    if not ps:
        return {"ok": False, "error": "powershell not found"}
    if not script.is_file():
        return {"ok": False, "error": f"capture helper missing: {script}"}
    args = [
        ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File", str(script),
        "-Target", target, "-Out", str(out), "-CopyMode", copy_mode,
    ]
    try:
        proc = _run(args, timeout=120)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "screenshot timed out"}
    except OSError as error:
        return {"ok": False, "error": str(error)}
    data = _parse_json(proc.stdout)
    if not data:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "capture helper returned no JSON")[-1500:]}
    if not data.get("ok"):
        data["error"] = data.get("error") or "capture failed"
    return data


def _first_tool(names: List[str]) -> str:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return ""


def _focus_window(target: str) -> str:
    if not target or target.lower() in SCREEN_WORDS:
        return ""
    wmctrl = shutil.which("wmctrl")
    if wmctrl:
        try:
            _run([wmctrl, "-a", target], timeout=10)
            return "wmctrl"
        except (OSError, subprocess.TimeoutExpired):
            pass
    xdotool = shutil.which("xdotool")
    if xdotool:
        try:
            found = _run([xdotool, "search", "--name", target], timeout=10).stdout.split()
            if found:
                _run([xdotool, "windowactivate", "--sync", found[-1]], timeout=10)
                return "xdotool"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ""


def _copy_linux_image(path: Path) -> str:
    copy_image = _first_tool(["wl-copy", "xclip"])
    if not copy_image:
        return "none"
    try:
        name = Path(copy_image).name
        if name == "xclip":
            _run([copy_image, "-selection", "clipboard", "-t", "image/png", "-i", str(path)], timeout=20)
        else:
            _run_bytes([copy_image, "--type", "image/png"], data=path.read_bytes(), timeout=20)
        return "image"
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return "failed"


def _capture_linux(target: str, out: Path, copy_mode: str) -> Dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    full = not target or target.strip().lower() in SCREEN_WORDS
    tool = ""
    if full:
        tool = _first_tool(["grim", "gnome-screenshot", "spectacle", "scrot", "import"])
    else:
        focused = _focus_window(target)
        if focused:
            tool = _first_tool(["gnome-screenshot", "spectacle", "scrot", "import"])
        if not tool:
            tool = _first_tool(["import", "gnome-screenshot", "spectacle"])
    if not tool:
        return {"ok": False, "error": "no screenshot tool found; install grim, gnome-screenshot, spectacle, scrot or ImageMagick import"}

    name = Path(tool).name
    try:
        if name == "grim":
            proc = _run([tool, str(out)], timeout=30)
        elif name == "gnome-screenshot":
            args = [tool, "-f", str(out)]
            if not full:
                args.insert(1, "-w")
            proc = _run(args, timeout=30)
        elif name == "spectacle":
            args = [tool, "-b", "-n", "-o", str(out)]
            if not full:
                args.insert(1, "-a")
            proc = _run(args, timeout=30)
        elif name == "scrot":
            args = [tool, str(out)]
            if not full:
                args.insert(1, "-u")
            proc = _run(args, timeout=30)
        else:
            if full:
                proc = _run([tool, "-window", "root", str(out)], timeout=30)
            else:
                return {"ok": False, "error": "specific-window capture needs gnome-screenshot, spectacle or scrot; ImageMagick import only supports full screen here"}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}
    if proc.returncode != 0 or not out.is_file():
        return {"ok": False, "error": (proc.stderr or proc.stdout or f"{name} failed")[-1200:]}

    clipboard = _copy_linux_image(out) if copy_mode != "none" else "none"
    width, height = _image_size(out)
    return {
        "ok": True,
        "path": str(out),
        "window": "screen" if full else target,
        "width": width,
        "height": height,
        "recognition": "model",
        "clipboard": clipboard,
        "tool": name,
    }


def capture(workspace: Path, target: str, *, out: Path, copy_mode: str = "auto") -> Dict[str, Any]:
    os_id = environment.local_os()
    if os_id == "windows":
        result = _capture_windows(target, out, copy_mode)
    elif os_id == "linux":
        result = _capture_linux(target, out, copy_mode)
    elif os_id == "macos":
        tool = shutil.which("screencapture")
        if not tool:
            return {"ok": False, "error": "screencapture not found"}
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = _run([tool, "-x", str(out)], timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"ok": False, "error": str(error)}
        if proc.returncode != 0 or not out.is_file():
            return {"ok": False, "error": (proc.stderr or "screencapture failed")[-1200:]}
        return {"ok": True, "path": str(out), "window": "screen", "width": 0, "height": 0, "recognition": "model", "clipboard": "none"}
    else:
        return {"ok": False, "error": f"unsupported OS: {os_id}"}
    result.setdefault("path", str(out))
    if result.get("ok"):
        result.setdefault("recognition", "model")
    return result


def format_result(result: Dict[str, Any], target: str = "") -> str:
    if not result.get("ok"):
        lines = [f"截图失败：{result.get('error') or 'unknown error'}"]
        windows = result.get("windows")
        if windows:
            lines.append("可用窗口：" + "；".join(str(item) for item in windows[:8]))
        return "\n".join(lines)
    lines = [f"截图已保存：{result.get('path')}"]
    if result.get("window"):
        lines.append(f"目标：{result.get('window')}（{result.get('width')}×{result.get('height')}）")
    lines.append("识别方式：由大模型读取 PNG；未调用本机 OCR。")
    clipboard = result.get("clipboard")
    if clipboard == "image":
        lines.append("已复制截图图片到剪贴板。")
    elif clipboard == "failed":
        lines.append("剪贴板写入失败；图片仍保存在上面的路径。")
    else:
        lines.append("未写入剪贴板（copy_mode=none 或没有可用剪贴板工具）。")
    return "\n".join(lines)
