#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从「全部服务」页点击「设立登记」，用 XHR hook 抓取 /icpsp-api/ 请求与响应。
用于证明上下文是否必须从门户入口建立（与直达 guide/base 对比）。
单次执行，不循环。
"""
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_capture_portal_establish_entry.json")

# 与线上一致：全部服务 + name-register 回跳上下文（fromPage 指向名称申报说明页）
PORTAL_ALL_SERVICES = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/page?fromProject=name-register&fromPage=%2Fnamenotice%2Fdeclaration-instructions"
)


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, ""


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method, params=None, timeout=18):
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

    def ev(self, expr: str, timeout_ms=120000):
        m = self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
                "timeout": timeout_ms,
            },
            timeout=22,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


HOOK_JS = r"""(function(){
  window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
  function pushOne(x){
    try{
      x.ts = Date.now();
      window.__ufo_cap.items.push(x);
      if(window.__ufo_cap.items.length > 200) window.__ufo_cap.items.shift();
    }catch(e){}
  }
  if(!window.__ufo_cap.installed){
    var XO = XMLHttpRequest.prototype.open, XS = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m,u){
      this.__ufo = {m:m,u:u};
      return XO.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body){
      var self = this;
      var u = (self.__ufo && self.__ufo.u) || '';
      if(String(u).indexOf('/icpsp-api/') >= 0){
        pushOne({t:'xhr', m:(self.__ufo&&self.__ufo.m)||'', u:u, body:String(body||'').slice(0,50000)});
        self.addEventListener('loadend', function(){
          pushOne({t:'xhr_end', u:u, status:self.status, resp:String(self.responseText||'').slice(0,50000)});
        });
      }
      return XS.apply(this, arguments);
    };
    var OF = window.fetch;
    if(typeof OF === 'function'){
      window.fetch = function(input, init){
        try{
          var u = (typeof input === 'string') ? input : (input && input.url) || '';
          if(String(u).indexOf('/icpsp-api/') >= 0){
            var m = (init && init.method) || 'GET';
            var b = (init && init.body) ? String(init.body).slice(0,50000) : '';
            pushOne({t:'fetch', m:m, u:u, body:b});
            return OF.apply(this, arguments).then(function(res){
              try{
                return res.clone().text().then(function(txt){
                  pushOne({t:'fetch_end', u:u, status:res.status, resp:String(txt||'').slice(0,50000)});
                  return res;
                });
              }catch(e){ return res; }
            });
          }
        }catch(e){}
        return OF.apply(this, arguments);
      };
    }
    window.__ufo_cap.installed = true;
  }
  window.__ufo_cap.items = [];
  return {ok:true};
})()"""

CLICK_ESTABLISH_JS = r"""(function(){
  function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
  var all = document.querySelectorAll('*');
  for(var i=0;i<all.length;i++){
    var t = clean(all[i].textContent);
    var rect = all[i].getBoundingClientRect();
    if(t === '设立登记' && rect.width>0 && rect.height>0 && all[i].children.length===0){
      var el = all[i];
      for(var j=0;j<4;j++){
        if(!el.parentElement) break;
        el = el.parentElement;
        if(el.tagName==='A' || el.tagName==='BUTTON' || (el.className||'').indexOf('cursor')>=0) break;
      }
      el.click();
      return {ok:true, strategy:'text_leaf_parent', tag:el.tagName};
    }
  }
  var hit = [...document.querySelectorAll('a,button,div,span')].find(function(e){
    return e.offsetParent!==null && clean(e.textContent).indexOf('设立登记')>=0 && clean(e.textContent).length<80;
  });
  if(hit){ hit.click(); return {ok:true, strategy:'first_contains', text:clean(hit.textContent).slice(0,60)}; }
  return {ok:false};
})()"""


def main():
    ws_url, cur = pick_ws()
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "page_before": cur,
        "portal_url": PORTAL_ALL_SERVICES,
        "steps": [],
    }
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
                "step": "nav_portal_all_services",
                "data": c.ev(f"location.href={json.dumps(PORTAL_ALL_SERVICES, ensure_ascii=False)}"),
            }
        )
        time.sleep(4)
        rec["steps"].append({"step": "install_hook", "data": c.ev(HOOK_JS)})
        rec["steps"].append(
            {
                "step": "state_before_click",
                "data": c.ev(
                    r"""(function(){
                      return {href:location.href, hash:location.hash, title:document.title};
                    })()"""
                ),
            }
        )
        rec["steps"].append({"step": "click_establish_registration", "data": c.ev(CLICK_ESTABLISH_JS)})
        time.sleep(6)
        rec["steps"].append(
            {
                "step": "state_after_click",
                "data": c.ev(
                    r"""(function(){
                      return {href:location.href, hash:location.hash, title:document.title};
                    })()"""
                ),
            }
        )
        rec["steps"].append(
            {
                "step": "captured_packets",
                "data": c.ev(
                    r"""(function(){
                      var c = window.__ufo_cap || {items:[]};
                      return {count:(c.items||[]).length, items:(c.items||[])};
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
