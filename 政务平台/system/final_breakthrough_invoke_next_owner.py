#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/final_breakthrough_invoke_next_owner.json")


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

    def net(self, sec=5):
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

    rec["steps"].append(
        {
            "step": "find_next_owner_chain",
            "data": c.ev(
                r"""(function(){
                  try{
                  function fnNames(vm){
                    var out=[];
                    var ms=(vm&&vm.$options&&vm.$options.methods)||{};
                    Object.keys(ms).forEach(function(k){
                      if(/next|step|save|submit|flow|check|valid|click|handle/i.test(k)) out.push(k);
                    });
                    return out.slice(0,80);
                  }
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!btn) return {ok:false,msg:'no_next_btn'};
                  var chain=[]; var el=btn; var hops=0;
                  while(el && hops<25){
                    var vm=el.__vue__;
                    chain.push({
                      tag:el.tagName||'',
                      cls:(el.className||'')+'',
                      text:(el.textContent||'').replace(/\s+/g,' ').trim().slice(0,80),
                      hasVue:!!vm,
                      vmName:vm&&vm.$options?((vm.$options.name||'')):null,
                      vmFns:vm?fnNames(vm):[]
                    });
                    el=el.parentElement; hops++;
                  }
                  return {
                    ok:true,
                    btnClass:(btn.className||'')+'',
                    btnText:(btn.textContent||'').replace(/\s+/g,' ').trim(),
                    chain:chain
                  };
                  }catch(e){
                    return {ok:false,error:String(e),stack:(e&&e.stack?String(e.stack).slice(0,500):'')};
                  }
                })()"""
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "install_owner_hook_and_invoke",
            "data": c.ev(
                r"""(function(){
                  try{
                  window.__owner_trace=[];
                  function mark(x){window.__owner_trace.push(x);}
                  function wrapVm(vm){
                    if(!vm) return [];
                    var hit=[];
                    var ms=(vm&&vm.$options&&vm.$options.methods)||{};
                    Object.keys(ms).forEach(function(k){
                      if(/next|step|save|submit|flow|check|valid|click|handle/i.test(k)){
                        if(typeof vm[k]!=='function') return;
                        var old=vm[k];
                        if(old.__owner_hooked) return;
                        vm[k]=(function(name,orig){
                          var fn=function(){
                            mark({t:Date.now(),name:name,phase:'enter'});
                            try{
                              var r=orig.apply(this,arguments);
                              if(r&&typeof r.then==='function'){
                                mark({t:Date.now(),name:name,phase:'promise'});
                                return r.then(function(v){mark({t:Date.now(),name:name,phase:'resolve'});return v;})
                                        .catch(function(e){mark({t:Date.now(),name:name,phase:'reject',err:String(e)});throw e;});
                              }
                              mark({t:Date.now(),name:name,phase:'return'});
                              return r;
                            }catch(e){
                              mark({t:Date.now(),name:name,phase:'throw',err:String(e)});
                              throw e;
                            }
                          };
                          fn.__owner_hooked=true;
                          return fn;
                        })(k,old);
                        hit.push(k);
                      }
                    });
                    return hit;
                  }
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!btn) return {ok:false,msg:'no_btn'};
                  var owners=[]; var el=btn; var hops=0;
                  while(el && hops<25){
                    if(el.__vue__) owners.push(el.__vue__);
                    el=el.parentElement; hops++;
                  }
                  var wrapped=[];
                  owners.forEach(function(vm){
                    wrapped.push({name:(vm.$options&&vm.$options.name)||'',fns:wrapVm(vm)});
                  });

                  // direct invoke candidates on owners
                  var invoked=[];
                  function tryInvoke(vm, names){
                    if(!vm) return;
                    names.forEach(function(n){
                      if(typeof vm[n]==='function'){
                        try{ vm[n](); invoked.push(n+':ok'); }catch(e){ invoked.push(n+':err:'+String(e)); }
                      }
                    });
                  }
                  owners.forEach(function(vm){
                    tryInvoke(vm,['handleClick','handleStepsNext','next','nextBtn','submit','save','flowSave','fzjgFlowSave']);
                  });

                  // also native click fallback
                  try{btn.click(); invoked.push('btn.click:ok');}catch(e){invoked.push('btn.click:err:'+String(e));}
                  return {ok:true,wrapped:wrapped,invoked:invoked};
                  }catch(e){
                    return {ok:false,error:String(e),stack:(e&&e.stack?String(e.stack).slice(0,500):'')};
                  }
                })()"""
            ),
        }
    )

    rec["steps"].append({"step": "network_after_invoke", "data": c.net(8)})
    rec["steps"].append({"step": "owner_trace", "data": c.ev("window.__owner_trace||[]")})
    rec["steps"].append(
        {
            "step": "final_state",
            "data": c.ev(
                r"""(function(){
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  var txt=(document.body&&document.body.innerText)||'';
                  var errs=[...document.querySelectorAll('.el-form-item__error')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  return {
                    href:location.href,hash:location.hash,
                    hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
                    btn:btn?{cls:(btn.className||'')+'',disabled:!!btn.disabled,text:(btn.textContent||'').replace(/\s+/g,' ').trim()}:null,
                    errs:errs
                  };
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

