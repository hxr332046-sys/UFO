#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/inspect_next_binding_owner.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    w = websocket.create_connection(ws, timeout=20)
    expr = r"""(function(){
      try{
      var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
      if(!btn) return {ok:false,msg:'no_btn'};
      var v=btn.__vue__;
      if(!v) return {ok:false,msg:'no_btn_vm'};
      function methodKeys(vm){return Object.keys((vm&&vm.$options&&vm.$options.methods)||{});}
      function dataKeys(vm){return Object.keys((vm&&vm.$data)||{});}
      var p=v.$parent;
      var gp=p&&p.$parent;
      return {
        ok:true,
        btnClass:(btn.className||'')+'',
        btnVmName:(v.$options&&v.$options.name)||'',
        btnVmLoading:v.loading,
        btnVmDisabled:v.buttonDisabled,
        btnVmListeners:Object.keys(v.$listeners||{}),
        btnVmVnodeOn:Object.keys((((v.$vnode||{}).data||{}).on||{})),
        parent:{
          name:(p&&p.$options&&p.$options.name)||null,
          methods:p?methodKeys(p):[],
          dataKeys:p?dataKeys(p):[],
          listeners:p?Object.keys(p.$listeners||{}):[],
          vnodeOn:p?Object.keys((((p.$vnode||{}).data||{}).on||{})):[]
        },
        grandParent:{
          name:(gp&&gp.$options&&gp.$options.name)||null,
          methods:gp?methodKeys(gp):[],
          dataKeys:gp?dataKeys(gp):[],
          listeners:gp?Object.keys(gp.$listeners||{}):[],
          vnodeOn:gp?Object.keys((((gp.$vnode||{}).data||{}).on||{})):[]
        }
      };
      }catch(e){
        return {ok:false,error:String(e),stack:(e&&e.stack?String(e.stack).slice(0,500):'')};
      }
    })()"""
    w.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    out = None
    end = time.time() + 10
    while time.time() < end:
        msg = json.loads(w.recv())
        if msg.get("id") == 1:
            if "result" in msg and "exceptionDetails" in msg["result"]:
                out = {"ok": False, "exceptionDetails": msg["result"]["exceptionDetails"]}
            else:
                out = msg.get("result", {}).get("result", {}).get("value")
            break
    w.close()
    rec["data"] = out
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

