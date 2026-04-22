#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/inspect_organization_select_runtime.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    if not ws:
        OUT.write_text(json.dumps({"error": "no_namecheck_page"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    data = ev(
        ws,
        r"""(function(){
          function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
          function flat(o){
            var r={}; if(!o||typeof o!=='object') return r;
            Object.keys(o).forEach(function(k){
              try{
                var v=o[k];
                if(v===null||v===undefined||typeof v==='string'||typeof v==='number'||typeof v==='boolean'){r[k]=v;}
                else if(Array.isArray(v)){r[k]='[array:'+v.length+']';}
                else if(typeof v==='object'){r[k]='[object]';}
              }catch(e){}
            });
            return r;
          }
          var app=document.getElementById('app'); var root=app&&app.__vue__;
          if(!root) return {ok:false,msg:'no_root'};
          var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
          var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
          if(!org) return {ok:false,msg:'no_org_vm'};
          var gl=org.groupList||[];
          var sample=gl.slice(0,8).map(function(it){
            if(!it||typeof it!=='object') return {raw:String(it)};
            return {
              value:it.value, code:it.code, id:it.id, dictCode:it.dictCode, organizeCode:it.organizeCode,
              label:it.label, name:it.name, text:it.text
            };
          });
          return {
            ok:true,
            orgData:flat(org.$data||{}),
            orgMethodKeys:Object.keys((org.$options&&org.$options.methods)||{}),
            orgPropKeys:Object.keys((org.$options&&org.$options.props)||{}),
            zhongjainzhiType:typeof org.zhongjainzhi,
            zhongjainzhi:flat(org.zhongjainzhi),
            formInline:flat(org.formInline),
            groupListLen:gl.length,
            groupListSample:sample,
            indexFormInfo: idx ? flat(idx.formInfo||{}) : {}
          };
        })()""",
    )
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

