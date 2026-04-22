#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP 直达名称核查页（core.html#/flow/base/name-check-info）。
用于当 guide/base “下一步”不跳转时的强制探索（仍不做云提交/最终提交）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/nav_to_namecheck_direct_latest.json")
HOST = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc"


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or ""):
            return p.get("webSocketDebuggerUrl"), p.get("url")
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 60000):
    ws = websocket.create_connection(ws_url, timeout=25)
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
    end = time.time() + 40
    out = None
    while time.time() < end:
        try:
            m = json.loads(ws.recv())
        except Exception:
            continue
        if m.get("id") == 1:
            out = ((m.get("result") or {}).get("result") or {}).get("value")
            break
    ws.close()
    return out


def main() -> int:
    ws, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "picked_url": cur, "steps": []}
    if not ws:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2

    target = f"{HOST}/core.html#/flow/base/name-check-info"
    rec["steps"].append({"step": "nav", "target": target, "data": ev(ws, f"location.href={json.dumps(target, ensure_ascii=False)}")})
    time.sleep(6)
    snap = ev(
        ws,
        r"""(function(){
          var txt=(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim();
          return {href:location.href,hash:location.hash,title:document.title,hasCore:location.href.indexOf('core.html')>=0,body:txt.slice(0,350)};
        })()""",
        timeout_ms=30000,
    )
    rec["steps"].append({"step": "after", "data": snap})

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

