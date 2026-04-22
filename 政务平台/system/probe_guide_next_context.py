#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_guide_next_context.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=20)
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
                return msg
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr, timeout=70000):
        msg = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            timeout=15,
        )
        return ((msg.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main():
    ws, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "picked_url": cur, "steps": []}
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws)
    c.call("Page.enable", {})
    c.call("Network.enable", {})
    c.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", timeout=20000)
    time.sleep(5)

    rec["steps"].append(
        {
            "step": "guide_snapshot",
            "data": c.ev(
                r"""(function(){
                  return {
                    href:location.href,hash:location.hash,
                    text:(document.body.innerText||'').slice(0,800)
                  };
                })()"""
            ),
        }
    )

    for mode in ["1", "0"]:
        rec["steps"].append(
            {
                "step": f"flowSave_havaAdress_{mode}",
                "data": c.ev(
                    r"""(async function(mode){
                      function walk(vm,d){
                        if(!vm||d>18) return null;
                        var n=(vm.$options&&vm.$options.name)||'';
                        if(n==='index'&&typeof vm.flowSave==='function') return vm;
                        for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}
                        return null;
                      }
                      function clickText(t){
                        var nodes=[...document.querySelectorAll('label,span,div,.tni-radio,.tni-radio__label')].filter(x=>x.offsetParent!==null);
                        for(var n of nodes){
                          var tx=(n.textContent||'').replace(/\s+/g,' ').trim();
                          if(tx===t||tx.indexOf(t)>=0){
                            ['mousedown','mouseup','click'].forEach(function(tp){
                              n.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));
                            });
                            return tx;
                          }
                        }
                        return null;
                      }
                      var app=document.getElementById('app');
                      var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                      if(!vm) return {ok:false,msg:'no_vm'};
                      clickText('个人独资企业');
                      clickText('未申请');
                      vm.form=vm.form||{};
                      vm.$set(vm.form,'entType','4540');
                      vm.$set(vm.form,'nameCode','0');
                      vm.$set(vm.form,'havaAdress',mode);
                      vm.$set(vm.form,'distCode','450102');
                      vm.$set(vm.form,'streetCode','450102');
                      vm.$set(vm.form,'streetName','兴宁区');
                      vm.$set(vm.form,'address','兴宁区');
                      vm.$set(vm.form,'detAddress','容州大道88号');
                      var flowRet=null, flowErr=null;
                      try{
                        flowRet=vm.flowSave();
                        if(flowRet&&typeof flowRet.then==='function'){
                          try{ flowRet=await flowRet; }catch(e){ flowErr=String(e); }
                        }
                      }catch(e){
                        flowErr=String(e);
                      }
                      var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
                      if(ok) ok.click();
                      await new Promise(function(r){setTimeout(r,1200);});
                      return {
                        ok:true,mode:mode,flowRet:flowRet,flowErr:flowErr,
                        href:location.href,hash:location.hash,form:vm.form
                      };
                    })(%s)""" % json.dumps(mode, ensure_ascii=False)
                ),
            }
        )
        time.sleep(2)

    rec["steps"].append(
        {
            "step": "final_snapshot",
            "data": c.ev(
                r"""(function(){
                  function find(vm,d){
                    if(!vm||d>20) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='flow-control') return vm;
                    for(var c of (vm.$children||[])){var r=find(c,d+1);if(r)return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var fc=app&&app.__vue__?find(app.__vue__,0):null;
                  return {
                    href:location.href,hash:location.hash,
                    text:(document.body.innerText||'').slice(0,900),
                    flowData:fc&&fc.params?fc.params.flowData:null
                  };
                })()"""
            ),
        }
    )

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
