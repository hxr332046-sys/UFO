#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/remove_extra_member_and_next_02_4.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=40000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = pick_ws()
    rec["steps"].append({"step": "S1_start", "data": url})
    if not ws:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append(
        {
            "step": "S2_try_delete_extra",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null && (x.textContent||'').indexOf('删除')>=0 && !x.disabled);
                  if(!b) return {clicked:false};
                  b.click();
                  return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(1)

    rec["steps"].append(
        {
            "step": "S3_confirm_delete_if_any",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null && /确 定|确定/.test((x.textContent||'')) && !x.disabled);
                  if(!b) return {clicked:false};
                  b.click(); return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(2)

    rec["steps"].append(
        {
            "step": "S4_click_save_next",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null && (x.textContent||'').indexOf('保存并下一步')>=0 && !x.disabled);
                  if(!b) return {clicked:false};
                  b.click(); return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(8)

    rec["steps"].append(
        {
            "step": "S5_after",
            "data": ev(
                ws,
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled}));
                  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  return {href:location.href,hash:location.hash,buttons:btns.slice(0,20),errors:errs.slice(0,10)};
                })()""",
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

