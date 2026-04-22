#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/" in p.get("url", ""):
            target = p
            break
    if not target:
        print(json.dumps({"error": "no_core_page"}, ensure_ascii=False))
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)
    expr = r"""(function(){
      function find(vm,d){
        if(!vm||d>20) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='flow-control') return vm;
        var ch=vm.$children||[];
        for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1); if(r)return r;}
        return null;
      }
      var app=document.getElementById('app');
      if(!app||!app.__vue__) return {error:'no_app'};
      var fc=find(app.__vue__,0);
      if(!fc) return {error:'no_fc'};
      var ms=Object.keys((fc.$options&&fc.$options.methods)||{});
      var picks=ms.filter(function(n){
        var x=n.toLowerCase();
        return x.indexOf('flow')>=0||x.indexOf('busi')>=0||x.indexOf('init')>=0||x.indexOf('extra')>=0||x.indexOf('load')>=0||x.indexOf('item')>=0||x.indexOf('save')>=0;
      });
      var dataKeys=Object.keys(fc.$data||{}).filter(function(k){
        var x=k.toLowerCase();
        return x.indexOf('flow')>=0||x.indexOf('busi')>=0||x.indexOf('item')>=0||x.indexOf('id')>=0||x.indexOf('extra')>=0||x.indexOf('sign')>=0||x.indexOf('path')>=0;
      });
      return {
        href:location.href,
        hash:location.hash,
        methodCount:ms.length,
        methods:picks,
        dataKeys:dataKeys,
        flowData:(fc.params&&fc.params.flowData)||null,
        busiCompUrlPaths:fc.busiCompUrlPaths||[]
      };
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "timeout": 15000}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            print(json.dumps(m.get("result", {}).get("result", {}).get("value"), ensure_ascii=False, indent=2))
            break
    ws.close()


if __name__ == "__main__":
    main()

