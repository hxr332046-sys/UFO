#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/final_breakthrough_patch_getformdata.json")


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
            "step": "patch_and_invoke",
            "data": c.ev(
                r"""(async function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1); if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};
                  var patched=[];
                  // patch refs that may be undefined/without getFormData
                  var refs=vm.$refs||{};
                  Object.keys(refs).forEach(function(k){
                    var r=refs[k];
                    if(Array.isArray(r)){
                      r.forEach(function(it,idx){
                        if(it && typeof it.getFormData!=='function'){
                          it.getFormData=function(){return {};};
                          patched.push(k+'['+idx+']');
                        }
                      });
                    }else if(r && typeof r.getFormData!=='function'){
                      r.getFormData=function(){return {};};
                      patched.push(k);
                    }
                  });

                  // also patch vm direct missing helper
                  if(typeof vm.getFormData!=='function'){
                    vm.getFormData=function(){return vm.form||{};};
                    patched.push('vm.getFormData');
                  }

                  var out={ok:true,patched:patched,calls:[]};
                  try{
                    var r1=vm.flowSave();
                    out.calls.push('flowSave_called');
                    if(r1&&typeof r1.then==='function'){
                      try{await r1; out.calls.push('flowSave_resolve');}
                      catch(e){out.calls.push('flowSave_reject:'+String(e));}
                    }
                  }catch(e){out.calls.push('flowSave_throw:'+String(e));}
                  try{
                    vm.fzjgFlowSave&&vm.fzjgFlowSave();
                    out.calls.push('fzjgFlowSave_called');
                  }catch(e){out.calls.push('fzjgFlowSave_throw:'+String(e));}
                  try{
                    var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                    if(btn){btn.click(); out.calls.push('btn_click');}
                  }catch(e){out.calls.push('btn_click_throw:'+String(e));}
                  return out;
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "net_after", "data": c.net(8)})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,btn:[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled,cls:(b.className||'')+''})).slice(0,5)};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

