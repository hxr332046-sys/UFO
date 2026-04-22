#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in p.get("url", ""):
            target = p
            break
    if not target:
        print(json.dumps({"error": "no_basic_info_page"}, ensure_ascii=False))
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)
    expr = r"""(function(){
  var app=document.getElementById('app');
  if(!app || !app.__vue__) return {error:'no_app', href:location.href};
  var root=app.__vue__;
  function find(vm,d){
    if(!vm || d>20) return null;
    var n=(vm.$options && vm.$options.name) || '';
    if(n==='flow-control') return vm;
    var ch=vm.$children || [];
    for(var i=0;i<ch.length;i++){
      var r=find(ch[i],d+1);
      if(r) return r;
    }
    return null;
  }
  var fc=find(root,0);
  if(!fc) return {error:'no_flow_control', href:location.href, hash:location.hash};
  var params=fc.params || {};
  return {
    href: location.href,
    hash: location.hash,
    curCompUrl: fc.curCompUrl || '',
    curCompUrlPath: fc.curCompUrlPath || [],
    busiCompUrlPaths: fc.busiCompUrlPaths || [],
    flowData: params.flowData || null,
    signInfoKeys: Object.keys(fc.signInfoList || {}),
    compUrlPathLen: (fc.curCompUrlPath || []).length,
    busiPathLen: (fc.busiCompUrlPaths || []).length
  };
})()"""
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "timeout": 15000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            print(json.dumps(msg.get("result", {}).get("result", {}).get("value"), ensure_ascii=False, indent=2))
            break
    ws.close()


if __name__ == "__main__":
    main()

