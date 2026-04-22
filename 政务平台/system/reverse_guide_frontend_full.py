#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_base_frontend_full_reverse.json")
URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.i = 1

    def ev(self, expr: str, timeout=60000):
        my_id = self.i
        self.i += 1
        self.ws.send(
            json.dumps(
                {
                    "id": my_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
                }
            )
        )
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == my_id:
                return (((msg or {}).get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "icpsp-web-pc" in u and "zhjg.scjdglj.gxzf.gov.cn:9087" in u:
            return p.get("webSocketDebuggerUrl")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p.get("webSocketDebuggerUrl")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:6087" in p.get("url", ""):
            return p.get("webSocketDebuggerUrl")
    for p in pages:
        if p.get("type") == "page":
            return p.get("webSocketDebuggerUrl")
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws_url = pick_ws()
    if not ws_url:
        rec["error"] = "no_target_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    cdp = CDP(ws_url)
    cdp.ev(f"location.href={json.dumps(URL, ensure_ascii=False)}")
    time.sleep(4)

    rec["steps"].append(
        {
            "step": "inject_frontend_probe",
            "data": cdp.ev(
                r"""(function(){
                  window.__fg_full={events:[],vmCalls:[],snapshots:[]};
                  if(!window.__fg_full_event_hooked){
                    window.__fg_full_event_hooked=true;
                    function mkPath(n){
                      var a=[]; var cur=n; var k=0;
                      while(cur&&k<8){a.push((cur.tagName||'')+'#'+(cur.id||'')+'.'+((cur.className||'')+'').split(' ').slice(0,2).join('.'));cur=cur.parentElement;k++;}
                      return a;
                    }
                    function recEvt(phase,e){
                      var tx=((e&&e.target&&e.target.textContent)||'').replace(/\s+/g,' ').trim().slice(0,80);
                      window.__fg_full.events.push({
                        t:Date.now(),phase:phase,type:e.type,tx:tx,path:mkPath(e.target||null)
                      });
                      if(window.__fg_full.events.length>300) window.__fg_full.events=window.__fg_full.events.slice(-300);
                    }
                    ['click','mousedown','mouseup'].forEach(function(tp){
                      document.addEventListener(tp,function(e){recEvt('capture',e);},true);
                      document.addEventListener(tp,function(e){recEvt('bubble',e);},false);
                    });
                  }

                  function walk(vm,d,out){
                    if(!vm||d>12) return;
                    var n=(vm.$options&&vm.$options.name)||'';
                    out.push({name:n,hasFlowSave:typeof vm.flowSave==='function',keys:Object.keys(vm.$data||{}).slice(0,60)});
                    (vm.$children||[]).forEach(function(ch){walk(ch,d+1,out);});
                  }
                  var vms=[]; var app=document.getElementById('app'); if(app&&app.__vue__) walk(app.__vue__,0,vms);
                  function pickBizVm(){
                    var app=document.getElementById('app');
                    function w(vm,d){
                      if(!vm||d>12) return null;
                      var n=(vm.$options&&vm.$options.name)||'';
                      if(n==='index'&&typeof vm.flowSave==='function') return vm;
                      for(var ch of (vm.$children||[])){var r=w(ch,d+1);if(r) return r;}
                      return null;
                    }
                    return app&&app.__vue__?w(app.__vue__,0):null;
                  }
                  var vm=pickBizVm();
                  if(vm){
                    var names=['flowSave','fzjgFlowSave','validateEntType','checkchange','changeEntType','queryExtraDto','init'];
                    names.forEach(function(k){
                      if(typeof vm[k]==='function' && !vm[k].__fg_wrapped){
                        var old=vm[k];
                        var fn=function(){
                          window.__fg_full.vmCalls.push({t:Date.now(),m:k,args:[].slice.call(arguments).map(function(a){try{return JSON.stringify(a).slice(0,120)}catch(e){return String(a)}})});
                          return old.apply(this,arguments);
                        };
                        fn.__fg_wrapped=true;
                        vm[k]=fn;
                      }
                    });
                  }
                  var snap={
                    href:location.href,hash:location.hash,
                    localKeys:Object.keys(localStorage||{}).slice(0,60),
                    sessionKeys:Object.keys(sessionStorage||{}).slice(0,60),
                    storeKeys:(window.__store&&window.__store.state)?Object.keys(window.__store.state):[],
                    vmCount:vms.length,
                    vmSample:vms.slice(0,25),
                    bizVmForm:vm&&vm.form?vm.form:null
                  };
                  window.__fg_full.snapshots.push(snap);
                  return {ok:true,snapshot:snap};
                })()"""
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "simulate_actions",
            "data": cdp.ev(
                r"""(async function(){
                  function clickTxt(t){
                    var els=[...document.querySelectorAll('button,.el-button,label,span,div,a,li')].filter(e=>e.offsetParent!==null);
                    for(var e of els){
                      var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx===t||tx.indexOf(t)>=0){
                        e.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
                        e.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}));
                        e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                        return {ok:true,text:tx};
                      }
                    }
                    return {ok:false,text:t};
                  }
                  var out={};
                  out.notApply=clickTxt('未申请');
                  await new Promise(r=>setTimeout(r,300));
                  out.next=clickTxt('下一步');
                  await new Promise(r=>setTimeout(r,300));
                  out.confirm=clickTxt('确定');
                  await new Promise(r=>setTimeout(r,900));
                  out.href=location.href; out.hash=location.hash;
                  out.events=(window.__fg_full&&window.__fg_full.events||[]).slice(-120);
                  out.vmCalls=(window.__fg_full&&window.__fg_full.vmCalls||[]).slice(-50);
                  out.lastSnapshot=(window.__fg_full&&window.__fg_full.snapshots||[]).slice(-1)[0]||null;
                  return out;
                })()"""
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

