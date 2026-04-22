#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or "") and "icpsp-web-pc" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    if not ws_url:
        print(json.dumps({"error": "no_page"}, ensure_ascii=False))
        return
    ws = websocket.create_connection(ws_url, timeout=20)

    def run(i, expr):
        ws.send(json.dumps({"id": i, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == i:
                return m.get("result", {}).get("result", {}).get("value")

    run(1, "location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/company/my-space/space-index'")
    run(2, "(async function(){await new Promise(r=>setTimeout(r,6000)); return {ok:true};})()")
    out = run(
        3,
        r"""(function(){
          var rows=[...document.querySelectorAll('.el-table__body tr')];
          var out=[];
          for(var r of rows){
            var tds=[...r.querySelectorAll('td .cell')].map(x=>(x.textContent||'').replace(/\s+/g,' ').trim());
            var btn=[...r.querySelectorAll('button,.el-button')].map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled,cls:(b.className||'').slice(0,60)}));
            out.push({cells:tds,btns:btn});
          }
          return {href:location.href,hash:location.hash,rowCount:out.length,rows:out.slice(0,10),text:(document.body.innerText||'').slice(0,600)};
        })()""",
    )
    ws.close()
    print(json.dumps(out, ensure_ascii=False, indent=2)[:18000])


if __name__ == "__main__":
    main()

