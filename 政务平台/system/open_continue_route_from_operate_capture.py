#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 auto_pick_enterprise_continue.json 的 captures 里解析 route（字符串 JSON），并跳转到 core.html 的真实路由。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
import websocket

ROOT = Path("G:/UFO/政务平台")
INP = ROOT / "dashboard" / "data" / "records" / "auto_pick_enterprise_continue.json"
OUT = ROOT / "dashboard" / "data" / "records" / "open_continue_route_latest.json"


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or ""):
            return p.get("webSocketDebuggerUrl"), p.get("url")
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 60000) -> Any:
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


def _extract_route_obj(payload_text: str) -> Optional[Dict[str, Any]]:
    try:
        j = json.loads(payload_text)
        busi = (((j.get("data") or {}).get("busiData")) or {})
        route_raw = busi.get("route")
        if isinstance(route_raw, str) and route_raw.strip().startswith("{"):
            return json.loads(route_raw)
        if isinstance(route_raw, dict):
            return route_raw
    except Exception:
        pass
    return None


def _build_url(route: Dict[str, Any]) -> str:
    project = str(route.get("project") or "").strip()
    path = str(route.get("path") or "").strip()
    params = route.get("params") or {}
    base = f"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/{project}.html#{path}"
    if isinstance(params, dict) and params:
        q = "&".join([f"{k}={requests.utils.quote(str(v or ''), safe='')}" for k, v in params.items()])
        return f"{base}?{q}"
    return base


def main() -> int:
    rec: Dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "input": str(INP), "steps": []}
    if not INP.is_file():
        rec["error"] = "missing_input"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    data = json.loads(INP.read_text(encoding="utf-8"))
    caps = (((data.get("pick_and_click") or {}).get("captures")) or [])
    route = None
    for c in caps:
        t = str((c or {}).get("t") or "")
        r = _extract_route_obj(t)
        if r:
            route = r
            break
    rec["route_obj"] = route
    if not route:
        rec["error"] = "no_route_in_captures"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 3
    url = _build_url(route)
    rec["built_url"] = url

    ws, cur = pick_ws()
    rec["picked_url"] = cur
    if not ws:
        rec["error"] = "no_cdp_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 4
    rec["steps"].append({"step": "nav", "data": ev(ws, f"location.href={json.dumps(url, ensure_ascii=False)}", 60000)})
    time.sleep(6)
    rec["steps"].append(
        {
            "step": "after",
            "data": ev(
                ws,
                r"""(function(){
                  var txt=(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim();
                  return {href:location.href,hash:location.hash,title:document.title,hasCore:location.href.indexOf('core.html')>=0,body:txt.slice(0,260)};
                })()""",
                30000,
            ),
        }
    )

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

