#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从当前已打开的 Chrome Dev（CDP 端口见 config/browser.json）政务页签读取 localStorage，
写入 packet_lab/out/runtime_auth_headers.json，供 ICPSPClient 优先使用。

不改造官网登录器：你在浏览器里正常扫码/登录即可。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_entry import list_page_targets  # noqa: E402

OUT = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
PORTAL_9087 = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page"
_BROWSER_CFG = ROOT / "config" / "browser.json"


def _cdp_port() -> int:
    with _BROWSER_CFG.open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _eval_raw(ws_url: str, expression: str, timeout_ms: int = 25000) -> Dict[str, Any]:
    ws = websocket.create_connection(ws_url, timeout=12)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": True,
                        "timeout": timeout_ms,
                    },
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _pick_any_page_ws(port: int) -> Optional[str]:
    for p in list_page_targets(port):
        ws = p.get("webSocketDebuggerUrl")
        u = str(p.get("url") or "")
        if ws and u.startswith("https://") and "devtools://" not in u:
            return str(ws)
    return None


def _ensure_9087_portal(ws_url: str) -> None:
    raw = _eval_raw(ws_url, "location.href", timeout_ms=15000)
    href = ""
    try:
        href = str((raw.get("result") or {}).get("result", {}).get("value") or "")
    except Exception:
        pass
    if ":9087/" in href and "icpsp-web-pc" in href:
        return
    nav = json.dumps(PORTAL_9087, ensure_ascii=False)
    _eval_raw(ws_url, f"location.href = {nav}", timeout_ms=60000)
    time.sleep(4)


def main() -> int:
    port = _cdp_port()
    ws_url = _pick_any_page_ws(port)
    if not ws_url:
        print(
            f"ERROR: no https page on CDP {port} (请先双击 打开登录器.cmd 启动 Chrome Dev，见 config/browser.json)",
            file=sys.stderr,
        )
        return 2
    _ensure_9087_portal(ws_url)
    js = r"""(function(){
      return {
        href: location.href,
        Authorization: localStorage.getItem('Authorization')||'',
        topToken: localStorage.getItem('top-token')||'',
        cookie: document.cookie||''
      };
    })()"""
    msg = _eval_raw(ws_url, js, timeout_ms=25000)
    res = msg.get("result") or {}
    if res.get("exceptionDetails"):
        print("ERROR: CDP exception", json.dumps(res.get("exceptionDetails"), ensure_ascii=False), file=sys.stderr)
        return 3
    if (res.get("result") or {}).get("subtype") == "error":
        print("ERROR: evaluate error", json.dumps(res.get("result"), ensure_ascii=False), file=sys.stderr)
        return 3
    inner = res.get("result") or {}
    val = inner.get("value")
    if not isinstance(val, dict):
        print("ERROR: unexpected CDP return", json.dumps(msg, ensure_ascii=False)[:2000], file=sys.stderr)
        return 3
    auth = str(val.get("Authorization") or "").strip()
    if len(auth) != 32:
        print("ERROR: Authorization missing or not 32-hex (请先在本机 Chrome 完成登录)", file=sys.stderr)
        print(json.dumps(val, ensure_ascii=False, indent=2))
        return 4
    top = str(val.get("topToken") or "").strip()
    cookie = str(val.get("cookie") or "").strip()
    headers = {
        "Authorization": auth,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html",
        "User-Agent": "Mozilla/5.0",
    }
    if top:
        headers["top-token"] = top
    if cookie:
        headers["Cookie"] = cookie
    payload = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Synced from live browser localStorage via CDP (runtime only). Do not commit.",
        "base_url": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "source": {"kind": "cdp_live", "page_url": val.get("href")},
        "headers": headers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("page", val.get("href"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
