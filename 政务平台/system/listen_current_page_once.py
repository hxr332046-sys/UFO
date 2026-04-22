#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/listen_current_page_once.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=8).json()
    pages = [p for p in pages if p.get("type") == "page"]
    for p in pages:
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:9087" in u and "name-register.html#/guide/base" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:9087" in u:
            return p.get("webSocketDebuggerUrl"), u
    return (pages[0].get("webSocketDebuggerUrl"), pages[0].get("url") or "") if pages else (None, "")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method, params=None, timeout=25):
        if params is None:
            params = {}
        cid = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == cid:
                return msg
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr, timeout_ms=120000):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            timeout=28,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main():
    ws_url, url = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "page": url, "steps": []}
    if not ws_url:
        rec["error"] = "no_cdp_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws_url)
    try:
        rec["steps"].append(
            {
                "step": "install_hook",
                "data": c.ev(
                    r"""(function(){
                      window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
                      function pushOne(x){ try{ x.ts=Date.now(); window.__ufo_cap.items.push(x); if(window.__ufo_cap.items.length>500) window.__ufo_cap.items.shift(); }catch(e){} }
                      if(!window.__ufo_cap.installed){
                        var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return XO.apply(this,arguments); };
                        XMLHttpRequest.prototype.send=function(body){
                          var self=this, u=(self.__ufo&&self.__ufo.u)||'', s=String(u);
                          if(s.indexOf('/icpsp-api/')>=0 || s.indexOf('9087')>=0){
                            pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:s.slice(0,900),body:String(body||'').slice(0,40000)});
                            self.addEventListener('loadend',function(){pushOne({t:'xhr_end',u:s.slice(0,900),status:self.status,resp:String(self.responseText||'').slice(0,40000)});});
                          }
                          return XS.apply(this,arguments);
                        };
                        window.__ufo_cap.installed=true;
                      }
                      window.__ufo_cap.items=[];
                      window.__ufo_cap_href_before=location.href;
                      return {ok:true,href:location.href};
                    })()"""
                ),
            }
        )
        start = time.time()
        obs = None
        while time.time() - start < 120:
            obs = c.ev(
                r"""(function(){
                  var cap=(window.__ufo_cap&&window.__ufo_cap.items)||[];
                  var before=window.__ufo_cap_href_before||'';
                  var href=location.href;
                  return {
                    href:href,
                    changed:href!==before,
                    capCount:cap.length,
                    last:cap.slice(-10)
                  };
                })()"""
            )
            if isinstance(obs, dict) and (obs.get("changed") or obs.get("capCount", 0) > 0):
                break
            time.sleep(1.0)
        rec["steps"].append({"step": "observed", "data": obs})
    finally:
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        c.close()


if __name__ == "__main__":
    main()

