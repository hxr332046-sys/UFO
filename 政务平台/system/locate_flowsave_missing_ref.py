#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/locate_flowsave_missing_ref.json")


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=10):
        if params is None:
            params = {}
        cid = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == cid:
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}, timeout=12)
        return (((r or {}).get("result") or {}).get("value"))


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    rec["steps"].append(
        {
            "step": "probe_refs_and_methods",
            "data": c.ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};
                  var refs=vm.$refs||{};
                  var refInfo={};
                  Object.keys(refs).forEach(function(k){
                    var r=refs[k];
                    if(Array.isArray(r)){
                      refInfo[k]=r.map(function(it){
                        return {
                          isNull:it==null,
                          name:it&&it.$options?it.$options.name:null,
                          hasGetFormData:!!(it&&typeof it.getFormData==='function')
                        };
                      });
                    }else{
                      refInfo[k]={
                        isNull:r==null,
                        name:r&&r.$options?r.$options.name:null,
                        hasGetFormData:!!(r&&typeof r.getFormData==='function')
                      };
                    }
                  });
                  return {
                    ok:true,
                    form:vm.form||null,
                    refKeys:Object.keys(refs),
                    refs:refInfo,
                    methodKeys:Object.keys((vm.$options&&vm.$options.methods)||{}),
                    dataKeys:Object.keys(vm.$data||{})
                  };
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "capture_flowsave_throw_detail",
            "data": c.ev(
                r"""(async function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}
                    return null;
                  }
                  var vm=(function(){var app=document.getElementById('app');return app&&app.__vue__?walk(app.__vue__,0):null;})();
                  if(!vm) return {ok:false,msg:'no_vm'};
                  try{
                    var r=vm.flowSave();
                    if(r&&typeof r.then==='function'){
                      try{await r; return {ok:true,status:'resolved'};}
                      catch(e){ return {ok:false,status:'rejected',err:String(e),stack:(e&&e.stack?String(e.stack).slice(0,1000):'')};}
                    }
                    return {ok:true,status:'returned_non_promise'};
                  }catch(e){
                    return {ok:false,status:'thrown',err:String(e),stack:(e&&e.stack?String(e.stack).slice(0,1000):'')};
                  }
                })()"""
            ),
        }
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

