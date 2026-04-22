#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/flow_requests_persistent.json")
PORTAL_URL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fname-check-info"
)


def pick_ws(url_kw=None):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    if url_kw:
        for p in pages:
            if p.get("type") == "page" and url_kw in p.get("url", ""):
                return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=20000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


INSTALL_EXPR = r"""(function(){
  var KEY='__FLOW_REQ_LOG__';
  function read(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){return[]}}
  function write(v){try{localStorage.setItem(KEY,JSON.stringify(v).slice(0,4000000))}catch(e){}}
  var log=read();
  log.push({t:Date.now(),type:'mark',href:location.href,hash:location.hash,msg:'install_probe'});
  write(log);
  if(window.__flow_persist_installed){return {ok:true,installed:true,count:read().length};}
  window.__flow_persist_installed=true;
  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments)};
  XMLHttpRequest.prototype.send=function(b){
    var u=this.__u||'';
    if(u.indexOf('/icpsp-api/')>=0){
      var arr=read();
      arr.push({t:Date.now(),type:'req',m:this.__m||'GET',u:u.slice(0,300),len:(b||'').length,body:(b||'').slice(0,420),href:location.href,hash:location.hash});
      write(arr);
      var self=this;
      self.addEventListener('load',function(){
        var arr2=read();
        arr2.push({t:Date.now(),type:'resp',u:u.slice(0,300),status:self.status,text:(self.responseText||'').slice(0,520),href:location.href,hash:location.hash});
        write(arr2);
      });
    }
    return os.apply(this,arguments);
  };
  return {ok:true,installed:true,count:read().length};
})()"""


def read_log(ws_url):
    return ev(
        ws_url,
        r"""(function(){
          try{return JSON.parse(localStorage.getItem('__FLOW_REQ_LOG__')||'[]')}catch(e){return[]}
        })()""",
    )


def main():
    rec = {"steps": []}
    ws, u = pick_ws()
    rec["steps"].append({"step": "S0_start_page", "data": u})
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append({"step": "S1_install", "data": ev(ws, INSTALL_EXPR)})
    ev(ws, "localStorage.removeItem('__FLOW_REQ_LOG__')")
    rec["steps"].append({"step": "S2_clear_log", "data": True})
    rec["steps"].append({"step": "S3_install_again", "data": ev(ws, INSTALL_EXPR)})

    rec["steps"].append({"step": "S4_goto_portal", "data": ev(ws, f"location.href='{PORTAL_URL}'", timeout=12000)})
    time.sleep(8)
    ws, u = pick_ws("portal.html#")
    rec["steps"].append({"step": "S5_on_portal", "data": u})
    rec["steps"].append({"step": "S6_install_portal", "data": ev(ws, INSTALL_EXPR)})

    rec["steps"].append({"step": "S7_push_enterprise_zone", "data": ev(ws, "(function(){var app=document.getElementById('app'); if(!app||!app.__vue__||!app.__vue__.$router)return {ok:false}; app.__vue__.$router.push('/index/enterprise/enterprise-zone'); return {ok:true,hash:location.hash};})()")})
    time.sleep(3)
    rec["steps"].append({"step": "S8_click_start", "data": ev(ws, "(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').includes('开始办理')); if(b){b.click(); return {ok:true,text:(b.textContent||'').trim()};} return {ok:false};})()")})
    time.sleep(4)

    rec["steps"].append({"step": "S9_to_not_name", "data": ev(ws, "(function(){function f(v,d){if(!v||d>15)return null;if(v.$options&&v.$options.name==='without-name')return v;for(var c of (v.$children||[])){var r=f(c,d+1);if(r)return r;}return null;} var app=document.getElementById('app'); var v=app&&app.__vue__?f(app.__vue__,0):null; if(v&&typeof v.toNotName==='function'){v.toNotName();return {ok:true,hash:location.hash};} return {ok:false,hash:location.hash};})()")})
    time.sleep(4)

    rec["steps"].append({"step": "S10_next_btn", "data": ev(ws, "(function(){function f(v,d){if(!v||d>15)return null;if(v.$options&&v.$options.name==='establish')return v;for(var c of (v.$children||[])){var r=f(c,d+1);if(r)return r;}return null;} var app=document.getElementById('app'); var v=app&&app.__vue__?f(app.__vue__,0):null; if(v&&v.$data&&v.$data.radioGroup&&v.$data.radioGroup.length){try{v.$set(v.$data.radioGroup[0],'checked','1100')}catch(e){}} if(v&&typeof v.nextBtn==='function'){v.nextBtn(); return {ok:true,hash:location.hash};} return {ok:false,hash:location.hash};})()")})
    time.sleep(6)

    ws2, u2 = pick_ws("core.html#/flow/base/basic-info")
    if not ws2:
        ws2, u2 = pick_ws("core.html#/flow/base/")
    rec["steps"].append({"step": "S11_core_page", "data": u2})
    if ws2:
        rec["steps"].append({"step": "S12_install_core", "data": ev(ws2, INSTALL_EXPR)})
        rec["steps"].append({"step": "S13_core_state", "data": ev(ws2, "(function(){return {href:location.href,hash:location.hash};})()")})

    # 尝试从 portal / core 两端读取持久日志，取更长者
    log1 = read_log(ws) if ws else []
    log2 = read_log(ws2) if ws2 else []
    rec["log_len_portal"] = len(log1 or [])
    rec["log_len_core"] = len(log2 or [])
    rec["log"] = log1 if len(log1 or []) >= len(log2 or []) else log2

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

