#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type") == "page"][0]
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=25000, awaitp=True):
        nonlocal mid
        mid += 1
        ws.send(
            json.dumps(
                {
                    "id": mid,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": awaitp,
                        "timeout": timeout,
                    },
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    print("href:", ev("location.href", 5000))
    expr = r"""(function(){
      var app=document.getElementById('app');
      var vm=app && app.__vue__;
      function find(vm,name,d){
        if(!vm||d>25) return null;
        if((vm.$options&&vm.$options.name)===name) return vm;
        var ch=vm.$children||[];
        for(var i=0;i<ch.length;i++){var r=find(ch[i],name,d+1); if(r) return r;}
        return null;
      }
      var sp=find(vm,'select-prise',0);
      if(!sp) return {error:'no_select_prise',hash:location.hash};
      return {
        hash:location.hash,
        methods:Object.keys((sp.$options&&sp.$options.methods)||{}),
        dataKeys:Object.keys(sp.$data||{}),
        fromType:sp.$data&&sp.$data.fromType,
        priseListLen:((sp.$data&&sp.$data.priseList)||[]).length,
        dataInfo:sp.$data&&sp.$data.dataInfo ? JSON.stringify(sp.$data.dataInfo).slice(0,400) : null,
        nameId: (sp.$data&&sp.$data.nameId) || (sp.$data&&sp.$data.dataInfo&&sp.$data.dataInfo.nameId) || ''
      };
    })()"""
    info = ev(expr, 15000)
    print(json.dumps(info, ensure_ascii=False, indent=2)[:4000])
    ws.close()


if __name__ == "__main__":
    main()

