#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/final_breakthrough_invoke_listener_click.json")


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
                reqs.append({"url": (req.get("url") or "")[:260], "method": req.get("method"), "postData": (req.get("postData") or "")[:500]})
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
            "step": "invoke_listener_click",
            "data": c.ev(
                r"""(async function(){
                  window.__listener_trace=[];
                  function tr(x){window.__listener_trace.push(x);}
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!btn) return {ok:false,msg:'no_btn'};
                  var bvm=btn.__vue__;
                  if(!bvm) return {ok:false,msg:'no_btn_vm'};
                  var fn=(bvm.$listeners||{}).click;
                  if(!fn) return {ok:false,msg:'no_listener_click',listeners:Object.keys(bvm.$listeners||{})};
                  try{
                    tr({t:Date.now(),m:'listener_enter'});
                    var r=fn({type:'click',target:btn,currentTarget:btn});
                    if(r&&typeof r.then==='function'){
                      tr({t:Date.now(),m:'listener_promise'});
                      try{await r; tr({t:Date.now(),m:'listener_resolve'});}catch(e){tr({t:Date.now(),m:'listener_reject',err:String(e)});}
                    }else{
                      tr({t:Date.now(),m:'listener_return'});
                    }
                  }catch(e){
                    tr({t:Date.now(),m:'listener_throw',err:String(e)});
                  }
                  return {ok:true,trace:window.__listener_trace,btn:{cls:(btn.className||'')+'',disabled:!!btn.disabled,text:(btn.textContent||'').replace(/\s+/g,' ').trim()}};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "net_after", "data": c.net(8)})
    rec["steps"].append({"step": "trace_after", "data": c.ev("window.__listener_trace||[]")})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);return b?{cls:(b.className||'')+'',disabled:!!b.disabled,text:(b.textContent||'').replace(/\s+/g,' ').trim()}:null;})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

