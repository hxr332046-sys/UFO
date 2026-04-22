#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 enterprise-zone 点击“开始办理”，定位下一步框架。"""

import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/entry_to_guide_survey.json")


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
            return m.get("result", {}).get("result", {}).get("value")


def snap(ws_url: str):
    return ev(
        ws_url,
        r"""(function(){
  var names=[];
  function walk(vm,d){ if(!vm||d>8) return; var n=(vm.$options&&vm.$options.name)||''; if(n) names.push(n); (vm.$children||[]).forEach(function(c){walk(c,d+1);}); }
  var app=document.getElementById('app'); if(app&&app.__vue__) walk(app.__vue__,0);
  return {
    href:location.href,
    hash:location.hash,
    title:document.title,
    forms:document.querySelectorAll('.el-form-item').length,
    compNames:Array.from(new Set(names)).slice(0,30),
    buttons:Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;}).map(function(b){return {text:(b.textContent||'').trim(),disabled:!!b.disabled};}).slice(0,20)
  };
})()""",
        timeout=12,
    )


def click_start(ws_url: str):
    return ev(
        ws_url,
        r"""(function(){
  var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;});
  for(var i=0;i<btns.length;i++){
    var t=(btns[i].textContent||'').trim();
    if(t.indexOf('开始办理')>=0){
      btns[i].click();
      return {clicked:true,text:t,index:i};
    }
  }
  return {clicked:false};
})()""",
        timeout=10,
    )


def main():
    ws, url = get_ws()
    if not ws:
        print("No target zhjg page.")
        return
    result = {"initial_url": url, "steps": []}
    s1 = snap(ws)
    result["steps"].append({"step": "before_click", "data": s1})
    print("before:", s1.get("hash"), s1.get("buttons"))

    c = click_start(ws)
    result["steps"].append({"step": "click_start", "data": c})
    print("click:", c)
    time.sleep(4)

    s2 = snap(ws)
    result["steps"].append({"step": "after_click", "data": s2})
    print("after:", s2.get("hash"), s2.get("compNames")[:10])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

