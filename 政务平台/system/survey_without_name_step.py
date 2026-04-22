#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在 without-name 页面执行 toNotName，并记录跳转后的框架。"""

import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/without_name_step_survey.json")


def ws_for_without_name():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "#/index/without-name" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    # fallback zhjg
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url: str, expr: str, timeout: int = 12):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "timeout": timeout * 1000},
            }
        )
    )
    ws.settimeout(timeout + 2)
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def snap(ws_url: str):
    expr = r"""(function(){
  var app=document.getElementById('app');
  var names=[];
  function walk(vm,d){ if(!vm||d>8) return; var n=(vm.$options&&vm.$options.name)||''; if(n) names.push(n); (vm.$children||[]).forEach(function(c){walk(c,d+1);}); }
  if(app&&app.__vue__) walk(app.__vue__,0);
  return {
    href:location.href,
    hash:location.hash,
    forms:document.querySelectorAll('.el-form-item').length,
    compNames:Array.from(new Set(names)).slice(0,30),
    buttons:Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;}).map(function(b){return (b.textContent||'').trim();}).slice(0,20)
  };
})()"""
    return ev(ws_url, expr, timeout=12)


def call_to_not_name(ws_url: str):
    expr = r"""(function(){
  var app=document.getElementById('app'); if(!app||!app.__vue__) return {ok:false,err:'no_vue'};
  function findComp(vm,name,d){ if(!vm||d>15) return null; if(vm.$options&&vm.$options.name===name) return vm; for(var i=0;i<(vm.$children||[]).length;i++){ var r=findComp(vm.$children[i],name,d+1); if(r) return r; } return null; }
  var wn=findComp(app.__vue__,'without-name',0);
  if(!wn) return {ok:false,err:'no_without_name'};
  if(typeof wn.toNotName!=='function') return {ok:false,err:'no_toNotName'};
  wn.toNotName();
  return {ok:true,called:'toNotName'};
})()"""
    return ev(ws_url, expr, timeout=12)


def main():
    ws, url = ws_for_without_name()
    if not ws:
        print("No target page.")
        return
    out = {"initial_url": url, "steps": []}
    s1 = snap(ws)
    out["steps"].append({"step": "before_toNotName", "data": s1})
    print("before:", s1.get("hash"), s1.get("compNames")[:8])

    r = call_to_not_name(ws)
    out["steps"].append({"step": "call_toNotName", "data": r})
    print("call:", r)
    time.sleep(4)

    s2 = snap(ws)
    out["steps"].append({"step": "after_toNotName", "data": s2})
    print("after:", s2.get("hash"), s2.get("compNames")[:10])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

