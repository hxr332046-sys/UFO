#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出当前页面已安装的 window.__ufo_cap.items（XHR/fetch hook 缓存），用于对齐“此名称可以申报”那一刻的数据包。
不点击、不等待。
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_dump_ufo_cap.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, ""


def ev(ws_url, expr, timeout_ms=90000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.settimeout(2.0)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            }
        )
    )
    end = time.time() + 20
    try:
        while time.time() < end:
            try:
                msg = json.loads(ws.recv())
            except Exception:
                continue
            if msg.get("id") == 1:
                return (msg.get("result") or {}).get("result", {}).get("value")
        return {"error": "timeout"}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "page": cur}
    if not ws_url:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["cap"] = ev(
        ws_url,
        r"""(function(){
          var cap = window.__ufo_cap || window.__ufo_cap || null;
          if(!cap) return {ok:false,reason:'no_cap'};
          var items = cap.items || [];
          return {ok:true,count:items.length,items:items};
        })()""",
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

