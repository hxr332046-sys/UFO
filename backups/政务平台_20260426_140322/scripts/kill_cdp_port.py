"""关闭占用 config/browser.json cdp_port 的浏览器进程（仅 chrome/msedge），用于切换浏览器。"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "browser.json"


def _port() -> int:
    with CFG.open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _find_pid_on_port(port: int) -> list[int]:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, encoding="utf-8", errors="replace")
    except Exception as e:
        print("netstat failed:", e, file=sys.stderr)
        return []
    pids: set[int] = set()
    needle = f":{port} "
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        if needle not in line:
            continue
        parts = line.split()
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        pids.add(pid)
    return sorted(pids)


def _process_name(pid: int) -> str:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in out.splitlines():
            cells = [c.strip().strip('"') for c in line.split(",")]
            if cells and cells[0]:
                return cells[0]
    except Exception:
        pass
    return ""


def main() -> int:
    port = _port()
    pids = _find_pid_on_port(port)
    if not pids:
        print(f"no process listening on {port}")
        return 0
    for pid in pids:
        name = _process_name(pid)
        if name.lower() not in ("chrome.exe", "msedge.exe"):
            print(f"skip non-browser pid={pid} name={name}")
            continue
        print(f"killing pid={pid} name={name} (port {port})")
        try:
            subprocess.check_call(["taskkill", "/PID", str(pid), "/F", "/T"], stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print(f"taskkill failed for pid={pid}: {e}", file=sys.stderr)
    time.sleep(2)
    still = _find_pid_on_port(port)
    print("remaining on port:", still)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
