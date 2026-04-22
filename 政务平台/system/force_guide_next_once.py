#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/force_guide_next_once.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or "") and "icpsp-web-pc" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": [{"step": "pick", "data": {"url": cur}}]}
    if not ws_url:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=20000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    def snap(tag):
        return ev(
            r"""(function(){
              var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled,cls:(b.className||'').slice(0,50)}));
              var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              return {tag:%s,href:location.href,hash:location.hash,btns:btns.slice(0,10),errs:errs.slice(0,8)};
            })()""" % json.dumps(tag, ensure_ascii=False),
            20000,
        )

    rec["steps"].append({"step": "state_before", "data": snap("before")})
    # click any visible 确定
    rec["steps"].append(
        {
            "step": "click_ok",
            "data": ev(
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null);
                  var ok=btns.find(b=>((b.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!b.disabled);
                  if(ok){ok.click();return {clicked:true,cls:(ok.className||'').slice(0,60)};}
                  return {clicked:false};
                })()"""
            ),
        }
    )
    time.sleep(1)
    # click next if enabled
    rec["steps"].append(
        {
            "step": "click_next",
            "data": ev(
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null);
                  var n=btns.find(b=>((b.textContent||'').replace(/\s+/g,' ').trim())==='下一步');
                  if(n && !n.disabled){n.click();return {clicked:true};}
                  return {clicked:false,disabled:!!(n&&n.disabled),cls:(n&&n.className||'').slice(0,60)};
                })()"""
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "state_after", "data": snap("after")})

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

