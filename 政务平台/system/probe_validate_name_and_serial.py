#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_validate_name_and_serial.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws_url:
        rec["error"] = "no_guide_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=80000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    rec["steps"].append(
        {
            "step": "call_validateNameAndSerialNum",
            "data": ev(
                r"""(async function(){
                  function walk(vm,d){if(!vm||d>18)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&vm.$api&&vm.$api.guide)return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1);if(r)return r;}return null;}
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  var g=vm.$api.guide;
                  if(!g || typeof g.validateNameAndSerialNum!=='function') return {ok:false,err:'no_validate_api'};
                  var variants=[
                    {name:'广西智信数据科技有限公司',number:'GX2024001'},
                    {entName:'广西智信数据科技有限公司',number:'GX2024001'},
                    {entName:'广西智信数据科技有限公司',serialNum:'GX2024001'},
                    {entName:'广西智信数据科技有限公司',reserveNo:'GX2024001'},
                    {entName:'广西智信数据科技有限公司',nameCode:'1',number:'GX2024001'},
                    {entName:'广西智信数据科技有限公司（个人独资）',serialNum:'GX2024001',entType:'4540'}
                  ];
                  var out=[];
                  for(var i=0;i<variants.length;i++){
                    var p=variants[i];
                    try{
                      var r=await g.validateNameAndSerialNum(p);
                      out.push({ok:true,arg:p,r:r||null});
                    }catch(e){
                      var item={ok:false,arg:p,err:String(e)};
                      try{item.err_json=JSON.stringify(e);}catch(_){}
                      out.push(item);
                    }
                  }
                  return {ok:true,cases:out};
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

