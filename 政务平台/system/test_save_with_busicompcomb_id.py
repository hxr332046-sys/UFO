#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/test_save_with_busicompcomb_id.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in p.get("url", ""):
            target = p
            break
    rec = {"steps": []}
    if not target:
        rec["error"] = "no_basic_info_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)

    def ev(expr, timeout=60000):
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")

    s1 = ev(
        r"""(async function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          var ret={};
          try{
            var r1=await fc.initBusinessInfoList('ManyCertRegistration');
            ret.mcCompId=r1&&r1.linkData&&r1.linkData.busiCompComb&&r1.linkData.busiCompComb.id||null;
          }catch(e){ret.mcErr=String(e);}
          try{
            var r2=await fc.initBusinessInfoList('OpManyAddress');
            ret.opCompId=r2&&r2.linkData&&r2.linkData.busiCompComb&&r2.linkData.busiCompComb.id||null;
          }catch(e){ret.opErr=String(e);}
          var id = ret.opCompId || ret.mcCompId || '';
          if(id){
            fc.$set(fc,'busiCompUrlPaths',[{compUrl:'BasicInfo',id:id}]);
            fc.$set(fc,'curCompUrlPath',['BasicInfo']);
            if(fc.params&&fc.params.flowData){
              fc.params.flowData.currCompUrl='BasicInfo';
            }
          }
          return {id:id,busiCompUrlPaths:fc.busiCompUrlPaths,flowData:fc.params&&fc.params.flowData||null,detail:ret};
        })()"""
    )
    rec["steps"].append({"step": "S1_extract_and_inject_id", "data": s1})

    s2 = ev(
        r"""(function(){
          window.__save_with_id={req:null,resp:null};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments)};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('operationBusinessData')>=0){
              window.__save_with_id.req={u:u,m:this.__m||'POST',len:(b||'').length,body:(b||'').slice(0,560)};
              var self=this;
              self.addEventListener('load',function(){window.__save_with_id.resp={status:self.status,text:(self.responseText||'').slice(0,520)};});
            }
            return os.apply(this,arguments);
          };
          return {ok:true};
        })()"""
    )
    rec["steps"].append({"step": "S2_hook_save", "data": s2})

    s3 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{ok:false,err:'no_fc'};
          try{ fc.save(null,null,'working'); return {ok:true}; }catch(e){ return {ok:false,err:String(e)}; }
        })()"""
    )
    rec["steps"].append({"step": "S3_trigger_save", "data": s3})
    time.sleep(8)

    s4 = ev("window.__save_with_id")
    rec["steps"].append({"step": "S4_save_capture", "data": s4})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

