#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/click_save_next_after_member_fix_02_4.json")


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        try:
            m = json.loads(ws.recv())
        except Exception:
            continue
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_member_post_page"
    else:
        rec["click"] = ev(
            ws,
            r"""(function(){
              var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null && (x.textContent||'').indexOf('保存并下一步')>=0 && !x.disabled);
              if(!b) return {clicked:false};
              b.click(); return {clicked:true,text:(b.textContent||'').trim()};
            })()""",
        )
        time.sleep(8)
        rec["after"] = ev(
            ws,
            r"""(function(){
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled}));
              var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              return {href:location.href,hash:location.hash,errors:errs.slice(0,10),buttons:btns.slice(0,15),text:(document.body.innerText||'').slice(0,600)};
            })()""",
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

