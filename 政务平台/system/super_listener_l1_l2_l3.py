#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L1+L2+L3 最小强监听器（单文件版）

L1: CDP Network 级别抓包（请求/响应/响应体）
L2: 页面内 XHR/fetch hook + 路由/简要状态快照
L3: 统一时间线编排（event timeline）

用法:
  python super_listener_l1_l2_l3.py --seconds 180
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/super_listener_l1_l2_l3.json")


def pick_ws() -> Tuple[Optional[str], str]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=8).json()
    pages = [p for p in pages if p.get("type") == "page"]
    for p in pages:
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:9087" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:6087" in u:
            return p.get("webSocketDebuggerUrl"), u
    return (pages[0].get("webSocketDebuggerUrl"), pages[0].get("url") or "") if pages else (None, "")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
        self.seq = 1

    def _send_cmd(self, method: str, params: Optional[dict] = None) -> int:
        if params is None:
            params = {}
        cid = self.seq
        self.seq += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        return cid

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 10.0) -> Any:
        cid = self._send_cmd(method, params)
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = json.loads(self.ws.recv())
            except Exception:
                continue
            if m.get("id") == cid:
                if "error" in m:
                    return {"error": m["error"]}
                return m.get("result", {})
        return {"error": {"message": f"timeout {method}"}}

    def eval(self, expression: str, timeout_ms: int = 60000) -> Any:
        ret = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            timeout=12.0,
        )
        return ((ret or {}).get("result") or {}).get("value")

    def recv_one(self) -> Optional[dict]:
        try:
            return json.loads(self.ws.recv())
        except Exception:
            return None

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


HOOK_JS = r"""(function(){
  window.__ufo_cap2 = window.__ufo_cap2 || {installed:false,items:[]};
  function pushOne(x){
    try{
      x.ts = Date.now();
      window.__ufo_cap2.items.push(x);
      if(window.__ufo_cap2.items.length > 1200) window.__ufo_cap2.items.shift();
    }catch(e){}
  }
  if(!window.__ufo_cap2.installed){
    var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){ this.__ufo2={m:m,u:u}; return XO.apply(this,arguments); };
    XMLHttpRequest.prototype.send=function(body){
      var self=this, u=(self.__ufo2&&self.__ufo2.u)||'', m=(self.__ufo2&&self.__ufo2.m)||'';
      pushOne({layer:'L2',kind:'xhr_req',method:m,url:String(u).slice(0,1200),body:String(body||'').slice(0,40000)});
      self.addEventListener('loadend',function(){
        pushOne({layer:'L2',kind:'xhr_res',url:String(u).slice(0,1200),status:self.status,resp:String(self.responseText||'').slice(0,40000)});
      });
      return XS.apply(this,arguments);
    };
    var OF=window.fetch;
    if(typeof OF==='function'){
      window.fetch=function(input,init){
        var u=(typeof input==='string')?input:(input&&input.url)||'';
        var m=(init&&init.method)||'GET';
        var b=(init&&init.body)?String(init.body).slice(0,40000):'';
        pushOne({layer:'L2',kind:'fetch_req',method:m,url:String(u).slice(0,1200),body:b});
        return OF.apply(this,arguments).then(function(res){
          try{
            return res.clone().text().then(function(txt){
              pushOne({layer:'L2',kind:'fetch_res',url:String(u).slice(0,1200),status:res.status,resp:String(txt||'').slice(0,40000)});
              return res;
            });
          }catch(e){
            return res;
          }
        });
      };
    }
    window.__ufo_cap2.installed = true;
  }
  return {ok:true,href:location.href};
})()"""


SNAP_JS = r"""(function(){
  var t=(document.body&&document.body.innerText)||'';
  var cap=(window.__ufo_cap2&&window.__ufo_cap2.items)||[];
  return {
    href:location.href,
    hash:location.hash||'',
    title:document.title||'',
    hasTaskCenter:t.indexOf('办件中心')>=0,
    snippet:t.replace(/\s+/g,' ').trim().slice(0,220),
    l2Count:cap.length
  };
})()"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=180)
    args = ap.parse_args()

    ws_url, start_url = pick_ws()
    rec: Dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_url": start_url,
        "duration_seconds": args.seconds,
        "events": [],
        "requests": {},
    }
    if not ws_url:
        rec["result"] = "no_cdp_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws_url)
    try:
        # L1 enable
        c.call("Page.enable", {})
        c.call("Runtime.enable", {})
        c.call("Network.enable", {"maxTotalBufferSize": 100000000, "maxResourceBufferSize": 5000000})
        rec["events"].append({"ts": int(time.time() * 1000), "layer": "L3", "kind": "listener_started", "url": start_url})

        # L2 hook + first snapshot
        rec["events"].append({"ts": int(time.time() * 1000), "layer": "L2", "kind": "hook_install", "data": c.eval(HOOK_JS)})
        rec["events"].append({"ts": int(time.time() * 1000), "layer": "L3", "kind": "snapshot", "data": c.eval(SNAP_JS)})

        end = time.time() + args.seconds
        last_snap = time.time()

        while time.time() < end:
            msg = c.recv_one()
            if msg and "method" in msg:
                method = msg.get("method")
                p = msg.get("params", {}) or {}
                now_ms = int(time.time() * 1000)

                if method == "Network.requestWillBeSent":
                    rid = p.get("requestId")
                    req = p.get("request", {}) or {}
                    rec["requests"][rid] = rec["requests"].get(rid, {})
                    rec["requests"][rid].update(
                        {
                            "url": req.get("url"),
                            "method": req.get("method"),
                            "postData": req.get("postData"),
                            "start_ts": now_ms,
                            "type": p.get("type"),
                        }
                    )
                    rec["events"].append({"ts": now_ms, "layer": "L1", "kind": "request", "requestId": rid, "url": req.get("url"), "method": req.get("method")})
                elif method == "Network.responseReceived":
                    rid = p.get("requestId")
                    resp = p.get("response", {}) or {}
                    rec["requests"][rid] = rec["requests"].get(rid, {})
                    rec["requests"][rid].update(
                        {
                            "status": resp.get("status"),
                            "mimeType": resp.get("mimeType"),
                            "headers": resp.get("headers"),
                            "response_url": resp.get("url"),
                        }
                    )
                    rec["events"].append({"ts": now_ms, "layer": "L1", "kind": "response", "requestId": rid, "status": resp.get("status"), "url": resp.get("url")})
                elif method == "Network.loadingFinished":
                    rid = p.get("requestId")
                    body_ret = c.call("Network.getResponseBody", {"requestId": rid}, timeout=3.0)
                    body = None
                    if isinstance(body_ret, dict) and "error" not in body_ret:
                        body = body_ret.get("body")
                        if body and len(body) > 40000:
                            body = body[:40000]
                        rec["requests"][rid] = rec["requests"].get(rid, {})
                        rec["requests"][rid]["responseBody"] = body
                    rec["events"].append({"ts": now_ms, "layer": "L1", "kind": "finished", "requestId": rid})

            # L3 periodic snapshot
            if time.time() - last_snap >= 2.0:
                snap = c.eval(SNAP_JS)
                rec["events"].append({"ts": int(time.time() * 1000), "layer": "L3", "kind": "snapshot", "data": snap})
                last_snap = time.time()

        # pull L2 hook cache at end
        l2_dump = c.eval(
            r"""(function(){
              var cap=(window.__ufo_cap2&&window.__ufo_cap2.items)||[];
              return cap.slice(-1200);
            })()"""
        )
        rec["l2_dump"] = l2_dump
        rec["result"] = "ok"
    finally:
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        c.close()


if __name__ == "__main__":
    main()

