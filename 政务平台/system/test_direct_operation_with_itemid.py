#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/test_direct_operation_with_itemid.json")


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

    def ev(expr, timeout=80000):
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")

    s1 = ev(
        r"""(async function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
          var id='22561619020183';
          try{
            var r=await fc.initBusinessInfoList('OpManyAddress');
            var x=r&&r.linkData&&r.linkData.busiCompComb&&r.linkData.busiCompComb.id;
            if(x) id=x;
          }catch(e){}
          if(!Array.isArray(fc.busiCompUrlPaths) || !fc.busiCompUrlPaths.length){
            fc.$set(fc,'busiCompUrlPaths',[{compUrl:'BasicInfo',id:id}]);
          }else{
            if(!fc.busiCompUrlPaths[0]) fc.busiCompUrlPaths[0]={compUrl:'BasicInfo',id:id};
            fc.busiCompUrlPaths[0].compUrl='BasicInfo';
            fc.busiCompUrlPaths[0].id=id;
            try{fc.$set(fc.busiCompUrlPaths[0],'id',id);}catch(e){}
          }
          fc.$set(fc,'curCompUrlPath',['BasicInfo']);
          if(fc.params&&fc.params.flowData){
            fc.params.flowData.currCompUrl='BasicInfo';
          }
          var bdi=JSON.parse(JSON.stringify((fc.$data&&fc.$data.businessDataInfo)||{}));
          var out={id:id,busiCompUrlPaths:fc.busiCompUrlPaths,flowData:fc.params&&fc.params.flowData||null};
          try{
            var rsp=await fc.operationBusinessDataInfo('tempSave','BasicInfo',bdi,undefined,undefined,false);
            out.callOk=true;
            out.code=rsp&&rsp.code||null;
            out.msg=rsp&&rsp.msg||null;
            out.resultType=rsp&&rsp.data&&rsp.data.resultType||null;
            out.resFlowData=rsp&&rsp.data&&rsp.data.busiData&&rsp.data.busiData.flowData||null;
          }catch(e){
            out.callOk=false;
            out.err=String(e);
            try{out.errJson=JSON.stringify(e);}catch(_){}
          }
          return out;
        })()"""
    )
    rec["steps"].append({"step": "S1_direct_call", "data": s1})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

