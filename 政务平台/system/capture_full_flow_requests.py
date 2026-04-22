#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/full_flow_requests_capture.json")
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


def install_probe(ws_url):
    return ev(
        ws_url,
        r"""(function(){
          window.__flow_probe={reqs:[],resps:[]};
          var oo=XMLHttpRequest.prototype.open;
          var os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('/icpsp-api/')>=0){
              var body=(b||'');
              window.__flow_probe.reqs.push({m:this.__m||'GET',u:u.slice(0,260),len:body.length,body:body.slice(0,380)});
              var self=this;
              self.addEventListener('load',function(){
                window.__flow_probe.resps.push({u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,420)});
              });
            }
            return os.apply(this,arguments);
          };
          return {ok:true,href:location.href,hash:location.hash};
        })()""",
    )


def main():
    rec = {"steps": []}

    ws, u = pick_ws()
    rec["steps"].append({"step": "S0_pick_page", "data": {"url": u}})
    if not ws:
        rec["error"] = "no_zhjg_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append({"step": "S1_install_probe_init", "data": install_probe(ws)})

    rec["steps"].append({"step": "S2_goto_portal", "data": ev(ws, f"location.href='{PORTAL_URL}'", timeout=12000)})
    time.sleep(8)
    ws, _ = pick_ws("portal.html#")
    rec["steps"].append({"step": "S3_install_probe_portal", "data": install_probe(ws)})
    ev(ws, "location.reload()")
    time.sleep(6)

    rec["steps"].append({"step": "S4_push_enterprise_zone", "data": ev(ws, "(function(){var app=document.getElementById('app'); if(!app||!app.__vue__||!app.__vue__.$router)return {ok:false}; app.__vue__.$router.push('/index/enterprise/enterprise-zone'); return {ok:true,hash:location.hash};})()")})
    time.sleep(3)
    ev(ws, "location.reload()")
    time.sleep(6)

    rec["steps"].append({"step": "S5_click_start", "data": ev(ws, "(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').includes('开始办理')); if(b){b.click();return {ok:true,text:(b.textContent||'').trim()};} return {ok:false};})()")})
    time.sleep(4)
    rec["steps"].append({"step": "S6_probe_after_start", "data": ev(ws, "window.__flow_probe")})

    ev(ws, "location.reload()")
    time.sleep(6)
    rec["steps"].append({"step": "S7_to_not_name", "data": ev(ws, "(function(){function f(v,d){if(!v||d>15)return null;if(v.$options&&v.$options.name==='without-name')return v;for(var c of (v.$children||[])){var r=f(c,d+1);if(r)return r;}return null;} var app=document.getElementById('app'); var v=app&&app.__vue__?f(app.__vue__,0):null; if(v&&typeof v.toNotName==='function'){v.toNotName(); return {ok:true,hash:location.hash};} return {ok:false};})()")})
    time.sleep(4)
    rec["steps"].append({"step": "S8_probe_after_not_name", "data": ev(ws, "window.__flow_probe")})

    ev(ws, "location.reload()")
    time.sleep(6)
    rec["steps"].append({"step": "S9_next_btn", "data": ev(ws, "(function(){function f(v,d){if(!v||d>15)return null;if(v.$options&&v.$options.name==='establish')return v;for(var c of (v.$children||[])){var r=f(c,d+1);if(r)return r;}return null;} var app=document.getElementById('app'); var v=app&&app.__vue__?f(app.__vue__,0):null; if(v&&v.$data&&v.$data.radioGroup&&v.$data.radioGroup.length){try{v.$set(v.$data.radioGroup[0],'checked','1100')}catch(e){}} if(v&&typeof v.nextBtn==='function'){v.nextBtn(); return {ok:true,hash:location.hash};} return {ok:false};})()")})
    time.sleep(6)
    rec["steps"].append({"step": "S10_probe_after_next", "data": ev(ws, "window.__flow_probe")})

    rec["steps"].append({"step": "S11_final_state", "data": ev(ws, "(function(){return {href:location.href,hash:location.hash};})()")})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

