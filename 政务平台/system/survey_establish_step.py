#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在 establish 页面选择企业类型并 nextBtn，记录下一步框架。"""

import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/establish_step_survey.json")


def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "#/index/enterprise/establish" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
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
            return m.get("result", {}).get("result", {}).get("value")


def snap(ws_url: str):
    return ev(
        ws_url,
        r"""(function(){
  var app=document.getElementById('app');
  var names=[];
  function walk(vm,d){ if(!vm||d>8) return; var n=(vm.$options&&vm.$options.name)||''; if(n) names.push(n); (vm.$children||[]).forEach(function(c){walk(c,d+1);}); }
  if(app&&app.__vue__) walk(app.__vue__,0);
  return {
    href:location.href,hash:location.hash,forms:document.querySelectorAll('.el-form-item').length,
    compNames:Array.from(new Set(names)).slice(0,30),
    buttons:Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;}).map(function(b){return {text:(b.textContent||'').trim(),disabled:!!b.disabled};}).slice(0,20)
  };
})()""",
        timeout=12,
    )


def do_next(ws_url: str):
    return ev(
        ws_url,
        r"""(function(){
  var app=document.getElementById('app'); if(!app||!app.__vue__) return {ok:false,err:'no_vue'};
  function findComp(vm,name,d){ if(!vm||d>15) return null; if(vm.$options&&vm.$options.name===name) return vm; for(var i=0;i<(vm.$children||[]).length;i++){ var r=findComp(vm.$children[i],name,d+1); if(r) return r; } return null; }
  var est=findComp(app.__vue__,'establish',0);
  if(!est) return {ok:false,err:'no_establish'};
  // 按既有经验：radioGroup[0].checked='1100' 再 nextBtn
  if(est.$data && est.$data.radioGroup && est.$data.radioGroup.length){
    est.$set(est.$data.radioGroup[0],'checked','1100');
  }
  if(typeof est.nextBtn!=='function') return {ok:false,err:'no_nextBtn'};
  est.nextBtn();
  return {ok:true,called:'nextBtn'};
})()""",
        timeout=12,
    )


def main():
    ws, url = get_ws()
    if not ws:
        print("No target page.")
        return
    out = {"initial_url": url, "steps": []}
    s1 = snap(ws)
    out["steps"].append({"step": "before_nextBtn", "data": s1})
    print("before:", s1.get("hash"), s1.get("buttons"))

    r = do_next(ws)
    out["steps"].append({"step": "call_nextBtn", "data": r})
    print("call:", r)
    time.sleep(5)

    s2 = snap(ws)
    out["steps"].append({"step": "after_nextBtn", "data": s2})
    print("after:", s2.get("hash"), s2.get("compNames")[:10])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

