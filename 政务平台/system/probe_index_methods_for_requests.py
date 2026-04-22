#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_index_methods_for_requests.json")


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

    def net(self, sec=4):
        reqs = []
        end = time.time() + sec
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                req = p.get("request", {})
                reqs.append({"url": (req.get("url") or "")[:260], "method": req.get("method")})
        return reqs


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "probes": []}
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})
    methods = c.ev(
        r"""(function(){
          function walk(vm,d){if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
          if(!vm) return [];
          return Object.keys((vm.$options&&vm.$options.methods)||{});
        })()"""
    ) or []
    # Focus on methods likely to trigger API/state transitions
    targets = [m for m in methods if any(k in m.lower() for k in ["flow", "save", "query", "init", "change", "address", "check", "validate"])]
    targets = targets[:20]
    for m in targets:
        _ = c.net(0.8)  # flush
        result = c.ev(
            f"""(async function(){{
              function walk(vm,d){{if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var ch of (vm.$children||[])){{var r=walk(ch,d+1);if(r)return r;}}return null;}}
              var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
              if(!vm||typeof vm[{json.dumps(m)}]!=='function') return {{ok:false,msg:'no_method'}};
              try{{
                var r=vm[{json.dumps(m)}]();
                if(r&&typeof r.then==='function'){{
                  try{{await r; return {{ok:true,status:'resolved'}};}}
                  catch(e){{return {{ok:false,status:'rejected',err:String(e)}};}}
                }}
                return {{ok:true,status:'returned'}};
              }}catch(e){{
                return {{ok:false,status:'throw',err:String(e)}};
              }}
            }})()"""
        )
        net = c.net(2.5)
        rec["probes"].append({"method": m, "invoke": result, "netCount": len(net), "netSample": net[:5]})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

