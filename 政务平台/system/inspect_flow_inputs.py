#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/flow_input_context.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/" in p.get("url", ""):
            target = p
            break
    if not target:
        OUT.write_text(json.dumps({"error": "no_core_page"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)
    expr = r"""(function(){
      function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
      var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
      var ls={};
      for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i); if(/flow|busi|name|extra|token|continue/i.test(k)){ls[k]=localStorage.getItem(k);} }
      return {
        href:location.href,
        hash:location.hash,
        search:location.search,
        params:fc?fc.params:null,
        fromPage:fc?fc.fromPage:null,
        extraParams:fc?fc.extraParams:null,
        jumpParams:fc?fc.jumpParams:null,
        localStorage:ls
      };
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "timeout": 20000}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            data = m.get("result", {}).get("result", {}).get("value")
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved: {OUT}")
            break
    ws.close()


if __name__ == "__main__":
    main()

