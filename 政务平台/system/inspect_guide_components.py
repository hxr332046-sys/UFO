#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import requests
import websocket


def eval_js(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=12)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            ws_url = p.get("webSocketDebuggerUrl")
            break
    if not ws_url:
        print(json.dumps({"error": "no_guide_page"}, ensure_ascii=False))
        return
    expr = r"""(function(){
      function walk(vm,d,res){
        if(!vm||d>12) return;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n){
          res.push({name:n, funcs:Object.keys(vm).filter(function(k){return typeof vm[k]==='function';}).slice(0,40)});
        }
        (vm.$children||[]).forEach(function(c){walk(c,d+1,res);});
      }
      var out=[];
      var app=document.getElementById('app');
      if(app&&app.__vue__) walk(app.__vue__,0,out);
      return out;
    })()"""
    print(json.dumps(eval_js(ws_url, expr), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

