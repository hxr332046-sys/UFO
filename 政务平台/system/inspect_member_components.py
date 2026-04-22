#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import requests
import websocket


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            ws = p["webSocketDebuggerUrl"]
            break
    if not ws:
        print(json.dumps({"error": "no_member_post_page"}, ensure_ascii=False))
        return
    expr = r"""(function(){
      function walk(vm,d,o){
        if(!vm||d>9) return;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n){
          o.push({
            name:n,
            funcs:Object.keys(vm).filter(function(k){return typeof vm[k]==='function';}).slice(0,20)
          });
        }
        (vm.$children||[]).forEach(function(c){walk(c,d+1,o);});
      }
      var out=[];
      var app=document.getElementById('app');
      if(app&&app.__vue__) walk(app.__vue__,0,out);
      return out;
    })()"""
    print(json.dumps(ev(ws, expr), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

