#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/global_listener_install_latest.json")

INSTALL_JS = r"""(function(){
  var KEY='__UFO_GLOBAL_TRACE__';
  function read(){ try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){return[]} }
  function write(v){ try{localStorage.setItem(KEY, JSON.stringify(v).slice(0,8000000))}catch(e){} }
  function push(x){ var arr=read(); arr.push(x); if(arr.length>5000) arr=arr.slice(arr.length-5000); write(arr); }
  push({t:Date.now(),type:'mark',stage:'install',href:location.href,hash:location.hash});
  if(window.__ufo_global_listener_installed){ return {ok:true,already:true,count:read().length}; }
  window.__ufo_global_listener_installed=true;
  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return oo.apply(this,arguments); };
  XMLHttpRequest.prototype.send=function(b){
    var u=(this.__ufo&&this.__ufo.u)||'';
    if(String(u).indexOf('/icpsp-api/')>=0){
      push({t:Date.now(),type:'req',m:(this.__ufo&&this.__ufo.m)||'',u:String(u).slice(0,300),body:String(b||'').slice(0,1000),href:location.href,hash:location.hash});
      var self=this;
      self.addEventListener('loadend',function(){
        push({t:Date.now(),type:'resp',u:String(u).slice(0,300),status:self.status,resp:String(self.responseText||'').slice(0,1200),href:location.href,hash:location.hash});
      });
    }
    return os.apply(this,arguments);
  };
  // route变化记录
  window.addEventListener('hashchange', function(){
    push({t:Date.now(),type:'hashchange',href:location.href,hash:location.hash});
  }, true);
  return {ok:true,already:false,count:read().length};
})()"""


def eval_js(ws_url: str, expr: str, timeout_ms: int = 30000):
    ws = websocket.create_connection(ws_url, timeout=12)
    ws.settimeout(2.0)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            }
        )
    )
    end = time.time() + 30
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


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "tabs": []}
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target_pages = [p for p in pages if p.get("type") == "page" and ":9087" in (p.get("url") or "")]
    for p in target_pages:
        ws = p.get("webSocketDebuggerUrl")
        url = p.get("url")
        if not ws:
            continue
        res = eval_js(ws, INSTALL_JS, 30000)
        rec["tabs"].append({"url": url, "install_result": res})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

