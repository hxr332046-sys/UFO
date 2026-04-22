#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/advance_guide_to_basicinfo_02_4.json")
URL_GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=30000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["steps"].append({"step": "S1_start", "data": cur})
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append({"step": "S2_open_guide", "data": ev(ws, f"location.href='{URL_GUIDE}'", timeout=15000)})
    time.sleep(7)
    ws, _ = pick_ws()

    for i in range(5):
        st = ev(
            ws,
            r"""(function(){
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').trim(),disabled:!!x.disabled}));
              return {href:location.href,hash:location.hash,btns:btns.slice(0,20)};
            })()""",
        )
        rec["steps"].append({"step": f"Loop_{i}_state", "data": st})
        h = (st or {}).get("hash", "")
        href = (st or {}).get("href", "")
        if "core.html#/flow/base/basic-info" in href or "#/flow/base/basic-info" in h:
            rec["reached_basic_info"] = True
            break

        click = ev(
            ws,
            r"""(function(){
              var targets=['继续办理设立登记','完成并提交','我已阅读并同意','下一步','确定'];
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null&&!x.disabled);
              for(var t of targets){
                for(var b of btns){
                  var txt=(b.textContent||'').trim();
                  if(txt.indexOf(t)>=0){b.click(); return {clicked:true,text:txt,target:t};}
                }
              }
              return {clicked:false};
            })()""",
        )
        rec["steps"].append({"step": f"Loop_{i}_click", "data": click})
        time.sleep(5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

