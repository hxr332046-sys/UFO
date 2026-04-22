#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""逐步测试路由可跳转性，产出可跳/不可跳清单。"""

import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/route_jumpability_report.json")

ROUTES = [
    "/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fname-check-info",
    "/index/enterprise/enterprise-zone",
    "/index/without-name?entType=1100",
    "/index/enterprise/establish?busiType=02&entType=1100",
    "/flow/base/basic-info",
    "/flow/base/name-check-info",
]


def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url: str, expr: str, timeout: int = 12):
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
            if "exceptionDetails" in m.get("result", {}):
                return {"__exception__": m["result"]["exceptionDetails"].get("text", "js_exception")}
            return m.get("result", {}).get("result", {}).get("value")


def snapshot(ws_url: str):
    expr = r"""(function(){
  var app=document.getElementById('app');
  var names=[];
  function walk(vm,d){ if(!vm||d>8)return; var n=(vm.$options&&vm.$options.name)||''; if(n)names.push(n); (vm.$children||[]).forEach(function(c){walk(c,d+1)}); }
  if(app&&app.__vue__) walk(app.__vue__,0);
  return {
    href: location.href,
    hash: location.hash,
    title: document.title,
    forms: document.querySelectorAll('.el-form-item').length,
    compNames: Array.from(new Set(names)).slice(0,30),
    hasFlowControl: Array.from(new Set(names)).includes('flow-control'),
    hasEstablish: Array.from(new Set(names)).includes('establish'),
    hasWithoutName: Array.from(new Set(names)).includes('without-name'),
    errors: Array.from(document.querySelectorAll('.el-form-item__error')).map(e=>(e.textContent||'').trim()).filter(Boolean).slice(0,10)
  };
})()"""
    return ev(ws_url, expr, timeout=12)


def push_route(ws_url: str, route: str):
    expr = f"""(function(){{
  var app=document.getElementById('app');
  if(!app||!app.__vue__||!app.__vue__.$router) return {{ok:false,err:'no_router'}};
  try {{
    app.__vue__.$router.push('{route}');
    return {{ok:true,route:'{route}',hash:location.hash}};
  }} catch(e) {{
    return {{ok:false,route:'{route}',err:String(e).slice(0,120)}};
  }}
}})()"""
    return ev(ws_url, expr, timeout=10)


def main():
    ws, start_url = get_ws()
    if not ws:
        print("No target zhjg page found.")
        return

    report = {"start_url": start_url, "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": []}
    report["baseline"] = snapshot(ws)

    for r in ROUTES:
        item = {"route": r}
        item["push_result"] = push_route(ws, r)
        time.sleep(2)
        item["after"] = snapshot(ws)
        report["results"].append(item)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

