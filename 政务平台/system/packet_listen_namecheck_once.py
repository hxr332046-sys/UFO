#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
监听 name-check-info 页面的一次提交相关数据包（XHR/fetch）。

用法：
1) 先运行本脚本，它会安装 hook 并进入等待（最多 wait_seconds）。
2) 用户在页面上操作一次（行业下拉点选一条候选 -> 点“保存并下一步”）。
3) 脚本捕获到 /icpsp-api/ 请求/响应后立即保存并退出。

约束：
- 不自动点击，不循环轰炸
- 只抓 /icpsp-api/，并截断 body 防止文件过大
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_listen_namecheck_once.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, ""


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method, params=None, timeout=12):
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

    def ev(self, expr: str, timeout_ms=90000):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            timeout=15,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main(wait_seconds: int = 180):
    ws_url, cur = pick_ws()
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "page": cur,
        "wait_seconds": wait_seconds,
        "steps": [],
        "result": "waiting",
    }
    if not ws_url:
        rec["error"] = "no_namecheck_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws_url)
    try:
        start_ts = int(time.time() * 1000)
        # Install hooks once
        rec["steps"].append(
            {
                "step": "install_hooks",
                "data": c.ev(
                    r"""(function(){
                      window.__ufo_cap = window.__ufo_cap || {items:[], installed:false};
                      if(window.__ufo_cap.installed) return {ok:true,already:true,count:window.__ufo_cap.items.length};
                      window.__ufo_cap.items = [];
                      function pushOne(x){
                        try{
                          x.ts = Date.now();
                          window.__ufo_cap.items.push(x);
                          if(window.__ufo_cap.items.length>80) window.__ufo_cap.items.shift();
                        }catch(e){}
                      }
                      // XHR
                      var XO = XMLHttpRequest.prototype.open;
                      var XS = XMLHttpRequest.prototype.send;
                      XMLHttpRequest.prototype.open = function(m,u){
                        try{ this.__ufo = {m:m,u:u}; }catch(e){}
                        return XO.apply(this, arguments);
                      };
                      XMLHttpRequest.prototype.send = function(body){
                        var self=this;
                        try{
                          var u=(self.__ufo&&self.__ufo.u)||'';
                          if(String(u).indexOf('/icpsp-api/')>=0){
                            pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u,body:String(body||'').slice(0,40000)});
                            self.addEventListener('loadend', function(){
                              pushOne({t:'xhr_end',u:u,status:self.status,resp:String(self.responseText||'').slice(0,40000)});
                            });
                          }
                        }catch(e){}
                        return XS.apply(this, arguments);
                      };
                      // fetch
                      var OF = window.fetch;
                      if(typeof OF === 'function'){
                        window.fetch = function(input, init){
                          try{
                            var u = (typeof input==='string') ? input : (input && input.url) || '';
                            if(String(u).indexOf('/icpsp-api/')>=0){
                              var m = (init && init.method) || 'GET';
                              var b = (init && init.body) ? String(init.body).slice(0,40000) : '';
                              pushOne({t:'fetch',m:m,u:u,body:b});
                              return OF.apply(this, arguments).then(function(res){
                                try{
                                  return res.clone().text().then(function(txt){
                                    pushOne({t:'fetch_end',u:u,status:res.status,resp:String(txt||'').slice(0,40000)});
                                    return res;
                                  });
                                }catch(e){
                                  return res;
                                }
                              });
                            }
                          }catch(e){}
                          return OF.apply(this, arguments);
                        };
                      }
                      window.__ufo_cap.installed = true;
                      return {ok:true,already:false};
                    })()"""
                ),
            }
        )

        # Clear old captures to avoid false "captured"
        rec["steps"].append(
            {
                "step": "clear_old",
                "data": c.ev(
                    r"""(function(){
                      if(!window.__ufo_cap) window.__ufo_cap = {items:[], installed:true};
                      var prev = (window.__ufo_cap.items||[]).length;
                      window.__ufo_cap.items = [];
                      return {ok:true,prev:prev};
                    })()"""
                ),
            }
        )

        rec["steps"].append(
            {
                "step": "ready",
                "data": c.ev(
                    r"""(function(){
                      function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                      var txt=(document.body.innerText||'');
                      return {href:location.href,hash:location.hash,hasMainIndustryEmpty:txt.indexOf('主营行业不能为空')>=0,hasSaveText:txt.indexOf('保存并下一步')>=0};
                    })()"""
                ),
            }
        )

        print("LISTEN_READY: 请在页面上操作一次（选行业候选 -> 点保存并下一步）")

        # Wait/poll until we see SUBMIT capture items (not just suggestion queries)
        def is_submit_url(u: str) -> bool:
            u = (u or "")
            return (
                "operationBusiness" in u
                or "flowSave" in u
                or "NameCheckInfo" in u and "save" in u.lower()
                or "register/name/component" in u
            )

        deadline = time.time() + wait_seconds
        last_count = -1
        while time.time() < deadline:
            cap = c.ev(r"""(function(){return window.__ufo_cap ? {count:(window.__ufo_cap.items||[]).length,items:(window.__ufo_cap.items||[])} : {count:0,items:[]};})()""")
            if isinstance(cap, dict):
                count = int(cap.get("count") or 0)
                if count != last_count and count > 0:
                    items = cap.get("items") or []
                    # filter only new + submit-like
                    picked = []
                    for it in items:
                        try:
                            ts = int(it.get("ts") or 0)
                        except Exception:
                            ts = 0
                        u = it.get("u") or ""
                        if ts >= start_ts and "/icpsp-api/" in u and is_submit_url(u):
                            picked.append(it)
                    if picked:
                        rec["steps"].append({"step": "captured_submit", "data": {"count": len(picked), "items": picked}})
                        # also keep full buffer for context
                        rec["steps"].append({"step": "captured_buffer", "data": cap})
                        rec["result"] = "captured_submit"
                        break
                last_count = count
            time.sleep(1.0)

        if rec["result"] != "captured_submit":
            rec["result"] = "timeout_no_submit_packets"

        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
    finally:
        c.close()


if __name__ == "__main__":
    main()

