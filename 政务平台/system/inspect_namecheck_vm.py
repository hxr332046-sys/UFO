#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/inspect_namecheck_vm.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p.get("webSocketDebuggerUrl")
    return None


def main():
    ws = pick_ws()
    rec = {}
    if not ws:
        rec["error"] = "no_name_check_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = websocket.create_connection(ws, timeout=20)
    payload = {
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": r"""(function(){
              try{
                function walk(vm,d){
                  if(!vm||d>25) return null;
                  var n=(vm.$options&&vm.$options.name)||'';
                  if(/name-check|NameCheck|namecheck/i.test(n)) return vm;
                  for(var ch of (vm.$children||[])){var r=walk(ch,d+1); if(r) return r;}
                  return null;
                }
                var app=document.getElementById('app');
                var root=app&&app.__vue__?app.__vue__:null;
                if(!root) return {ok:false,msg:'no_root'};
                var vm=walk(root,0);
                if(!vm){
                  // fallback: flow-control subtree first child
                  function findFlow(v,d){
                    if(!v||d>20)return null;
                    var n=(v.$options&&v.$options.name)||'';
                    if(n==='flow-control') return v;
                    for(var ch of (v.$children||[])){var r=findFlow(ch,d+1);if(r)return r;}
                    return null;
                  }
                  var fc=findFlow(root,0);
                  if(fc && fc.$children && fc.$children.length) vm=fc.$children[0];
                }
                if(!vm) return {ok:false,msg:'no_vm_found'};
                var methods=Object.keys((vm.$options&&vm.$options.methods)||{});
                var dataKeys=Object.keys(vm.$data||{});
                var refs=Object.keys(vm.$refs||{});
                var compNames=[];
                var q=[vm],seen=new Set();
                while(q.length&&compNames.length<80){
                  var x=q.shift();
                  if(!x||seen.has(x)) continue;
                  seen.add(x);
                  var nm=(x.$options&&x.$options.name)||'';
                  if(nm) compNames.push(nm);
                  for(var ch of (x.$children||[])) q.push(ch);
                }
                return {ok:true,name:(vm.$options&&vm.$options.name)||'',methods:methods,dataKeys:dataKeys,refs:refs,compNames:compNames};
              }catch(e){
                return {ok:false,msg:String(e),stack:(e&&e.stack)?String(e.stack):''};
              }
            })()""",
            "returnByValue": True,
            "awaitPromise": True,
            "timeout": 60000,
        },
    }
    c.send(json.dumps(payload))
    while True:
        msg = json.loads(c.recv())
        if msg.get("id") == 1:
            rec = ((msg.get("result") or {}).get("result") or {}).get("value")
            break
    c.close()
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

