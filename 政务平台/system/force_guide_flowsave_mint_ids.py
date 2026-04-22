#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/force_guide_flowsave_mint_ids.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or "") and "icpsp-web-pc" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": [{"step": "S0_pick", "data": {"url": cur}}]}
    if not ws_url:
        rec["error"] = "no_page"
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

    # hook xhr + fetch
    rec["steps"].append(
        {
            "step": "S1_hook",
            "data": ev(
                r"""(function(){
                  window.__fg={reqs:[],resps:[]};
                  if(window.__fg_hooked) return {ok:true,already:true};
                  window.__fg_hooked=true;
                  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
                  XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
                  XMLHttpRequest.prototype.send=function(b){
                    var u=this.__u||'';
                    if(u.indexOf('/icpsp-api/')>=0){
                      window.__fg.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,900)});
                      var self=this; self.addEventListener('load',function(){
                        window.__fg.resps.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,900)});
                      });
                    }
                    return os.apply(this,arguments);
                  };
                  var of=window.fetch;
                  window.fetch=function(){
                    try{
                      var url=arguments[0]||'';
                      var opt=arguments[1]||{};
                      var m=(opt.method||'GET')+'';
                      var body=(opt.body||'')+'';
                      if(typeof url==='string' && url.indexOf('/icpsp-api/')>=0){
                        window.__fg.reqs.push({t:Date.now(),m:m,u:url.slice(0,260),body:body.slice(0,900),via:'fetch'});
                      }
                    }catch(e){}
                    return of.apply(this,arguments).then(function(resp){
                      try{
                        var url=(arguments[0]&&arguments[0].url)||'';
                        if(url.indexOf('/icpsp-api/')>=0){
                          resp.clone().text().then(function(tx){
                            window.__fg.resps.push({t:Date.now(),u:url.slice(0,260),status:resp.status,text:(tx||'').slice(0,900),via:'fetch'});
                          });
                        }
                      }catch(e){}
                      return resp;
                    });
                  };
                  return {ok:true};
                })()"""
            ),
        }
    )

    # set vm.form + click precise labels + call flowSave()
    stamp = str(int(time.time()))
    rec["steps"].append(
        {
            "step": "S2_set_and_flowsave",
            "data": ev(
                rf"""(function(){{
                  function walk(vm,d){{
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var c of (vm.$children||[])){{var r=walk(c,d+1); if(r) return r;}}
                    return null;
                  }}
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {{ok:false,msg:'no_vm'}};
                  vm.form=vm.form||{{}};
                  vm.distList=['450000','450100','450102','450102'];
                  vm.$set(vm.form,'distList',vm.distList);
                  vm.$set(vm.form,'entType','4540');
                  vm.$set(vm.form,'nameCode','0');
                  vm.$set(vm.form,'havaAdress','1');
                  vm.$set(vm.form,'distCode','450102');
                  vm.$set(vm.form,'streetCode','450102');
                  vm.$set(vm.form,'streetName','兴宁区');
                  vm.$set(vm.form,'address','兴宁区');
                  vm.$set(vm.form,'detAddress','容州大道88号');
                  // 给 rule 里可能要求的字段塞值（即使 UI 未展示）
                  vm.$set(vm.form,'name', '广西智信'+'{stamp}'+'（个人独资）');
                  vm.$set(vm.form,'number', 'AUTO'+ '{stamp}');
                  function clickLabel(t){{
                    // 只点业务单选标签，避免误点整个容器
                    var labels=[...document.querySelectorAll('label.tni-radio,.tni-radio')].filter(n=>n.offsetParent!==null);
                    for(var n of labels){{
                      var tx=(n.textContent||'').replace(/\\s+/g,' ').trim();
                      if(tx===t||tx.indexOf(t)>=0){{ n.dispatchEvent(new MouseEvent('click',{{bubbles:true,cancelable:true,view:window}})); return tx; }}
                    }}
                    return null;
                  }}
                  var a=clickLabel('个人独资企业');
                  var b=clickLabel('未申请');
                  // 关掉提示弹窗
                  var okBtn=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).find(x=>((x.textContent||'').replace(/\\s+/g,'').indexOf('确定')>=0));
                  if(okBtn) okBtn.click();
                  try{{ vm.flowSave(); }}catch(e){{ return {{ok:false,msg:String(e),a:a,b:b,form:vm.form}}; }}
                  return {{ok:true,a:a,b:b,form:vm.form}};
                }})()"""
            ),
        }
    )
    time.sleep(10)
    rec["steps"].append({"step": "S3_state", "data": ev(r"""(function(){return {href:location.href,hash:location.hash,title:document.title};})()""", 15000)})
    rec["steps"].append({"step": "S4_cap", "data": ev(r"""(function(){return window.__fg||null;})()""", 15000)})

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

