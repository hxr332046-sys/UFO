#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/round3_force_guide_flowsave.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = pick_ws()
    rec["steps"].append({"step": "start", "data": url})
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append(
        {
            "step": "hook",
            "data": ev(
                ws,
                r"""(function(){
                  window.__fg_cap={reqs:[],resps:[]};
                  if(!window.__fg_hook){
                    window.__fg_hook=true;
                    var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
                    XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
                    XMLHttpRequest.prototype.send=function(b){
                      var u=this.__u||'';
                      if(u.indexOf('/icpsp-api/')>=0){
                        window.__fg_cap.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,700)});
                        var self=this; self.addEventListener('load',function(){
                          window.__fg_cap.resps.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,1000)});
                        });
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
            "step": "force_flow_save",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_guide_vm'};

                  // force expected values
                  if(vm.form){
                    vm.$set(vm.form,'isnameType','0'); // 未申请
                    if(!vm.form.entType || vm.form.entType==='') vm.$set(vm.form,'entType','4540');
                    if(!vm.form.choiceName || vm.form.choiceName==='') vm.$set(vm.form,'choiceName','0');
                  }
                  var rt={ok:true};
                  try{
                    vm.flowSave();
                    rt.flowSave='called';
                  }catch(e){rt.flowSave='err:'+String(e);}
                  await new Promise(r=>setTimeout(r,1500));
                  try{
                    vm.fzjgFlowSave();
                    rt.fzjgFlowSave='called';
                  }catch(e){rt.fzjgFlowSave='err:'+String(e);}
                  await new Promise(r=>setTimeout(r,1500));
                  var next=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
                  if(next){next.click(); rt.next='clicked';}
                  var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
                  if(ok){ok.click(); rt.confirm='clicked';}
                  await new Promise(r=>setTimeout(r,3000));
                  rt.href=location.href; rt.hash=location.hash;
                  return rt;
                })()""",
            ),
        }
    )
    time.sleep(2)
    rec["steps"].append(
        {
            "step": "after",
            "data": ev(
                ws,
                r"""(function(){
                  return {
                    href:location.href,hash:location.hash,
                    text:(document.body.innerText||'').slice(0,1000),
                    reqs:(window.__fg_cap&&window.__fg_cap.reqs||[]).slice(-10),
                    resps:(window.__fg_cap&&window.__fg_cap.resps||[]).slice(-10)
                  };
                })()""",
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

