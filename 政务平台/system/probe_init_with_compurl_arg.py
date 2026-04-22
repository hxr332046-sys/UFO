#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/probe_init_with_compurl_arg.json")


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

    def ev(expr, timeout=20000):
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")

    s1 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          window.__arg_probe={reqs:[],resps:[]};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('/icpsp-api/')>=0){
              window.__arg_probe.reqs.push({m:this.__m||'GET',u:u.slice(0,200),len:(b||'').length,body:(b||'').slice(0,260)});
              var self=this;
              self.addEventListener('load',function(){window.__arg_probe.resps.push({u:u.slice(0,200),status:self.status,text:(self.responseText||'').slice(0,260)});});
            }
            return os.apply(this,arguments);
          };
          return {ok:true};
        })()"""
    )
    rec["steps"].append({"step": "S1_hook", "data": s1})

    s2 = ev(
        r"""(async function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          var out={};
          try{
            if(typeof fc.initBusinessDataInfo==='function'){
              var r1=fc.initBusinessDataInfo('BasicInfo');
              out.r1Type=typeof r1;
              if(r1&&typeof r1.then==='function'){ await r1; out.r1Await='ok'; }
            }
          }catch(e){ out.r1Err=String(e); }
          try{
            if(typeof fc.initBusinessInfoList==='function'){
              var r2=fc.initBusinessInfoList('BasicInfo');
              out.r2Type=typeof r2;
              if(r2&&typeof r2.then==='function'){ await r2; out.r2Await='ok'; }
            }
          }catch(e){ out.r2Err=String(e); }
          return out;
        })()"""
    )
    rec["steps"].append({"step": "S2_call_with_arg", "data": s2})
    time.sleep(5)

    s3 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; var p=fc&&fc.params?fc.params:{};
          return {
            flowData:p.flowData||null,
            busiCompUrlPaths:fc?fc.busiCompUrlPaths:null,
            probe:window.__arg_probe||null
          };
        })()"""
    )
    rec["steps"].append({"step": "S3_after", "data": s3})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

