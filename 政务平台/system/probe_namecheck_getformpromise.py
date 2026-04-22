#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_namecheck_getformpromise.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = websocket.create_connection(ws, timeout=20)
    expr = r"""(async function(){
      function walk(vm,d){
        if(!vm||d>20) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && vm.$parent && vm.$parent.$options && vm.$parent.$options.name==='name-check-info') return vm;
        for(var ch of (vm.$children||[])){ var r=walk(ch,d+1); if(r) return r; }
        return null;
      }
      var app=document.getElementById('app');
      var vm=app&&app.__vue__?walk(app.__vue__,0):null;
      if(!vm) return {ok:false,msg:'no_vm'};
      if(typeof vm.getFormPromise!=='function') return {ok:false,msg:'no_getFormPromise'};
      try{
        var p=vm.getFormPromise();
        if(p&&typeof p.then==='function'){
          try{
            await p;
            return {ok:true,status:'resolved'};
          }catch(e){
            return {ok:false,status:'rejected',err:String(e),stack:(e&&e.stack)?String(e.stack):''};
          }
        }
        return {ok:true,status:'returned_non_promise'};
      }catch(e){
        return {ok:false,status:'throw',err:String(e),stack:(e&&e.stack)?String(e.stack):''};
      }
    })()"""
    payload = {
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
    }
    c.send(json.dumps(payload))
    msg = None
    while True:
        m = json.loads(c.recv())
        if m.get("id") == 1:
            msg = m
            break
    c.close()
    rec["raw"] = msg
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

