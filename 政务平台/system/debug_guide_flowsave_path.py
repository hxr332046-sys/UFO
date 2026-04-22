#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/debug_guide_flowsave_path.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws_url:
        rec["error"] = "no_guide_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=60000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    rec["steps"].append(
        {
            "step": "instrument",
            "data": ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>18) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    var ch=vm.$children||[];
                    for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=walk(app&&app.__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  window.__dbg={events:[]};
                  function log(x){window.__dbg.events.push({t:Date.now(),x:x});}
                  vm.goHistroy=false;
                  // hook validate
                  if(vm.$refs && vm.$refs.form && vm.$refs.form.validate){
                    var ov=vm.$refs.form.validate.bind(vm.$refs.form);
                    vm.$refs.form.validate=function(cb){
                      log('validate_called');
                      return ov(function(ok){
                        log('validate_cb:'+ok);
                        try{ cb && cb(ok); }catch(e){ log('validate_cb_err:'+String(e)); }
                      });
                    };
                  } else {
                    log('no_form_ref');
                  }
                  // hook api
                  if(vm.$api && vm.$api.guide){
                    if(vm.$api.guide.bindName){
                      var ob=vm.$api.guide.bindName.bind(vm.$api.guide);
                      vm.$api.guide.bindName=function(p){ log('bindName_call:'+JSON.stringify(p||{})); return ob(p).then(function(r){log('bindName_ok'); return r;}).catch(function(e){log('bindName_err:'+String(e)); throw e;}); };
                    }
                    if(vm.$api.guide.checkEstablishName){
                      var oc=vm.$api.guide.checkEstablishName.bind(vm.$api.guide);
                      vm.$api.guide.checkEstablishName=function(p){ log('checkEstablishName_call:'+JSON.stringify(p||{}).slice(0,220)); return oc(p).then(function(r){log('checkEstablishName_ok:'+JSON.stringify(r||{}).slice(0,220)); return r;}).catch(function(e){log('checkEstablishName_err:'+String(e)); throw e;}); };
                    }
                  } else {
                    log('no_api_guide');
                  }
                  // hook router.jump
                  if(vm.$router && vm.$router.jump){
                    var oj=vm.$router.jump.bind(vm.$router);
                    vm.$router.jump=function(p){ log('router_jump:'+JSON.stringify(p||{}).slice(0,260)); return oj(p); };
                  }
                  return {ok:true,goHistroy:vm.goHistroy,href:location.href,hash:location.hash};
                })()"""
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "call_flowsave",
            "data": ev(
                r"""(async function(){
                  function walk(vm,d){if(!vm||d>18)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1);if(r)return r;}return null;}
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  try{
                    var p=vm.flowSave();
                    if(p && typeof p.then==='function'){ await p; }
                    return {ok:true,goHistroy:vm.goHistroy};
                  }catch(e){
                    return {ok:false,err:String(e),goHistroy:vm.goHistroy};
                  }
                })()"""
            ),
        }
    )
    time.sleep(2)
    rec["steps"].append({"step": "events", "data": ev("window.__dbg||null", 20000)})
    rec["steps"].append({"step": "state", "data": ev(r"""(function(){var b=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled,cls:(x.className||'').slice(0,60)}));return {href:location.href,hash:location.hash,buttons:b.slice(0,8)};})()""", 20000)})

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

