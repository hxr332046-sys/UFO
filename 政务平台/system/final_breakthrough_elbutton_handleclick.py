#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/final_breakthrough_elbutton_handleclick.json")


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

    def net(self, sec=8):
        reqs, resps = [], []
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
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                res = p.get("response", {})
                resps.append({"url": (res.get("url") or "")[:260], "status": res.get("status")})
        return {"reqs": reqs, "resps": resps}


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
    c.call("Network.enable", {})
    rec["steps"].append({"step": "net_before", "data": c.net(1.5)})
    rec["steps"].append(
        {
            "step": "invoke_elbutton_handleclick",
            "data": c.ev(
                r"""(function(){
                  window.__elbtn_trace=[];
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!btn) return {ok:false,msg:'no_btn'};
                  var vm=btn.__vue__;
                  if(!vm) return {ok:false,msg:'no_btn_vm'};
                  if(typeof vm.handleClick!=='function') return {ok:false,msg:'no_handleClick'};
                  var old=vm.handleClick;
                  if(!old.__hooked){
                    vm.handleClick=function(){
                      window.__elbtn_trace.push({t:Date.now(),m:'handleClick_enter'});
                      try{
                        var r=old.apply(this,arguments);
                        window.__elbtn_trace.push({t:Date.now(),m:'handleClick_return'});
                        return r;
                      }catch(e){
                        window.__elbtn_trace.push({t:Date.now(),m:'handleClick_throw',err:String(e)});
                        throw e;
                      }
                    };
                    vm.handleClick.__hooked=true;
                  }
                  try{
                    vm.handleClick({type:'click',target:btn,currentTarget:btn});
                    return {ok:true,cls:(btn.className||'')+'',disabled:!!btn.disabled,trace:window.__elbtn_trace};
                  }catch(e){
                    return {ok:false,err:String(e),trace:window.__elbtn_trace};
                  }
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "net_after", "data": c.net(8)})
    rec["steps"].append({"step": "trace_after", "data": c.ev("window.__elbtn_trace||[]")})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);return b?{cls:(b.className||'')+'',disabled:!!b.disabled,text:(b.textContent||'').replace(/\s+/g,' ').trim()}:null;})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

