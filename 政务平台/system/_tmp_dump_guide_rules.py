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
      var vm=walk(app&&app.__vue__,0);
      if(!vm) return {error:'no_vm'};
      var out={};
      var rk=['entType','name','number','havaAdress','distCode','streetCode'];
      for(var i=0;i<rk.length;i++){
        var k=rk[i], arr=(vm.rules&&vm.rules[k])||[];
        out[k]=arr.map(function(r){
          return {
            required: !!r.required,
            message: r.message||'',
            trigger: r.trigger||'',
            hasValidator: typeof r.validator==='function',
            validatorSrc: typeof r.validator==='function' ? r.validator.toString().slice(0,800) : ''
          };
        });
      }
      var fields=((vm.$refs&&vm.$refs.form&&vm.$refs.form.fields)||[]).map(function(f){
        return {prop:f.prop, validateState:f.validateState, validateMessage:f.validateMessage, fieldValue:f.fieldValue};
      });
      return {form:vm.form||null, rules:out, fields:fields};
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            print(json.dumps(m.get("result", {}).get("result", {}).get("value"), ensure_ascii=False, indent=2)[:20000])
            break
    ws.close()


if __name__ == "__main__":
    main()

