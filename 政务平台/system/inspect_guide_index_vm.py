#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import requests
import websocket


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=12)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            ws = p["webSocketDebuggerUrl"]
            break
    if not ws:
        print(json.dumps({"error": "no_guide_page"}, ensure_ascii=False))
        return
    expr = r"""(function(){
      function walk(vm,d,out){
        if(!vm||d>12) return;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && typeof vm.flowSave==='function'){
          out.push({
            name:n,
            dataKeys:Object.keys(vm.$data||{}).slice(0,80),
            hasInit:typeof vm.init==='function',
            hasFlowSave:typeof vm.flowSave==='function',
            hasFzjgFlowSave:typeof vm.fzjgFlowSave==='function',
            flowSaveSrc:String(vm.flowSave).slice(0,1200),
            fzjgFlowSaveSrc:String(vm.fzjgFlowSave||'').slice(0,1200)
          });
        }
        (vm.$children||[]).forEach(function(c){walk(c,d+1,out);});
      }
      var out=[]; var app=document.getElementById('app'); if(app&&app.__vue__) walk(app.__vue__,0,out);
      return out;
    })()"""
    print(json.dumps(ev(ws, expr), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

