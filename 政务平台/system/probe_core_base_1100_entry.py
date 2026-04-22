#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
探测是否可直接从 core 入口拉起 1100/02_4 新草稿流。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_core_base_1100_entry_latest.json")
URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or ""):
            return p.get("webSocketDebuggerUrl"), p.get("url")
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 60000):
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
    end = time.time() + 45
    try:
        while time.time() < end:
            try:
                m = json.loads(ws.recv())
            except Exception:
                continue
            if m.get("id") == 1:
                return ((m.get("result") or {}).get("result") or {}).get("value")
    finally:
        ws.close()
    return None


def main() -> int:
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "nav_core_1100", "data": ev(ws, f"location.href={json.dumps(URL, ensure_ascii=False)}", 60000)})
    time.sleep(5.0)
    rec["steps"].append(
        {
            "step": "after",
            "data": ev(
                ws,
                r"""(function(){
                  var txt=(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim();
                  return {href:location.href,hash:location.hash,title:document.title,snippet:txt.slice(0,260)};
                })()""",
                30000,
            ),
        }
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

