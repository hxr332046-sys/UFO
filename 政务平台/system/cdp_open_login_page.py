#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在已开启的 CDP Chrome（9087）当前目标页签打开统一认证登录页，便于重新登录。

步骤间使用 config/human_pacing.json 的类人节奏，避免刚连上 CDP 就整页跳转触发风控。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
LOGIN_URL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage"
)


def _cdp_port() -> int:
    with (ROOT / "config" / "browser.json").open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def main() -> int:
    ap = argparse.ArgumentParser(description="CDP 打开统一认证登录页（类人节奏）")
    ap.add_argument("--human-fast", action="store_true", help="关闭类人节奏（仅调试）")
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=bool(args.human_fast))

    port = _cdp_port()
    try:
        pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
    except Exception as e:
        print("ERROR: CDP 不可用，请先运行 打开登录器.cmd 或 scripts\\launch_browser.py", e)
        return 2
    # 刚拿到页签列表后略等，避免与首页渲染/请求叠在一起
    sleep_human(1.35)
    icpsp = [p for p in pages if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in (p.get("url") or "")]
    target = icpsp[0] if icpsp else next((p for p in pages if p.get("type") == "page" and not (p.get("url") or "").startswith("devtools://")), None)
    if not target or not target.get("webSocketDebuggerUrl"):
        print("ERROR: 无可用 page 目标")
        return 2
    ws_url = target["webSocketDebuggerUrl"]
    print("目标页签:", target.get("url"))
    sleep_human(1.85)
    ws = websocket.create_connection(ws_url, timeout=15)
    try:
        sleep_human(0.95)
        expr = f"location.href = {json.dumps(LOGIN_URL, ensure_ascii=False)}"
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True},
                }
            )
        )
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
        print("已导航至:", LOGIN_URL)
        sleep_human(1.1)
        return 0
    finally:
        try:
            ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
