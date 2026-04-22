#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/navigate_no_final_refresh_record.json")
PORTAL_URL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fname-check-info"
)


def pick_ws(prefer_kw=None):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    if prefer_kw:
        for p in pages:
            if p.get("type") == "page" and prefer_kw in p.get("url", ""):
                return p["webSocketDebuggerUrl"]
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr, timeout=15000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"steps": []}
    ws = pick_ws()
    rec["steps"].append({"step": "S0_goto_portal", "data": ev(ws, f"location.href='{PORTAL_URL}'")})
    time.sleep(8)
    ws = pick_ws("portal.html#")
    ev(ws, "location.reload()")
    time.sleep(6)

    rec["steps"].append({"step": "S1_push_enterprise_zone", "data": ev(ws, "(function(){var r=document.getElementById('app').__vue__.$router; r.push('/index/enterprise/enterprise-zone'); return {hash:location.hash};})()")})
    time.sleep(3)
    ev(ws, "location.reload()")
    time.sleep(6)

    rec["steps"].append({"step": "S2_click_start", "data": ev(ws, "(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').includes('开始办理')); if(b){b.click();return {ok:true}} return {ok:false};})()")})
    time.sleep(4)
    ev(ws, "location.reload()")
    time.sleep(6)

    rec["steps"].append({"step": "S3_to_not_name", "data": ev(ws, "(function(){function f(v,d){if(!v||d>15)return null;if(v.$options&&v.$options.name==='without-name')return v;for(var c of (v.$children||[])){var r=f(c,d+1);if(r)return r;}return null;} var v=f(document.getElementById('app').__vue__,0); if(v&&typeof v.toNotName==='function'){v.toNotName();return {ok:true,hash:location.hash}} return {ok:false};})()")})
    time.sleep(4)
    ev(ws, "location.reload()")
    time.sleep(6)

    rec["steps"].append({"step": "S4_next_btn", "data": ev(ws, "(function(){function f(v,d){if(!v||d>15)return null;if(v.$options&&v.$options.name==='establish')return v;for(var c of (v.$children||[])){var r=f(c,d+1);if(r)return r;}return null;} var v=f(document.getElementById('app').__vue__,0); if(v&&v.$data&&v.$data.radioGroup&&v.$data.radioGroup.length){try{v.$set(v.$data.radioGroup[0],'checked','1100')}catch(e){}} if(v&&typeof v.nextBtn==='function'){v.nextBtn();return {ok:true,hash:location.hash}} return {ok:false};})()")})
    time.sleep(3)

    # 关键：不再刷新，直接记录 basic-info 内存态
    s = ev(ws, r"""(function(){
      function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
      var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null; var p=fc&&fc.params?fc.params:{};
      return {href:location.href,hash:location.hash,curCompUrl:fc?fc.curCompUrl:null,flowData:p.flowData||null,busiCompUrlPaths:fc?fc.busiCompUrlPaths:null};
    })()""")
    rec["steps"].append({"step": "S5_final_state_without_reload", "data": s})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

