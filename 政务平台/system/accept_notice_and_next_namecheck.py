#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/accept_notice_and_next_namecheck.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=18)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["steps"].append({"step": "before", "data": ev(ws, r"""(function(){var txt=(document.body.innerText||'');var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {hash:location.hash,errors:errs.slice(0,10),hasNotice:txt.indexOf('请阅读《名称登记自主申报须知》并勾选')>=0};})()""")})
    rec["steps"].append(
        {
            "step": "accept_and_next",
            "data": ev(
                ws,
                r"""(function(){
                  var act=[];
                  function clickByContains(t){
                    var els=[...document.querySelectorAll('button,.el-button,label,span,div,a,li')].filter(x=>x.offsetParent!==null);
                    for(var e of els){
                      var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx.indexOf(t)>=0){
                        e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                        return tx;
                      }
                    }
                    return '';
                  }
                  var agree = clickByContains('我已阅读并同意');
                  if(agree) act.push('click_agree');
                  var ok = clickByContains('确定');
                  if(ok) act.push('click_ok');
                  var save = clickByContains('保存并下一步');
                  if(save) act.push('click_save');
                  return {actions:act};
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "after", "data": ev(ws, r"""(function(){var txt=(document.body.innerText||'');var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasNotice:txt.indexOf('请阅读《名称登记自主申报须知》并勾选')>=0,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

