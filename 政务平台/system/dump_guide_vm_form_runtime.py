#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time

import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    if not ws_url:
        print(json.dumps({"error": "no_guide_page"}, ensure_ascii=False))
        return

    ws = websocket.create_connection(ws_url, timeout=20)
    expr = r"""(function(){
      function walk(vm,d){
        if(!vm||d>12) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && typeof vm.flowSave==='function') return vm;
        for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
        return null;
      }
      var app=document.getElementById('app');
      var vm=app&&app.__vue__?walk(app.__vue__,0):null;
      if(!vm) return {error:'no_vm'};
      return {
        form: vm.form||null,
        deepForm: vm.deepForm||null,
        companyInfo: vm.companyInfo||null,
        distListLen: (vm.distList||[]).length,
        localdataTreeLen: (vm.localdataTree||[]).length,
        localdataTreeSample: (function(){
          function pick(node,d){
            if(!node||d>3) return null;
            var out={
              id:(node.id||node.value||node.code||'')+'',
              name:(node.name||node.label||'')+'',
              children:[]
            };
            var cs=node.children||[];
            for(var i=0;i<Math.min(cs.length,5);i++) out.children.push(pick(cs[i],d+1));
            return out;
          }
          var roots=vm.localdataTree||[];
          var arr=[];
          for(var i=0;i<Math.min(roots.length,3);i++) arr.push(pick(roots[i],0));
          return arr;
        })(),
        rulesKeys: Object.keys(vm.rules||{}),
        formKeys: Object.keys(vm.form||{})
      };
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    out = None
    end = time.time() + 10
    while time.time() < end:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            out = msg.get("result", {}).get("result", {}).get("value")
            break
    ws.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

