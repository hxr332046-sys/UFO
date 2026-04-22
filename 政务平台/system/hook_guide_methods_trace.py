#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/hook_guide_methods_trace.json")


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
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}, timeout=10)
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
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})

    rec["steps"].append(
        {
            "step": "install_method_hooks",
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
                  window.__guide_method_trace=[];
                  var names=[
                    'validateEntType','queryExtraDto','checkchange','changeEntType','flowSave','fzjgFlowSave',
                    'validateDetailAddress','init','getQueryNameEntTypeTwo','concatenateNameAndCode',
                    'addressChange','getTotalAddress'
                  ];
                  names.forEach(function(k){
                    if(typeof vm[k]!=='function') return;
                    var old=vm[k];
                    if(old.__hooked) return;
                    var fn=function(){
                      var row={t:Date.now(),method:k,phase:'enter'};
                      window.__guide_method_trace.push(row);
                      try{
                        var ret=old.apply(this,arguments);
                        if(ret&&typeof ret.then==='function'){
                          window.__guide_method_trace.push({t:Date.now(),method:k,phase:'promise'});
                          return ret.then(function(v){
                            window.__guide_method_trace.push({t:Date.now(),method:k,phase:'resolve'});
                            return v;
                          }).catch(function(e){
                            window.__guide_method_trace.push({t:Date.now(),method:k,phase:'reject',err:String(e)});
                            throw e;
                          });
                        }
                        window.__guide_method_trace.push({t:Date.now(),method:k,phase:'return'});
                        return ret;
                      }catch(e){
                        window.__guide_method_trace.push({t:Date.now(),method:k,phase:'throw',err:String(e)});
                        throw e;
                      }
                    };
                    fn.__hooked=true;
                    vm[k]=fn;
                  });
                  return {
                    ok:true,
                    hooked:names.filter(function(k){return typeof vm[k]==='function';}),
                    form:vm.form||null
                  };
                })()"""
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "click_next_once",
            "data": c.ev(
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!b) return {ok:false};
                  b.click();
                  return {ok:true,cls:(b.className||'')+'',disabled:!!b.disabled,text:(b.textContent||'').replace(/\s+/g,' ').trim()};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "network_after_click", "data": c.net(6)})
    rec["steps"].append({"step": "method_trace", "data": c.ev("window.__guide_method_trace||[]")})
    rec["steps"].append(
        {
            "step": "final_state",
            "data": c.ev(
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  var errs=[...document.querySelectorAll('.el-form-item__error')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  return {btn:b?{cls:(b.className||'')+'',disabled:!!b.disabled,text:(b.textContent||'').replace(/\s+/g,' ').trim()}:null,errs:errs,href:location.href,hash:location.hash};
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

