#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    if not ws_url:
        print(json.dumps({"error": "no_guide_page"}, ensure_ascii=False))
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    expr = r"""(function(){
      function walk(vm,d){
        if(!vm||d>18) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && typeof vm.flowSave==='function') return vm;
        var ch=vm.$children||[];
        for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
        return null;
      }
      var app=document.getElementById('app');
      var root=app&&app.__vue__;
      var vm=walk(root,0);
      if(!vm){
        return {error:'no_index_vm',href:location.href,hash:location.hash};
      }
      var m=(vm.$options&&vm.$options.methods)||{};
      var src = m.flowSave ? m.flowSave.toString() : '';
      var nextSrc = m.nextStep ? m.nextStep.toString() : '';
      var validateSrc = m.$validate ? m.$validate.toString() : '';
      return {
        href: location.href,
        hash: location.hash,
        vmName: (vm.$options&&vm.$options.name)||'',
        dataKeys: Object.keys(vm.$data||{}),
        form: vm.form || null,
        distList: vm.distList || null,
        flowSaveSrc: src.slice(0,12000),
        nextStepSrc: nextSrc.slice(0,4000),
        validateSrc: validateSrc.slice(0,4000)
      };
    })()"""
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000},
            }
        )
    )
    out = None
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            out = m.get("result", {}).get("result", {}).get("value")
            break
    ws.close()
    print(json.dumps(out, ensure_ascii=False, indent=2)[:20000])


if __name__ == "__main__":
    main()

