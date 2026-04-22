#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_core_basicinfo_vm_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 70000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.settimeout(2.0)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms}}))
    end = time.time() + 45
    try:
        while time.time() < end:
            try:
                m = json.loads(ws.recv())
            except Exception:
                continue
            if m.get("id") == 1:
                return ((m.get("result") or {}).get("result") or {}).get("value")
    finally:
        ws.close()
    return None


JS = r"""(function(){
  function walk(vm,d,pred){
    if(!vm||d>25) return null;
    if(pred(vm)) return vm;
    for(var ch of (vm.$children||[])){ var r=walk(ch,d+1,pred); if(r) return r; }
    return null;
  }
  var app=document.getElementById('app');
  var root=app&&app.__vue__;
  if(!root) return {ok:false,msg:'no_root'};
  var idx=walk(root,0,function(v){return (v.$options&&v.$options.name)==='index' && location.hash.indexOf('basic-info')>=0;});
  if(!idx){
    idx=walk(root,0,function(v){return (v.$options&&v.$options.name)==='index';});
  }
  if(!idx) return {ok:false,msg:'no_index'};
  var refs={};
  try{
    var r=idx.$refs||{};
    Object.keys(r).slice(0,30).forEach(function(k){
      var it=r[k];
      refs[k]={isArray:Array.isArray(it),name:it&&it.$options?it.$options.name:null,hasGetFormData:!!(it&&typeof it.getFormData==='function')};
    });
  }catch(e){}
  return {
    ok:true,
    href:location.href,
    hash:location.hash,
    vmName:(idx.$options&&idx.$options.name)||'',
    dataKeys:Object.keys(idx.$data||{}).slice(0,120),
    formInfo:idx.formInfo||null,
    form:idx.form||null,
    refs:refs
  };
})()"""


def main() -> int:
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_basicinfo_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "probe", "data": ev(ws, JS, 70000)})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

