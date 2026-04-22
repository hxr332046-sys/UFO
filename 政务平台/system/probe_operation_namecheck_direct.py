#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/probe_operation_namecheck_direct.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/" in p.get("url", ""):
            target = p
            break
    rec = {"steps": []}
    if not target:
        rec["error"] = "no_core_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)

    def ev(expr, timeout=40000):
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")

    s1 = ev(
        r"""(async function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          var bdi=JSON.parse(JSON.stringify((fc.$data&&fc.$data.businessDataInfo)||{}));
          bdi.entName=bdi.entName||'广西智信数据科技有限公司';
          bdi.name=bdi.name||'广西智信数据科技有限公司';
          bdi.entType='4540';
          bdi.namePreFlag=false;

          var ret={};
          try{
            var rsp=await fc.operationBusinessDataInfo('tempSave','NameCheckInfo',bdi,undefined,undefined,true);
            ret.ok=true;
            ret.code=rsp&&rsp.code;
            ret.msg=rsp&&rsp.msg;
            ret.resultType=rsp&&rsp.data&&rsp.data.resultType;
            ret.flowData=rsp&&rsp.data&&rsp.data.busiData&&rsp.data.busiData.flowData||null;
            ret.busiId=ret.flowData&&ret.flowData.busiId||null;
          }catch(e){
            ret.ok=false;
            ret.err=String(e);
            try{
              ret.err_json=JSON.stringify(e);
            }catch(_){}
            try{
              ret.err_keys=Object.keys(e||{});
            }catch(_){}
            try{
              ret.err_data=e&&e.data?e.data:null;
            }catch(_){}
            try{
              ret.err_msg=e&&e.msg?e.msg:null;
            }catch(_){}
          }
          var p=fc.params||{};
          ret.localFlowData=p.flowData||null;
          ret.localPath=fc.busiCompUrlPaths||null;
          return ret;
        })()"""
    )
    rec["steps"].append({"step": "S1_call_operation_namecheck", "data": s1})

    s2 = ev(
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; var p=fc&&fc.params?fc.params:{};
          return {hash:location.hash,flowData:p.flowData||null,busiCompUrlPaths:fc?fc.busiCompUrlPaths:null};
        })()"""
    )
    rec["steps"].append({"step": "S2_after_state", "data": s2})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

