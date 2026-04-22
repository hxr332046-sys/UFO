#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/bridge_success_to_fill_snapshot.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=20000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"steps": []}
    ws, url = pick_ws()
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["steps"].append({"step": "S1_start", "data": {"url": url}})

    snap1 = ev(
        ws,
        r"""(function(){
          var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;}).map(function(b){return (b.textContent||'').trim();}).filter(Boolean);
          return {href:location.href,hash:location.hash,title:document.title,buttons:btns.slice(0,20)};
        })()""",
    )
    rec["steps"].append({"step": "S2_success_page_snapshot", "data": snap1})

    click = ev(
        ws,
        r"""(function(){
          var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;});
          for(var i=0;i<btns.length;i++){
            var t=(btns[i].textContent||'').trim();
            if(t.indexOf('继续办理设立登记')>=0 || t.indexOf('继续办理')>=0){
              btns[i].click();
              return {clicked:true,text:t};
            }
          }
          return {clicked:false};
        })()""",
    )
    rec["steps"].append({"step": "S3_click_continue", "data": click})

    time.sleep(6)

    snap2 = ev(
        ws,
        r"""(function(){
          var fields=[];
          var items=document.querySelectorAll('.el-form-item');
          for(var i=0;i<items.length;i++){
            var lb=items[i].querySelector('.el-form-item__label');
            var input=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
            var val='';
            if(input) val=(input.value||'').trim();
            fields.push({label:(lb&&lb.textContent||'').trim(),value:val,hasInput:!!input});
          }
          var filled=fields.filter(function(f){return f.value&&f.value.length>0;}).length;
          var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
          return {
            href:location.href,
            hash:location.hash,
            formItems:items.length,
            filledCount:filled,
            errors:errs,
            sampleFilled:fields.filter(function(f){return f.value;}).slice(0,20)
          };
        })()""",
    )
    rec["steps"].append({"step": "S4_fill_page_snapshot", "data": snap2})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

