#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从当前 core flow 页面出发，按页面按钮逐步推进到 basic-info，再执行模拟填表+保存草稿。
不询问用户，自动连续执行并输出结果。
"""

import json
import subprocess
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/progress_core_flow_then_save.json")


def get_core_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/" in p.get("url", ""):
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
  var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;})
    .map(function(b){return {text:(b.textContent||'').trim().slice(0,40),disabled:!!b.disabled,cls:(b.className||'').slice(0,50)};});
  var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
  return {href:location.href,hash:location.hash,title:document.title,forms:document.querySelectorAll('.el-form-item').length,buttons:btns.slice(0,20),errors:errs.slice(0,10)};
})()""",
        timeout=12,
    )


def click_priority(ws_url: str):
    # 优先“继续申报” > “下一步” > “保存并下一步”
    return ev(
        ws_url,
        r"""(function(){
  var priorities=['继续申报','下一步','保存并下一步'];
  var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;});
  for(var p=0;p<priorities.length;p++){
    for(var i=0;i<btns.length;i++){
      var t=(btns[i].textContent||'').trim();
      if(t.indexOf(priorities[p])>=0 && !btns[i].disabled){
        btns[i].click();
        return {clicked:true,text:t,priority:priorities[p]};
      }
    }
  }
  return {clicked:false};
})()""",
        timeout=10,
    )


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = get_core_ws()
    if not ws:
        rec["error"] = "no_core_flow_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["start_url"] = url

    # 最多推进 8 轮
    for i in range(8):
        s = snap(ws)
        rec["steps"].append({"step": f"snap_{i}", "data": s})
        h = s.get("hash", "")
        if "#/flow/base/basic-info" in h:
            rec["reached_basic_info"] = True
            break
        c = click_priority(ws)
        rec["steps"].append({"step": f"click_{i}", "data": c})
        time.sleep(3)
    else:
        rec["reached_basic_info"] = False

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")

    # 若已到 basic-info，执行保存脚本
    if rec.get("reached_basic_info"):
        cmd = ["python", "-u", "G:/UFO/政务平台/system/run_mock_fill_and_save.py"]
        p = subprocess.run(cmd, capture_output=True, text=True)
        save_out = Path("G:/UFO/政务平台/data/progress_core_flow_then_save_output.txt")
        save_out.write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8")
        print(f"Saved: {save_out}")


if __name__ == "__main__":
    main()

