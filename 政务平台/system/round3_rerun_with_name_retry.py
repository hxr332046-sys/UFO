#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT_MAIN = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round3_to_yunbangban.json")
OUT_ERR = Path("G:/UFO/政务平台/dashboard/data/records/round3_error_fix_log.json")
OUT_STOP = Path("G:/UFO/政务平台/dashboard/data/records/round3_yunbangban_stop_evidence.json")

URL_ENTERPRISE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y"
URL_DECL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=1100&busiType=02_4"
URL_GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="
TARGET_NAME = "广西玉林桂柚百货中心（个人独资）"


def pick_ws(prefer=None):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    if prefer:
        for p in pages:
            if p.get("type") == "page" and prefer in p.get("url", ""):
                return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=50000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def snap(ws):
    return ev(
        ws,
        r"""(function(){
          return {
            href:location.href,hash:location.hash,
            text:(document.body.innerText||'').slice(0,1500),
            btns:[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled})).slice(0,20)
          };
        })()""",
    )


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "target_company_name": TARGET_NAME, "rerun_steps": []}
    err = {"started_at": rec["started_at"], "items": []}

    ws, _ = pick_ws()
    ev(ws, f"location.href='{URL_ENTERPRISE}'", timeout=15000)
    time.sleep(5)
    ws, _ = pick_ws("portal.html#/index/enterprise/enterprise-zone")
    ev(ws, "(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('开始办理')>=0&&!x.disabled); if(b){b.click();return true;} return false;})()")
    time.sleep(2)

    ev(ws, f"location.href='{URL_DECL}'", timeout=15000)
    time.sleep(5)
    ws, _ = pick_ws("name-register.html#/namenotice/declaration-instructions")
    ev(ws, "(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0&&!x.disabled); if(b){b.click();return true;} return false;})()")
    time.sleep(2)

    ev(ws, f"location.href='{URL_GUIDE}'", timeout=15000)
    time.sleep(6)
    ws, _ = pick_ws("name-register.html#/guide/base")

    for i in range(10):
        s = snap(ws)
        rec["rerun_steps"].append({"i": i, "snapshot": s})
        txt = s.get("text", "")
        if "云帮办流程模式选择" in txt:
            rec["result"] = "stopped_at_yunbangban"
            OUT_STOP.write_text(json.dumps({"captured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "url": s.get("href"), "snapshot": s}, ensure_ascii=False, indent=2), encoding="utf-8")
            break

        action = ev(
            ws,
            r"""(function(){
              function clickText(t){
                var els=[...document.querySelectorAll('button,.el-button,label,span,div,li,a')].filter(x=>x.offsetParent!==null);
                for(var e of els){
                  var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                  if(tx===t || tx.indexOf(t)>=0){
                    e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                    return true;
                  }
                }
                return false;
              }
              if(clickText('未申请')) return 'click_未申请';
              if(clickText('确定')) return 'click_确定';
              if(clickText('下一步')) return 'click_下一步';
              if(clickText('关 闭')) return 'click_关闭';
              return 'none';
            })()""",
        )
        rec["rerun_steps"][-1]["action"] = action
        if "请选择是否需要名称" in txt:
            err["items"].append(
                {
                    "stage": "guide/base",
                    "error": "请选择是否需要名称",
                    "fix_action": action,
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        time.sleep(3)

    rec.setdefault("result", "still_blocked_guide")
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_MAIN.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_ERR.write_text(json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT_MAIN}")
    print(f"Saved: {OUT_ERR}")
    if OUT_STOP.exists():
        print(f"Saved: {OUT_STOP}")


if __name__ == "__main__":
    main()

