#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在 name-check-info 页面执行一次“保存并下一步”，并用 CDP Network 抓取相关请求/响应。

目标：
- 找到触发“主营行业不能为空 / A0002”的后端接口
- 抓到 request postData 与 response body，便于对照缺失字段

约束：
- 单次点击，不循环
- 仅聚焦 /icpsp-api/ 请求（会截断 body 以免文件过大）
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_capture_namecheck_save_once.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, ""


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
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


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "page": cur, "steps": []}
    if not ws_url:
        rec["error"] = "no_namecheck_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws_url)
    try:
        c.call("Network.enable", {})
        c.call("Page.enable", {})

        # Install XHR + fetch hooks (more reliable than Network events when
        # submission is blocked or when requests happen outside our event window).
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
                          if(window.__ufo_cap.items.length>60) window.__ufo_cap.items.shift();
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
                            pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u,body:String(body||'').slice(0,20000)});
                            self.addEventListener('loadend', function(){
                              pushOne({t:'xhr_end',u:u,status:self.status,resp:String(self.responseText||'').slice(0,20000)});
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
                              var b = (init && init.body) ? String(init.body).slice(0,20000) : '';
                              pushOne({t:'fetch',m:m,u:u,body:b});
                              return OF.apply(this, arguments).then(function(res){
                                try{
                                  return res.clone().text().then(function(txt){
                                    pushOne({t:'fetch_end',u:u,status:res.status,resp:String(txt||'').slice(0,20000)});
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

        # clean state & read visible errors
        rec["steps"].append(
            {
                "step": "state_before",
                "data": c.ev(
                    r"""(function(){
                      function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                      var txt=(document.body.innerText||'');
                      var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>clean(e.textContent)).filter(Boolean);
                      return {href:location.href,hash:location.hash,hasMainIndustryEmpty:txt.indexOf('主营行业不能为空')>=0,errs:errs.slice(0,10)};
                    })()"""
                ),
            }
        )

        # click "确定" if modal exists to avoid blocking
        rec["steps"].append(
            {
                "step": "click_ok_if_any",
                "data": c.ev(
                    r"""(function(){
                      function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                      var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&!x.disabled&&clean(x.textContent).indexOf('确定')>=0);
                      if(btn){btn.click();return {clicked:true};}
                      return {clicked:false};
                    })()"""
                ),
            }
        )

        # perform ONE click save-next (no loop)
        rec["steps"].append(
            {
                "step": "click_save_next_once",
                "data": c.ev(
                    r"""(function(){
                      function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                      function vis(x){return !!(x && x.offsetParent!==null);}
                      function click(el){ if(!el) return false; ['mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}))); return true; }
                      // find by exact button first
                      var btn=[...document.querySelectorAll('button,.el-button')].find(x=>vis(x)&&!x.disabled&&clean(x.textContent).replace(/\s+/g,'').indexOf('保存并下一步')>=0);
                      if(btn){ click(btn); return {clicked:true,mode:'button'}; }
                      // fallback: find any node containing the text, then click closest button
                      var node=[...document.querySelectorAll('button,.el-button,span,div,a')].find(x=>vis(x)&&clean(x.textContent).replace(/\s+/g,'').indexOf('保存并下一步')>=0);
                      if(node){
                        var host = node.closest && node.closest('button,.el-button') ? node.closest('button,.el-button') : node;
                        click(host);
                        return {clicked:true,mode:'closest',tag:(host&&host.tagName)||''};
                      }
                      // evidence: list visible buttons text
                      var texts=[...document.querySelectorAll('button,.el-button')].filter(vis).map(x=>clean(x.textContent)).filter(Boolean).slice(0,15);
                      return {clicked:false,reason:'not_found',visibleButtons:texts};
                    })()"""
                ),
            }
        )

        # wait a bit for hooks to capture
        time.sleep(2.0)
        rec["steps"].append(
            {
                "step": "hook_captures",
                "data": c.ev(r"""(function(){return window.__ufo_cap ? {count:(window.__ufo_cap.items||[]).length,items:(window.__ufo_cap.items||[])} : {count:0,items:[]};})()"""),
            }
        )

        # collect network for a short window
        time.sleep(1.0)
        events = []
        end = time.time() + 10.0
        while time.time() < end:
            try:
                msg = json.loads(c.ws.recv())
            except Exception:
                continue
            m = msg.get("method")
            p = msg.get("params") or {}
            if m in ("Network.requestWillBeSent", "Network.responseReceived", "Network.loadingFailed"):
                events.append({"method": m, "params": p})

        # normalize to req/resp pairs for icpsp-api
        req_by_id = {}
        res_by_id = {}
        for e in events:
            m = e["method"]
            p = e["params"] or {}
            if m == "Network.requestWillBeSent":
                r = p.get("request") or {}
                url = r.get("url") or ""
                if "/icpsp-api/" not in url:
                    continue
                rid = p.get("requestId")
                req_by_id[rid] = {
                    "requestId": rid,
                    "url": url,
                    "method": r.get("method"),
                    "postData": (r.get("postData") or "")[:20000],
                    "headers": {k: v for k, v in (r.get("headers") or {}).items() if k.lower() in ("content-type", "x-requested-with")},
                }
            elif m == "Network.responseReceived":
                r = p.get("response") or {}
                url = r.get("url") or ""
                if "/icpsp-api/" not in url:
                    continue
                rid = p.get("requestId")
                body = None
                b = c.call("Network.getResponseBody", {"requestId": rid}, timeout=6)
                body = ((b.get("result") or {}).get("body") or "")[:20000]
                res_by_id[rid] = {"requestId": rid, "url": url, "status": r.get("status"), "body": body}

        pairs = []
        for rid, req in req_by_id.items():
            pairs.append({"req": req, "resp": res_by_id.get(rid)})

        rec["steps"].append({"step": "network_pairs", "data": {"count": len(pairs), "pairs": pairs}})
        rec["steps"].append(
            {
                "step": "state_after",
                "data": c.ev(
                    r"""(function(){
                      function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                      var txt=(document.body.innerText||'');
                      var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>clean(e.textContent)).filter(Boolean);
                      return {href:location.href,hash:location.hash,hasMainIndustryEmpty:txt.indexOf('主营行业不能为空')>=0,errs:errs.slice(0,10)};
                    })()"""
                ),
            }
        )
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
    finally:
        c.close()


if __name__ == "__main__":
    main()

