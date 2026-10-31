#!/usr/bin/env python3
"""Structural checks for a generated Architecture/Features/Prototype HTML file."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def check(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    result = {
        "path": str(path),
        "bytes": len(text.encode("utf-8")),
        "unresolved_token": "{{WC_" in text,
        "external_http": bool(re.search(r"https?://", text)),
        "external_script": bool(re.search(r"<script[^>]+src=|<link[^>]+href=", text, re.I)),
        "data_kind": None,
        "inline_js_chars": 0,
    }
    match = re.search(r'<script id="wc-data" type="application/json">(.*?)</script>', text, re.S)
    if not match:
        result["error"] = "missing wc-data"
        return result
    payload = json.loads(match.group(1))
    result["data_kind"] = payload.get("data", {}).get("kind")
    script = re.search(r"<script>\s*(.*?)\s*</script>", text, re.S)
    if script:
        result["inline_js_chars"] = len(script.group(1))
        result["script_path"] = str(path.with_name(path.stem + ".inline.js"))
        path.with_name(path.stem + ".inline.js").write_text(script.group(1), encoding="utf-8")
    return result


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_output.py <file.html> [...]", file=sys.stderr)
        return 2
    failed = False
    for name in argv:
        path = Path(name)
        info = check(path)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if info.get("unresolved_token") or info.get("external_http") or info.get("external_script") or info.get("error"):
            failed = True
        node = Path(sys.executable).with_name("node.exe")
        if info.get("script_path"):
            node_cmd = None
            if node.exists():
                node_cmd = str(node)
            else:
                import shutil
                node_cmd = shutil.which("node")
            if node_cmd:
                proc = subprocess.run([node_cmd, "--check", info["script_path"]], capture_output=True, text=True)
                print(f"node --check: {'ok' if proc.returncode == 0 else proc.stderr}")
                if proc.returncode != 0:
                    failed = True
            try:
                Path(info["script_path"]).unlink()
            except OSError:
                pass
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
