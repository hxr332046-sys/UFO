#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 portal 全部服务入口开始，逐步进入设立登记 basic-info。
要求：每进入关键页面先刷新（reload）再继续，减少停留过久导致的异常。
仅导航与框架记录，不做填表/保存。
"""

import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/navigate_with_refresh_record.json")

# 入口页（全部服务）
PORTAL_URL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fname-check-info"
)


def get_pages():
    return requests.get("http://127.0.0.1:9225/json", timeout=5).json()


def pick_ws(prefer_kw=None):
    pages = get_pages()
    if prefer_kw:
        for p in pages:
            if p.get("type") == "page" and prefer_kw in p.get("url", ""):
                return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url: str, expr: str, timeout: int = 15):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "timeout": timeout * 1000},
            }
        )
    )
    ws.settimeout(timeout + 2)
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def snapshot(ws_url: str, tag: str):
    expr = r"""(function(){
  var names=[];
  function walk(vm,d){ if(!vm||d>8) return; var n=(vm.$options&&vm.$options.name)||''; if(n) names.push(n); (vm.$children||[]).forEach(function(c){walk(c,d+1);}); }
  var app=document.getElementById('app'); if(app&&app.__vue__) walk(app.__vue__,0);
  var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;})
    .map(function(b){return {text:(b.textContent||'').trim().slice(0,30),disabled:!!b.disabled,cls:(b.className||'').slice(0,40)};})
    .slice(0,30);
  var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
  return {title:document.title,href:location.href,hash:location.hash,forms:document.querySelectorAll('.el-form-item').length,
          compNames:Array.from(new Set(names)).slice(0,40),buttons:btns,errors:errs.slice(0,10)};
})()"""
    data = ev(ws_url, expr, timeout=15)
    return {"tag": tag, "time": time.strftime("%H:%M:%S"), "data": data}


def reload_and_wait(ws_url: str, sec: int = 8):
    ev(ws_url, "location.reload()")
    time.sleep(sec)


def router_push(ws_url: str, path: str):
    expr = f"""(function(){{
      var app=document.getElementById('app');
      if(!app||!app.__vue__||!app.__vue__.$router) return {{ok:false,err:'no_router'}};
      try{{ app.__vue__.$router.push('{path}'); return {{ok:true,path:'{path}',hash:location.hash}}; }}
      catch(e){{ return {{ok:false,err:String(e).slice(0,120)}}; }}
    }})()"""
    return ev(ws_url, expr, timeout=12)


def click_button_contains(ws_url: str, text_kw: str):
    expr = f"""(function(){{
      var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(b=>b.offsetParent!==null);
      for(var i=0;i<btns.length;i++){{ var t=(btns[i].textContent||'').trim(); if(t.includes('{text_kw}')){{ btns[i].click(); return {{clicked:true,text:t,disabled:!!btns[i].disabled}}; }} }}
      return {{clicked:false}};
    }})()"""
    return ev(ws_url, expr, timeout=10)


def call_component_method(ws_url: str, comp_name: str, method: str):
    expr = f"""(function(){{
      var app=document.getElementById('app'); if(!app||!app.__vue__) return {{ok:false,err:'no_vue'}};
      function find(vm,name,d){{ if(!vm||d>15) return null; if(vm.$options&&vm.$options.name===name) return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){{ var r=find(vm.$children[i],name,d+1); if(r) return r; }} return null; }}
      var c=find(app.__vue__,'{comp_name}',0); if(!c) return {{ok:false,err:'no_comp'}};
      // establish.nextBtn 前必须给 radioGroup 设置 checked=1100（否则 flow 路由可能不注册）
      if('{comp_name}'==='establish' && '{method}'==='nextBtn' && c.$data && c.$data.radioGroup && c.$data.radioGroup.length){{
        try{{ c.$set(c.$data.radioGroup[0],'checked','1100'); }}catch(e){{}}
      }}
      if(typeof c['{method}']!=='function') return {{ok:false,err:'no_method'}};
      c['{method}'](); return {{ok:true,called:'{comp_name}.{method}',hash:location.hash}};
    }})()"""
    return ev(ws_url, expr, timeout=12)


def main():
    record = {"portal_url": PORTAL_URL, "steps": []}

    ws, cur = pick_ws()
    if not ws:
        print("No zhjg page found in CDP.")
        return

    # Step 0: 强制回到 portal 入口并刷新
    record["steps"].append({"step": "S0_goto_portal", "data": ev(ws, f"location.href='{PORTAL_URL}'", timeout=12)})
    time.sleep(8)
    ws, cur = pick_ws("portal.html#")
    if not ws:
        ws, cur = pick_ws()
    reload_and_wait(ws, 8)
    record["steps"].append({"step": "S1_portal_snapshot", **snapshot(ws, "portal")})

    # Step 1: 进入 enterprise-zone（已知可用）
    record["steps"].append({"step": "S2_router_push_enterprise_zone", "data": router_push(ws, "/index/enterprise/enterprise-zone")})
    time.sleep(2)
    reload_and_wait(ws, 6)
    record["steps"].append({"step": "S3_enterprise_zone_snapshot", **snapshot(ws, "enterprise-zone")})

    # Step 2: 点击开始办理 -> without-name
    record["steps"].append({"step": "S4_click_start", "data": click_button_contains(ws, "开始办理")})
    time.sleep(4)
    reload_and_wait(ws, 6)
    record["steps"].append({"step": "S5_without_name_snapshot", **snapshot(ws, "without-name")})

    # Step 3: toNotName -> establish
    record["steps"].append({"step": "S6_call_toNotName", "data": call_component_method(ws, "without-name", "toNotName")})
    time.sleep(4)
    reload_and_wait(ws, 6)
    record["steps"].append({"step": "S7_establish_snapshot", **snapshot(ws, "establish")})

    # Step 4: nextBtn -> basic-info
    # 这里优先走组件方法 nextBtn（你们记录里必需）
    record["steps"].append({"step": "S8_call_nextBtn", "data": call_component_method(ws, "establish", "nextBtn")})
    time.sleep(2)

    # 关键：不能立刻刷新。先等待路由真的进入 flow/basic-info
    wait_expr = r"""(function(){
      return {href:location.href,hash:location.hash};
    })()"""
    reached = None
    for _ in range(10):
        cur = ev(ws, wait_expr, timeout=8)
        h = (cur or {}).get("hash", "")
        u = (cur or {}).get("href", "")
        if ("#/flow/base/basic-info" in h) or ("core.html#/flow/base/basic-info" in u):
            reached = cur
            break
        time.sleep(1.5)
    record["steps"].append({"step": "S9_wait_flow_result", "data": reached or {"reached": False}})

    if reached:
        # 进入 flow 后再刷新，保证页面不过期
        reload_and_wait(ws, 8)
        record["steps"].append({"step": "S10_basic_info_snapshot", **snapshot(ws, "basic-info")})
    else:
        # 兜底：尝试直接推到 basic-info
        record["steps"].append(
            {"step": "S10_fallback_push_basic_info", "data": router_push(ws, "/flow/base/basic-info")}
        )
        time.sleep(2)
        reload_and_wait(ws, 8)
        record["steps"].append({"step": "S11_basic_info_snapshot_after_fallback", **snapshot(ws, "basic-info")})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

