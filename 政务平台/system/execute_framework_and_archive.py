#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT_JSON = Path("G:/UFO/政务平台/data/framework_execution_record_02_4.json")

URL_ENTERPRISE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y"
URL_DECL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=1100&busiType=02_4"
URL_GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=25000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def snap(ws_url, tag):
    return {
        "tag": tag,
        "time": time.strftime("%H:%M:%S"),
        "data": ev(
            ws_url,
            r"""(function(){
              var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
              var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;})
                .map(function(b){return {text:(b.textContent||'').trim(),disabled:!!b.disabled};});
              return {href:location.href,hash:location.hash,title:document.title,errors:errs.slice(0,10),buttons:btns.slice(0,15)};
            })()""",
        ),
    }


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    if not ws:
        rec["error"] = "no_zhjg_page"
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT_JSON}")
        return

    rec["steps"].append({"step": "S0_start", "data": {"url": cur}})

    # 1) enterprise-zone
    rec["steps"].append({"step": "S1_open_enterprise_zone", "data": ev(ws, f"location.href='{URL_ENTERPRISE}'", timeout=15000)})
    time.sleep(7)
    ws, _ = pick_ws()
    rec["steps"].append({"step": "S2_enterprise_snapshot", **snap(ws, "enterprise-zone")})
    rec["steps"].append(
        {
            "step": "S3_click_start",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').includes('开始办理'));
                  if(b){b.click(); return {clicked:true,text:(b.textContent||'').trim()};}
                  return {clicked:false};
                })()""",
            ),
        }
    )
    time.sleep(4)

    # 2) declaration-instructions
    rec["steps"].append({"step": "S4_open_declaration", "data": ev(ws, f"location.href='{URL_DECL}'", timeout=15000)})
    time.sleep(7)
    ws, _ = pick_ws()
    rec["steps"].append({"step": "S5_declaration_snapshot", **snap(ws, "declaration-instructions")})
    rec["steps"].append(
        {
            "step": "S6_click_agree",
            "data": ev(
                ws,
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null);
                  for(var i=0;i<btns.length;i++){
                    var t=(btns[i].textContent||'').trim();
                    if(t.includes('我已阅读并同意')){
                      if(!btns[i].disabled){btns[i].click(); return {clicked:true,text:t};}
                      return {clicked:false,text:t,reason:'disabled'};
                    }
                  }
                  return {clicked:false,reason:'not_found'};
                })()""",
            ),
        }
    )
    time.sleep(3)

    # 3) guide/base
    rec["steps"].append({"step": "S7_open_guide_base", "data": ev(ws, f"location.href='{URL_GUIDE}'", timeout=15000)})
    time.sleep(7)
    ws, _ = pick_ws()
    rec["steps"].append({"step": "S8_guide_snapshot", **snap(ws, "guide-base")})
    rec["steps"].append(
        {
            "step": "S9_click_next",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').includes('下一步'));
                  if(b){ if(!b.disabled){b.click(); return {clicked:true,text:(b.textContent||'').trim()};}
                    return {clicked:false,text:(b.textContent||'').trim(),reason:'disabled'};}
                  return {clicked:false,reason:'not_found'};
                })()""",
            ),
        }
    )
    time.sleep(5)
    rec["steps"].append({"step": "S10_final_snapshot", **snap(ws, "after-guide-next")})

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT_JSON}")


if __name__ == "__main__":
    main()

