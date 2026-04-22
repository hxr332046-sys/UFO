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
OUT_MD = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round3_to_yunbangban.md")


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
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def snap(ws):
    return ev(
        ws,
        r"""(function(){
          return {
            href:location.href, hash:location.hash,
            text:(document.body.innerText||'').slice(0,1200),
            errors:[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean).slice(0,10),
            buttons:[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled})).slice(0,20)
          };
        })()""",
    )


def is_yunbangban(s):
    return "云帮办流程模式选择" in (s.get("text") or "")


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def main():
    main_rec = load_json(OUT_MAIN, {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []})
    err_rec = load_json(OUT_ERR, {"started_at": main_rec.get("started_at", time.strftime("%Y-%m-%d %H:%M:%S")), "items": []})

    ws, url = pick_ws("name-register.html#/guide/base")
    if not ws:
        ws, url = pick_ws()
    main_rec["steps"].append({"step": "S10_recover_start", "data": {"url": url}})

    # Record root cause from previous round
    err_rec["items"].append(
        {
            "stage": "guide/base",
            "error": "流程停留在 guide/base，出现“请选择是否需要名称”提示，未进入 core 节点",
            "fix": "选择“未申请”并处理“确定”提示后重试下一步",
            "result": "in_progress",
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    for i in range(12):
        s = snap(ws)
        main_rec["steps"].append({"step": f"S11_loop_{i}", "data": s})
        if is_yunbangban(s):
            main_rec["result"] = "stopped_at_yunbangban"
            main_rec["final_url"] = s.get("href")
            main_rec["final_hash"] = s.get("hash")
            OUT_STOP.write_text(
                json.dumps({"captured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "url": s.get("href"), "snapshot": s}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            err_rec["items"][-1]["result"] = "fixed_reached_yunbangban"
            break

        # recovery actions priority
        ev(
            ws,
            r"""(function(){
              function clickByText(t){
                var b=[...document.querySelectorAll('button,.el-button,label,span,div,a,li')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf(t.replace(/\s+/g,''))>=0));
                if(b){ b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return true; }
                return false;
              }
              if(clickByText('未申请')) return 'clicked_未申请';
              if(clickByText('确定')) return 'clicked_确定';
              if(clickByText('关 闭')) return 'clicked_关闭';
              if(clickByText('下一步')) return 'clicked_下一步';
              return 'no_action';
            })()""",
        )
        time.sleep(3)

    if main_rec.get("result") != "stopped_at_yunbangban":
        err_rec["items"][-1]["result"] = "not_fixed_still_not_reached"
        err_rec["items"][-1]["note"] = "多轮恢复后仍未到云帮办节点，保留现场供下一轮人工确认"

    main_rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_MAIN.write_text(json.dumps(main_rec, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_ERR.write_text(json.dumps(err_rec, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 02_4 Round3 到云帮办节点",
        "",
        f"- ended_at: {main_rec.get('ended_at','')}",
        f"- result: {main_rec.get('result','')}",
        f"- final_hash: {main_rec.get('final_hash','')}",
        "",
        "## 错误修复",
        f"- latest_fix_result: {err_rec.get('items', [])[-1].get('result','') if err_rec.get('items') else ''}",
        "",
        "## 证据",
        f"- {OUT_MAIN.as_posix()}",
        f"- {OUT_ERR.as_posix()}",
        f"- {OUT_STOP.as_posix()}",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Updated: {OUT_MAIN}")
    print(f"Updated: {OUT_ERR}")
    print(f"Updated: {OUT_STOP}")
    print(f"Updated: {OUT_MD}")


if __name__ == "__main__":
    main()

