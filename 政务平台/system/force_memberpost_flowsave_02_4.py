#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/force_memberpost_flowsave_02_4.json")


def ev(ws_url, expr, timeout=60000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_member_post"
    else:
        rec["steps"].append(
            {
                "step": "hook",
                "data": ev(
                    ws,
                    r"""(function(){
                      window.__m_req=window.__m_req||[];
                      if(!window.__m_hook){
                        window.__m_hook=true;
                        var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
                        XMLHttpRequest.prototype.send=function(b){
                          var u=this.__u||'';
                          if(u.indexOf('/icpsp-api/')>=0){
                            window.__m_req.push({t:Date.now(),m:this.__m,u:u.slice(0,240),body:(b||'').slice(0,300)});
                          }
                          return os.apply(this,arguments);
                        };
                      }
                      return {ok:true};
                    })()""",
                ),
            }
        )
        rec["steps"].append(
            {
                "step": "call_flowsave",
                "data": ev(
                    ws,
                    r"""(async function(){
                      function walk(vm,d){
                        if(!vm||d>12) return null;
                        var n=(vm.$options&&vm.$options.name)||'';
                        if(n==='MemberPost' && typeof vm.flowSave==='function') return vm;
                        var ch=vm.$children||[];
                        for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
                        return null;
                      }
                      var root=document.getElementById('app').__vue__;
                      var m=walk(root,0);
                      if(!m) return {ok:false,msg:'no_memberpost_vm'};
                      try{ m.flowSave(); }catch(e){ return {ok:false,msg:String(e)}; }
                      return {ok:true,hash:location.hash};
                    })()""",
                ),
            }
        )
        time.sleep(8)
        rec["steps"].append({"step": "after_hash", "data": ev(ws, "location.href + ' | ' + location.hash")})
        rec["steps"].append({"step": "reqs", "data": ev(ws, "(window.__m_req||[]).slice(-10)")})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

