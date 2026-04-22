#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/dump_namecheck_index_fields.json")


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=12)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            ws = p["webSocketDebuggerUrl"]
            break
    if not ws:
        OUT.write_text(json.dumps({"error": "no_namecheck_page"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    expr = r"""(function(){
      function walk(vm,d){
        if(!vm||d>20) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && vm.$parent && vm.$parent.$options && vm.$parent.$options.name==='name-check-info'){
          return vm;
        }
        for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
        return null;
      }
      function flat(o){
        var r={};
        if(!o||typeof o!=='object') return r;
        Object.keys(o).forEach(function(k){
          try{
            var v=o[k];
            if(v===null || v===undefined || typeof v==='string' || typeof v==='number' || typeof v==='boolean'){
              r[k]=v;
            }
          }catch(e){}
        });
        return r;
      }
      var app=document.getElementById('app');
      var vm=app&&app.__vue__?walk(app.__vue__,0):null;
      if(!vm) return {ok:false,msg:'no_index_vm'};
      return {
        ok:true,
        flowDataKeys:Object.keys(vm.flowData||{}),
        formInfoKeys:Object.keys(vm.formInfo||{}),
        nameCheckDTOKeys:Object.keys(vm.nameCheckDTO||{}),
        flowData:flat(vm.flowData||{}),
        formInfo:flat(vm.formInfo||{}),
        nameCheckDTO:flat(vm.nameCheckDTO||{})
      };
    })()"""
    data = ev(ws, expr)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

