#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/click_namecheck_organization_option.json")


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
    rec["steps"].append({"step": "before", "data": ev(ws, r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {hash:location.hash,errors:errs};})()""")})
    rec["steps"].append(
        {
            "step": "click_org_and_save",
            "data": ev(
                ws,
                r"""(function(){
                  function text(n){return (n&&n.textContent||'').replace(/\s+/g,' ').trim();}
                  var items=[...document.querySelectorAll('.el-form-item')];
                  var target=null;
                  for(var it of items){
                    var lb=it.querySelector('.el-form-item__label');
                    if(lb && text(lb).indexOf('组织形式')>=0){ target=it; break; }
                  }
                  if(!target) return {ok:false,msg:'no_target_item'};
                  var clicked=[];
                  var candidates=[...target.querySelectorAll('label,span,div,.el-radio,.el-radio__label,.el-radio__input')].filter(x=>x.offsetParent!==null);
                  for(var c of candidates){
                    var t=text(c);
                    if(!t) continue;
                    c.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                    clicked.push(t);
                    if(clicked.length>=3) break;
                  }
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save) save.click();
                  return {ok:true,clicked:clicked};
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "after", "data": ev(ws, r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {hash:location.hash,errors:errs,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

