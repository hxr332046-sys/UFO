#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/scan_vm_children_for_getformdata.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws_url = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not ws_url:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    expr = r"""(function(){
      function walk(vm,d){
        if(!vm||d>12) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && typeof vm.flowSave==='function') return vm;
        for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}
        return null;
      }
      var app=document.getElementById('app');
      var vm=app&&app.__vue__?walk(app.__vue__,0):null;
      if(!vm) return {ok:false,msg:'no_vm'};

      var childInfo=(vm.$children||[]).map(function(c,idx){
        return {
          idx:idx,
          name:(c&&c.$options&&c.$options.name)||null,
          hasGetFormData:!!(c&&typeof c.getFormData==='function'),
          refName:(c&&c.$vnode&&c.$vnode.data&&c.$vnode.data.ref)||null
        };
      });

      var arrays=[];
      Object.keys(vm.$data||{}).forEach(function(k){
        var v=vm.$data[k];
        if(Array.isArray(v)){
          arrays.push({
            key:k,
            len:v.length,
            undefinedIndexes:v.map(function(x,i){return x===undefined?i:null}).filter(function(x){return x!==null}).slice(0,20),
            sampleTypes:v.slice(0,10).map(function(x){
              if(x===undefined) return 'undefined';
              if(x===null) return 'null';
              if(Array.isArray(x)) return 'array';
              return typeof x;
            })
          });
        }
      });

      var refInfo={};
      Object.keys(vm.$refs||{}).forEach(function(k){
        var r=vm.$refs[k];
        if(Array.isArray(r)){
          refInfo[k]={
            len:r.length,
            undefinedIndexes:r.map(function(x,i){return x===undefined?i:null}).filter(function(x){return x!==null}),
            hasGetFormData:r.map(function(x){return !!(x&&typeof x.getFormData==='function');})
          };
        }else{
          refInfo[k]={isNull:r==null,hasGetFormData:!!(r&&typeof r.getFormData==='function'),name:r&&r.$options?r.$options.name:null};
        }
      });

      return {
        ok:true,
        childInfo:childInfo,
        dataArrays:arrays,
        refs:refInfo,
        methods:Object.keys((vm.$options&&vm.$options.methods)||{})
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
    rec["data"] = out
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

