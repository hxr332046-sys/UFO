#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/manual_call_save_guidedata.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "icpsp-web-pc" in (p.get("url") or "") and ":9087" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws_url:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=90000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    rec["steps"].append({"step": "state0", "data": ev("({href:location.href,hash:location.hash})", 15000)})
    rec["steps"].append(
        {
            "step": "call_saveGuideData_raw_fetch",
            "data": ev(
                r"""(async function(){
                  var payload={
                    busiType:'02_4',
                    entType:'4540',
                    extra:'guideData',
                    guideData:{
                      entType:'4540',nameCode:'0',havaAdress:'0',distCode:'450102',streetCode:'450102',streetName:'兴宁区',detAddress:'容州大道88号',address:'兴宁区',distList:['450000','450100','450102','450102']
                    },
                    extraDto: JSON.stringify({extraDto:{entType:'4540',nameCode:'0',havaAdress:'0',distCode:'450102',streetCode:'450102',streetName:'兴宁区',detAddress:'容州大道88号',address:'兴宁区',distList:['450000','450100','450102','450102']}})
                  };
                  var tk=localStorage.getItem('top-token')||'';
                  var auth=localStorage.getItem('Authorization')||'';
                  try{
                    var r=await fetch('/icpsp-api/v4/pc/register/guide/saveGuideData',{method:'POST',headers:{'Content-Type':'application/json','top-token':tk,'Authorization':auth},body:JSON.stringify(payload)});
                    var t=await r.text();
                    return {ok:r.ok,status:r.status,text:t.slice(0,1000),payload:payload};
                  }catch(e){
                    return {ok:false,err:String(e),payload:payload};
                  }
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "call_saveGuideData_vmapi_if_exists",
            "data": ev(
                r"""(async function(){
                  function walk(vm,d){if(!vm||d>18)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&vm.$api&&vm.$api.guide)return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1);if(r)return r;}return null;}
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  var payload={busiType:'02_4',entType:'4540',extra:'guideData',guideData:{entType:'4540',nameCode:'0',havaAdress:'0',distCode:'450102',streetCode:'450102',streetName:'兴宁区',detAddress:'容州大道88号',address:'兴宁区',distList:['450000','450100','450102','450102']},extraDto:JSON.stringify({extraDto:{entType:'4540',nameCode:'0',havaAdress:'0',distCode:'450102',streetCode:'450102',streetName:'兴宁区',detAddress:'容州大道88号',address:'兴宁区',distList:['450000','450100','450102','450102']}})};
                  var api=vm.$api&&vm.$api.guide;
                  if(!api) return {ok:false,err:'no_api'};
                  var f=api.saveGuideData || api.saveGuide || null;
                  if(!f) return {ok:false,err:'no_save_guide_method',apiKeys:Object.keys(api||{}).slice(0,40)};
                  try{
                    var rsp=await f.call(api,payload);
                    return {ok:true,rsp:rsp||null};
                  }catch(e){
                    var out={ok:false,err:String(e)};
                    try{out.err_json=JSON.stringify(e);}catch(_){}
                    return out;
                  }
                })()"""
            ),
        }
    )

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

