#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/namecheck_state_snapshot.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            target = p
            break
    if not target:
        OUT.write_text(json.dumps({"error": "no_namecheck_page"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)
    expr = r"""(function(){
      var btns=Array.from(document.querySelectorAll('button,.el-button'))
        .filter(function(b){return b.offsetParent!==null;})
        .map(function(b){return {text:(b.textContent||'').trim(),disabled:!!b.disabled,cls:(b.className||'').slice(0,80)};});
      var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
      function find(vm,d){
        if(!vm||d>20) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='flow-control') return vm;
        var ch=vm.$children||[];
        for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1); if(r) return r;}
        return null;
      }
      var app=document.getElementById('app');
      var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
      var p=fc&&fc.params?fc.params:{};
      return {
        href:location.href,
        hash:location.hash,
        buttons:btns,
        errors:errs,
        curCompUrl:fc?fc.curCompUrl:null,
        flowData:p.flowData||null,
        busiCompUrlPaths:fc?fc.busiCompUrlPaths:null
      };
    })()"""
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "timeout": 15000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            data = msg.get("result", {}).get("result", {}).get("value")
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved: {OUT}")
            break
    ws.close()


if __name__ == "__main__":
    main()

