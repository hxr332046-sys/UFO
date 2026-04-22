#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 CDP 当前政务页签读取登录态摘要（stdout JSON，不含完整 token）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))


def _cdp_port() -> int:
    with (ROOT / "config" / "browser.json").open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _pick_target(pages: list) -> dict | None:
    icpsp = [
        p
        for p in pages
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in (p.get("url") or "")
    ]
    if icpsp:
        return icpsp[0]
    for p in pages:
        if p.get("type") == "page" and not (p.get("url") or "").startswith("devtools://"):
            return p
    return None


def _eval(ws_url: str, expression: str) -> dict:
    ws = websocket.create_connection(ws_url, timeout=15)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            )
        )
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                return msg
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _mask(s: str, head: int = 6) -> str:
    if not s:
        return ""
    if len(s) <= head + 3:
        return "***"
    return s[:head] + "…" + f"(len={len(s)})"


def main() -> int:
    port = _cdp_port()
    try:
        pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"CDP unavailable: {e}"}, ensure_ascii=False))
        return 2
    target = _pick_target(pages)
    if not target or not target.get("webSocketDebuggerUrl"):
        print(json.dumps({"ok": False, "error": "no page target"}, ensure_ascii=False))
        return 2
    ws_url = target["webSocketDebuggerUrl"]
    url = target.get("url") or ""
    js = r"""(function(){
      var ls={};
      for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);ls[k]=localStorage.getItem(k);}
      var app=document.getElementById('app')&&document.getElementById('app').__vue__;
      var store=app&&app.$store;
      var login=store&&store.state&&store.state.login;
      return {
        href: location.href,
        localStorageKeys: Object.keys(ls).sort(),
        topToken: ls['top-token']||'',
        authorization: ls['Authorization']||'',
        bodyHasLoginWords: /登录|注册|扫码/.test(document.body.innerText||''),
        vueHasLoginModule: !!login,
        vueTokenLen: login&&login.token ? String(login.token).length : 0,
        vueHasUserInfo: !!(login&&login.userInfo)
      };
    })()"""
    msg = _eval(ws_url, js)
    res = (msg.get("result") or {}).get("result", {})
    if res.get("subtype") == "error" or not res.get("value"):
        print(
            json.dumps(
                {"ok": False, "tab_url": url, "cdp_error": res},
                ensure_ascii=False,
            )
        )
        return 3
    v = res["value"]
    top = str(v.get("topToken") or "")
    auth = str(v.get("authorization") or "")
    out = {
        "ok": True,
        "cdp_port": port,
        "target_tab_url": url,
        "href": v.get("href"),
        "localStorage_keys": v.get("localStorageKeys"),
        "likely_logged_in_storage": len(top) >= 16 and len(auth) >= 16,
        "top_token": _mask(top),
        "authorization": _mask(auth),
        "dom_suggests_guest_bar": bool(v.get("bodyHasLoginWords")),
        "vue_login_module": bool(v.get("vueHasLoginModule")),
        "vue_token_length": int(v.get("vueTokenLen") or 0),
        "vue_has_user_info": bool(v.get("vueHasUserInfo")),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
