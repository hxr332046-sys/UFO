#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/probe_getlocation_variants.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in p.get("url", ""):
            target = p
            break
    rec = {"results": []}
    if not target:
        rec["error"] = "no_basic_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)
    expr = r"""(async function(){
      function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
      var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; if(!fc)return{err:'no_fc'};
      var base=JSON.parse(JSON.stringify(fc.params||{}));
      if(!base.flowData) base.flowData={};
      base.flowData.entType='1100';
      base.flowData.busiType='02';
      var variants=[
        {k:'base',patch:{}},
        {k:'fromType_0',patch:{fromType:'0'}},
        {k:'fromType_1',patch:{fromType:'1'}},
        {k:'fromType_2',patch:{fromType:'2'}},
        {k:'ywlb_2',patch:{ywlbSign:'2'}},
        {k:'ywlb_6',patch:{ywlbSign:'6'}},
        {k:'nameId_fake',patch:{nameId:'test-name-id'}},
        {k:'marPrId_fake',patch:{marPrId:'test-mar-id'}},
        {k:'name_mar',patch:{nameId:'test-name-id',marPrId:'test-mar-id'}},
        {k:'all_flags',patch:{fromType:'1',ywlbSign:'2',nameId:'test-name-id',marPrId:'test-mar-id',secondId:'test-second'}}
      ];
      var out=[];
      for(var i=0;i<variants.length;i++){
        var v=variants[i];
        var p=JSON.parse(JSON.stringify(base));
        Object.keys(v.patch).forEach(function(k){p.flowData[k]=v.patch[k];});
        try{
          var rsp=await fc.$api.flow.getLocationInfo(p);
          var d=rsp&&rsp.data&&rsp.data.busiData||{};
          var f=d.flowData||{};
          out.push({
            variant:v.k,
            code:rsp&&rsp.code||null,
            resultType:rsp&&rsp.data&&rsp.data.resultType||null,
            msg:rsp&&rsp.msg||null,
            busiId:f.busiId||null,
            currCompUrl:f.currCompUrl||null
          });
        }catch(e){
          var item={variant:v.k,error:String(e)};
          try{ item.err_json=JSON.stringify(e); }catch(_){}
          try{ item.err_keys=Object.keys(e||{}); }catch(_){}
          out.push(item);
        }
      }
      return out;
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 120000}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            rec["results"] = m.get("result", {}).get("result", {}).get("value")
            break
    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

