#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_base_state_machine_trace.json")
URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.idx = 1

    def ev(self, expr: str, timeout=60000):
        i = self.idx
        self.idx += 1
        self.ws.send(
            json.dumps(
                {
                    "id": i,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
                }
            )
        )
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == i:
                return (((msg or {}).get("result") or {}).get("result") or {}).get("value")

    def close(self):
        self.ws.close()


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p.get("webSocketDebuggerUrl")
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_target_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.ev(f"location.href={json.dumps(URL, ensure_ascii=False)}")
    time.sleep(4)

    rec["steps"].append(
        {
            "step": "inject_trace",
            "data": c.ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'index_vm_not_found'};
                  window.__guide_trace=[];
                  var names=['validateEntType','queryExtraDto','checkchange','changeEntType','flowSave','fzjgFlowSave','validateDetailAddress','init','getQueryNameEntTypeTwo','concatenateNameAndCode'];
                  names.forEach(function(k){
                    if(typeof vm[k]==='function'){
                      var old=vm[k];
                      if(old.__wrapped) return;
                      var wrapped=function(){
                        window.__guide_trace.push({t:Date.now(),method:k,args:[].slice.call(arguments).map(function(a){try{return JSON.stringify(a).slice(0,120)}catch(e){return String(a)}})});
                        return old.apply(this,arguments);
                      };
                      wrapped.__wrapped=true;
                      vm[k]=wrapped;
                    }
                  });
                  return {ok:true,wrapped:names.filter(function(k){return typeof vm[k]==='function'}),form:vm.form||null,dataKeys:Object.keys(vm.$data||{})};
                })()"""
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "simulate_clicks",
            "data": c.ev(
                r"""(async function(){
                  function clickTxt(t){
                    var els=[...document.querySelectorAll('button,.el-button,label,span,div,a,li')].filter(e=>e.offsetParent!==null);
                    for(var e of els){
                      var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx===t || tx.indexOf(t)>=0){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return true;}
                    }
                    return false;
                  }
                  var out={};
                  out.click_not_apply=clickTxt('未申请');
                  await new Promise(r=>setTimeout(r,400));
                  out.click_next=clickTxt('下一步');
                  await new Promise(r=>setTimeout(r,400));
                  out.click_confirm=clickTxt('确定');
                  await new Promise(r=>setTimeout(r,1000));
                  out.href=location.href; out.hash=location.hash;
                  out.trace=(window.__guide_trace||[]).slice(-30);
                  return out;
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "manual_call",
            "data": c.ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  var out={};
                  try{vm&&vm.flowSave&&vm.flowSave(); out.flowSave='called';}catch(e){out.flowSave='err:'+String(e);}
                  try{vm&&vm.fzjgFlowSave&&vm.fzjgFlowSave(); out.fzjgFlowSave='called';}catch(e){out.fzjgFlowSave='err:'+String(e);}
                  out.trace=(window.__guide_trace||[]).slice(-30);
                  out.hash=location.hash;
                  return out;
                })()"""
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

