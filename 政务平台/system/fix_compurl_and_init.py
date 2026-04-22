#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/fix_compurl_and_init.json")


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

    def ev(expr, timeout=15000):
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")

    s1 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          var p=fc.params||{};
          if(!p.flowData) p.flowData={};
          p.flowData.currCompUrl='BasicInfo';
          fc.$set(fc,'params',p);
          fc.$set(fc,'curCompUrl','BasicInfo');
          fc.$set(fc,'curCompName','basic-info');
          fc.$set(fc,'curCompUrlPath',['BasicInfo']);
          fc.$set(fc,'busiCompUrlPaths',[{compUrl:'BasicInfo',id:''}]);

          window.__fix_init_probe={reqs:[],resps:[]};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('/icpsp-api/')>=0){
              window.__fix_init_probe.reqs.push({m:this.__m||'GET',u:u.slice(0,180),len:(b||'').length,body:(b||'').slice(0,220)});
              var self=this;
              self.addEventListener('load',function(){window.__fix_init_probe.resps.push({u:u.slice(0,180),status:self.status,text:(self.responseText||'').slice(0,260)});});
            }
            return os.apply(this,arguments);
          };
          return {ok:true,curCompUrl:fc.curCompUrl,flowData:p.flowData,busiCompUrlPaths:fc.busiCompUrlPaths};
        })()"""
    )
    rec["steps"].append({"step": "S1_fix_compurl", "data": s1})

    s2 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          var out={called:[]};
          try{ if(typeof fc.initData==='function'){ fc.initData(); out.called.push('initData'); } }catch(e){ out.initDataErr=String(e); }
          try{ if(typeof fc.initBusinessDataInfo==='function'){ fc.initBusinessDataInfo(); out.called.push('initBusinessDataInfo'); } }catch(e){ out.initBusinessDataInfoErr=String(e); }
          try{ if(typeof fc.initBusinessInfoList==='function'){ fc.initBusinessInfoList(); out.called.push('initBusinessInfoList'); } }catch(e){ out.initBusinessInfoListErr=String(e); }
          return out;
        })()"""
    )
    rec["steps"].append({"step": "S2_call_inits", "data": s2})
    time.sleep(8)

    s3 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; var p=fc&&fc.params?fc.params:{};
          return {flowData:p.flowData||null,busiCompUrlPaths:fc?fc.busiCompUrlPaths:null,probe:window.__fix_init_probe||null};
        })()"""
    )
    rec["steps"].append({"step": "S3_after", "data": s3})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

