#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/locate_flowsave_undefined_prop.json")


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
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}, timeout=15)
        if "error" in r:
            return {"_cdp_error": r["error"]}
        return (((r or {}).get("result") or {}).get("value"))


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws)
    data = c.ev(
        r"""(async function(){
          function walk(vm,d){if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
          if(!vm) return {ok:false,msg:'no_vm'};
          var undefReads=[];
          var fnReads=[];
          var p = new Proxy(vm,{
            get(target,prop,recv){
              var v = Reflect.get(target,prop,recv);
              if(v===undefined) undefReads.push(String(prop));
              else if(typeof v==='function') fnReads.push(String(prop));
              return v;
            },
            has(target,prop){ return Reflect.has(target,prop); }
          });
          var status='unknown', err='', stack='';
          try{
            var r = vm.flowSave.call(p);
            status = 'returned';
            if(r && typeof r.then==='function'){
              status='promise';
              try{ await r; status='resolved'; }
              catch(e){ status='rejected'; err=String(e); stack=(e&&e.stack)?String(e.stack):''; }
            }
          }catch(e){
            status='throw'; err=String(e); stack=(e&&e.stack)?String(e.stack):'';
          }
          var uniq = Array.from(new Set(undefReads));
          return {ok:true,status:status,err:err,stack:stack,undefinedProps:uniq.slice(0,120),functionReads:Array.from(new Set(fnReads)).slice(0,80)};
        })()"""
    )
    rec["steps"].append({"step": "proxy_call_flowsave", "data": data})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

