#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
仓库已验证链路：portal 企业专区(busyType) → 点击「开始办理」。
XHR hook 抓取 /icpsp-api/，用于与直达 guide/base 对比上下文。
"""
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_capture_enterprise_zone_start.json")

# 与 icpsp_entry.enterprise_zone_entry_url 一致（避免包路径导入问题）
def enterprise_zone_entry_url(busi_type: str = "02_4") -> str:
    from urllib.parse import quote

    q = (
        "fromProject=portal"
        "&fromPage=%2Findex%2Fpage"
        f"&busiType={busi_type}"
        "&merge=Y"
    )
    return f"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?{q}"


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
  function pushOne(x){ try{ x.ts=Date.now(); window.__ufo_cap.items.push(x); if(window.__ufo_cap.items.length>200) window.__ufo_cap.items.shift(); }catch(e){} }
  if(!window.__ufo_cap.installed){
    var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return XO.apply(this,arguments); };
    XMLHttpRequest.prototype.send=function(body){
      var self=this, u=(self.__ufo&&self.__ufo.u)||'';
      if(String(u).indexOf('/icpsp-api/')>=0){
        pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u,body:String(body||'').slice(0,50000)});
        self.addEventListener('loadend',function(){ pushOne({t:'xhr_end',u:u,status:self.status,resp:String(self.responseText||'').slice(0,50000)}); });
      }
      return XS.apply(this,arguments);
    };
    window.__ufo_cap.installed=true;
  }
  window.__ufo_cap.items=[];
  return {ok:true};
})()"""

CLICK_START_JS = r"""(function(){
  function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
  var btns=[...document.querySelectorAll('button,.el-button,a,span,div')].filter(function(e){ return e.offsetParent!==null; });
  var hit=btns.find(function(b){ var t=clean(b.textContent); return t==='开始办理' || (t.indexOf('开始办理')>=0 && t.length<20); });
  if(hit){
    var el = hit.closest && hit.closest('button,.el-button,a') ? hit.closest('button,.el-button,a') : hit;
    el.click();
    return {ok:true,text:clean(el.textContent).slice(0,40)};
  }
  return {ok:false};
})()"""


def main():
    ws_url, cur = pick_ws()
    target = enterprise_zone_entry_url("02_4")
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "page_before": cur,
        "enterprise_zone_url": target,
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
            {"step": "nav_enterprise_zone", "data": c.ev(f"location.href={json.dumps(target, ensure_ascii=False)}")}
        )
        time.sleep(5)
        rec["steps"].append({"step": "install_hook", "data": c.ev(HOOK_JS)})
        rec["steps"].append(
            {
                "step": "state_before",
                "data": c.ev(r"""(function(){return {href:location.href,hash:location.hash};})()"""),
            }
        )
        rec["steps"].append({"step": "click_start", "data": c.ev(CLICK_START_JS)})
        # 等待跳到 name-register 后立即装 hook，减少首屏接口漏抓
        for _ in range(40):
            href = c.ev(r"""(function(){return location.href;})()""")
            if isinstance(href, str) and "name-register" in href:
                break
            time.sleep(0.25)
        rec["steps"].append(
            {
                "step": "state_after",
                "data": c.ev(r"""(function(){return {href:location.href,hash:location.hash};})()"""),
            }
        )
        # 整页跳到 name-register.html 会清空之前注入的 hook，必须在新文档上重装
        rec["steps"].append({"step": "install_hook_after_nav", "data": c.ev(HOOK_JS)})
        time.sleep(6)
        rec["steps"].append(
            {
                "step": "captured_packets",
                "data": c.ev(
                    r"""(function(){var c=window.__ufo_cap||{items:[]};return {count:(c.items||[]).length,items:(c.items||[])};})()"""
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
