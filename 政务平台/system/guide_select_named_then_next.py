#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_select_named_then_next.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
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
    ws, url = pick_ws()
    rec["steps"].append({"step": "S1_start", "data": url})
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append(
        {
            "step": "S2_select_named",
            "data": ev(
                ws,
                r"""(function(){
                  var els=[...document.querySelectorAll('label,span,div,li,a')].filter(e=>e.offsetParent!==null);
                  for(var e of els){
                    var t=(e.textContent||'').replace(/\s+/g,' ').trim();
                    if(t==='已办理企业名称预保留' || t.indexOf('已办理企业名称预保留')>=0){
                      e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                      return {clicked:true,text:t};
                    }
                  }
                  return {clicked:false};
                })()""",
            ),
        }
    )
    time.sleep(2)

    rec["steps"].append(
        {
            "step": "S3_click_next",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
                  if(!b) return {clicked:false};
                  b.click();
                  return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(2)

    rec["steps"].append(
        {
            "step": "S4_click_confirm_if_any",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0&&!x.disabled);
                  if(!b) return {clicked:false};
                  b.click();
                  return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(5)

    rec["steps"].append(
        {
            "step": "S5_after",
            "data": ev(
                ws,
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').trim(),disabled:!!x.disabled}));
                  return {href:location.href,hash:location.hash,buttons:btns.slice(0,20)};
                })()""",
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

