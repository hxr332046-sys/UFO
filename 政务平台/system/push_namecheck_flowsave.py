#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/push_namecheck_flowsave.json")


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=12):
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
                return msg
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            timeout=16,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def net(self, sec=6):
        reqs, resps = [], []
        end = time.time() + sec
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                r = p.get("request", {})
                reqs.append({"url": (r.get("url") or "")[:240], "method": r.get("method"), "postData": (r.get("postData") or "")[:400]})
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                r = p.get("response", {})
                resps.append({"url": (r.get("url") or "")[:240], "status": r.get("status")})
        return {"reqs": reqs, "resps": resps}


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})
    rec["steps"].append({"step": "before", "data": c.ev(r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10)};})()""")})
    rec["steps"].append(
        {
            "step": "invoke_flowSave",
            "data": c.ev(
                r"""(async function(){
                  function walk(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&vm.$parent&&vm.$parent.$options&&vm.$parent.$options.name==='name-check-info')return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}return null;}
                  var app=document.getElementById('app');var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};
                  try{
                    var r=vm.flowSave();
                    if(r&&typeof r.then==='function'){
                      try{await r;return {ok:true,status:'resolved'};}
                      catch(e){return {ok:false,status:'rejected',err:String(e),stack:(e&&e.stack)?String(e.stack):''};}
                    }
                    return {ok:true,status:'returned_non_promise'};
                  }catch(e){
                    return {ok:false,status:'throw',err:String(e),stack:(e&&e.stack)?String(e.stack):''};
                  }
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "network", "data": c.net(8)})
    rec["steps"].append({"step": "after", "data": c.ev(r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

