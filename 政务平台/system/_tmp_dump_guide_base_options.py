#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    if not ws_url:
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type") == "page"][0]
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=30000, awaitp=True):
        nonlocal mid
        mid += 1
        ws.send(
            json.dumps(
                {
                    "id": mid,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": awaitp,
                        "timeout": timeout,
                    },
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    # 强制导航到 02_4 / 4540 的 guide/base
    target = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="
    ev(f"location.href={json.dumps(target, ensure_ascii=False)}", 60000)

    expr = r"""(function(){
      function vis(el){return !!(el&&el.offsetParent!==null);}
      function txt(el){return ((el&&el.textContent)||'').replace(/\s+/g,' ').trim();}
      var radios=[...document.querySelectorAll('.el-radio, label.el-radio')].filter(vis).map(r=>({text:txt(r).slice(0,80),cls:(r.className||'').slice(0,60)}));
      var cbs=[...document.querySelectorAll('.el-checkbox, label.el-checkbox')].filter(vis).map(r=>({text:txt(r).slice(0,80),cls:(r.className||'').slice(0,60)}));
      var btns=[...document.querySelectorAll('button,.el-button')].filter(vis).map(b=>({text:txt(b).slice(0,40),disabled:!!b.disabled,cls:(b.className||'').slice(0,60)}));
      return {href:location.href,hash:location.hash,radios:radios.slice(0,30),checkboxes:cbs.slice(0,30),buttons:btns.slice(0,30),text:(document.body&&document.body.innerText||'').slice(0,600)};
    })()"""
    info = ev(expr, 30000)
    print(json.dumps(info, ensure_ascii=False, indent=2)[:8000])
    ws.close()


if __name__ == "__main__":
    main()

