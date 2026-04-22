#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/final_breakthrough_safe_flowsave.json")


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
            "step": "install_safe_flowsave_and_call",
            "data": c.ev(
                r"""(async function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}
                    return null;
                  }
                  var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};
                  window.__safe_trace=[];
                  function tr(x){window.__safe_trace.push(x);}
                  if(!vm.__orig_flowSave) vm.__orig_flowSave=vm.flowSave;
                  if(!vm.__orig_fzjgFlowSave) vm.__orig_fzjgFlowSave=vm.fzjgFlowSave;

                  vm.flowSave = async function(){
                    tr({t:Date.now(),m:'flowSave_wrapper_enter'});
                    try{
                      var r = vm.__orig_flowSave.apply(this, arguments);
                      if(r&&typeof r.then==='function'){
                        try{ await r; tr({t:Date.now(),m:'flowSave_wrapper_resolve'}); return r; }
                        catch(e){ tr({t:Date.now(),m:'flowSave_wrapper_reject',err:String(e)}); }
                      }else{
                        tr({t:Date.now(),m:'flowSave_wrapper_return_nonpromise'});
                        return r;
                      }
                    }catch(e){
                      tr({t:Date.now(),m:'flowSave_wrapper_throw',err:String(e)});
                    }
                    try{
                      var r2 = vm.__orig_fzjgFlowSave && vm.__orig_fzjgFlowSave.apply(this, arguments);
                      tr({t:Date.now(),m:'fallback_fzjgFlowSave_called'});
                      return r2;
                    }catch(e2){
                      tr({t:Date.now(),m:'fallback_fzjgFlowSave_throw',err:String(e2)});
                      throw e2;
                    }
                  };

                  // ensure core fields
                  vm.$set(vm.form,'entType','4540');
                  vm.$set(vm.form,'nameCode','0');
                  vm.$set(vm.form,'havaAdress','1');
                  vm.$set(vm.form,'distCode','450102');
                  vm.$set(vm.form,'streetCode','450102');
                  vm.$set(vm.form,'streetName','兴宁区');
                  vm.$set(vm.form,'address','兴宁区');
                  vm.$set(vm.form,'detAddress','容州大道88号');

                  // click standard next
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(btn){btn.click(); tr({t:Date.now(),m:'btn_click'});}
                  await new Promise(r=>setTimeout(r,1000));
                  return {ok:true,trace:window.__safe_trace,btn:btn?{cls:(btn.className||'')+'',disabled:!!btn.disabled}:null};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "net_after", "data": c.net(8)})
    rec["steps"].append({"step": "trace_after", "data": c.ev("window.__safe_trace||[]")})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var t=(document.body.innerText||'');return {href:location.href,hash:location.hash,hasYunbangban:t.indexOf('云帮办流程模式选择')>=0,btn:[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled,cls:(b.className||'')+''})).slice(0,3)};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

