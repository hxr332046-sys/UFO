#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从办件进度列表进入「继续办理」草稿，再多次「上一步」探索流程（不点云提交）。

比从门户重走 name-register/guide/base 更高效：直接续办已有「填写中」办件。

用法（在 政务平台 根目录）:
  .\\.venv-portal\\Scripts\\python.exe system\\cdp_resume_draft_explore.py
  .\\.venv-portal\\Scripts\\python.exe system\\cdp_resume_draft_explore.py --name-substr 食品市 --max-back 15

前置: Chrome Dev CDP 已开、已登录 9087；本脚本会导航到 portal 办件进度 hash。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_entry import ensure_icpsp_entry  # noqa: E402
from human_pacing import configure_human_pacing, sleep_human  # noqa: E402

OUT = ROOT / "dashboard" / "data" / "records" / "cdp_resume_draft_explore_latest.json"
PROGRESS_HASH = "#/company/my-space/selecthandle-progress"

CLICK_CONTINUE_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  function isVis(el){return !!(el && el.offsetParent!==null&&!el.disabled);}
  var SUB = __SUB__;
  var rows=[].slice.call(document.querySelectorAll(
    '.el-table__body-wrapper tbody tr,.el-table__body tbody tr,tbody tr.el-table__row,tr.el-table__row,.el-table__row,tbody tr'
  )).filter(function(el){
    if(!isVis(el)) return false;
    var t=clean(el.innerText||'');
    return t.length>5;
  });
  var chosen=null, reason='';
  for(var i=0;i<rows.length;i++){
    var t=clean(rows[i].innerText||'');
    if(t.indexOf('继续办理')<0) continue;
    if(SUB && t.indexOf(SUB)<0) continue;
    if(t.indexOf('企业开办')>=0 || t.indexOf('设立')>=0 || SUB){ chosen=rows[i]; reason='matched'; break; }
  }
  if(!chosen){
    for(var j=0;j<rows.length;j++){
      var t2=clean(rows[j].innerText||'');
      if(t2.indexOf('继续办理')>=0){ chosen=rows[j]; reason='fallback_first_continue'; break; }
    }
  }
  if(!chosen) return {ok:false,msg:'no_row_with_continue',rowCount:rows.length,debugRows:rows.slice(0,5).map(function(r){return clean(r.innerText||'').slice(0,120);})};
  var btn=[].slice.call(chosen.querySelectorAll('button,.el-button,a,span')).find(function(x){
    return isVis(x)&&clean(x.textContent).indexOf('继续办理')>=0;
  });
  if(!btn) return {ok:false,msg:'no_continue_btn',rowText:clean(chosen.innerText||'').slice(0,400)};
  btn.click();
  return {ok:true,reason:reason,rowText:clean(chosen.innerText||'').slice(0,400)};
})()"""

CLICK_PREV_STEP_JS = r"""(function(){
  var labels=['上一步','返回上一步','保存并上一步','上页','返回'];
  function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
  var els=[...document.querySelectorAll('button,.el-button,a')].filter(function(e){return e.offsetParent&&!e.disabled;});
  for(var li=0;li<labels.length;li++){
    var kw=labels[li];
    var hit=els.find(function(b){
      var t=clean(b.textContent);
      return t===kw || (t.indexOf(kw)>=0 && t.length<=32);
    });
    if(hit){ hit.click(); return {ok:true,kw:kw}; }
  }
  return {ok:false};
})()"""

PROBE_PAGE_JS = r"""(function(){
  var t=(document.body&&document.body.innerText)||'';
  var btns=[...document.querySelectorAll('button,.el-button')].filter(function(b){return b.offsetParent&&!b.disabled;})
    .map(function(b){return (b.textContent||'').replace(/\s+/g,' ').trim();}).filter(Boolean).slice(0,40);
  return {
    href:location.href,
    hash:location.hash,
    title:(document.title||'').slice(0,80),
    hasYunSubmit: /云提交|云端提交/.test(t),
    hasCore: location.href.indexOf('core.html')>=0,
    snippet:t.replace(/\s+/g,' ').trim().slice(0,900),
    buttons:btns
  };
})()"""


def _cdp_port() -> int:
    with (ROOT / "config" / "browser.json").open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def cdp_eval(ws: websocket.WebSocket, expr: str, msg_id: int, timeout_ms: int = 60000) -> Any:
    ws.send(
        json.dumps(
            {
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expr,
                    "returnByValue": True,
                    "awaitPromise": True,
                    "timeout": timeout_ms,
                },
            }
        )
    )
    end = time.time() + max(30.0, timeout_ms / 1000.0 + 15)
    while time.time() < end:
        try:
            msg = json.loads(ws.recv())
        except Exception:
            continue
        if msg.get("id") == msg_id:
            return ((msg.get("result") or {}).get("result") or {}).get("value")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--name-substr",
        default="",
        help="表格行 innerText 须包含该子串才点「继续办理」；空则优先「企业开办/设立」行否则首条含继续办理",
    )
    ap.add_argument("--max-back", type=int, default=12, help="最多点击「上一步」类按钮次数")
    ap.add_argument("-o", "--output", type=Path, default=OUT)
    ap.add_argument("--human-fast", action="store_true", help="关闭类人节奏（与 packet_chain 一致）")
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=args.human_fast)

    substr_js = json.dumps((args.name_substr or "").strip(), ensure_ascii=False)
    continue_js = CLICK_CONTINUE_JS.replace("__SUB__", substr_js)

    rec: Dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "name_substr": (args.name_substr or "").strip(),
        "max_back": int(args.max_back),
        "human_pacing": {"config": "config/human_pacing.json", "fast": bool(args.human_fast)},
        "steps": [],
    }
    port = _cdp_port()
    nav = ensure_icpsp_entry(port, busi_type="02_4", navigate_policy="host_only", wait_after_nav_sec=2.0)
    rec["steps"].append({"step": "ensure_icpsp_entry", "data": nav})
    ws_url = nav.get("ws_url")
    if not ws_url:
        rec["error"] = "no_ws"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ERROR: no CDP tab", rec)
        return 2

    ws = websocket.create_connection(ws_url, timeout=25)
    try:
        mid = 100
        goto = (
            "(async function(){"
            "try{var app=document.getElementById('app');"
            "if(app&&app.__vue__&&app.__vue__.$router){"
            "await app.__vue__.$router.push('/company/my-space/selecthandle-progress');"
            "await new Promise(function(r){setTimeout(r,2000);});"
            "return {ok:true,mode:'router',href:location.href,hash:location.hash};}"
            "}catch(e){}"
            f"location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html{PROGRESS_HASH}';"
            "await new Promise(function(r){setTimeout(r,2200);});"
            "return {ok:true,mode:'href',href:location.href,hash:location.hash};"
            "})()"
        )
        rec["steps"].append({"step": "goto_selecthandle_progress", "data": cdp_eval(ws, goto, mid, 45000)})
        mid += 1
        for wait_i in range(15):
            sleep_human(1.05)
            nrow = cdp_eval(
                ws,
                r"""(function(){
                  return {
                    n1:document.querySelectorAll('.el-table__body-wrapper tbody tr').length,
                    n2:document.querySelectorAll('.el-table__body tbody tr').length,
                    n3:document.querySelectorAll('tbody tr').length
                  };
                })()""",
                mid,
                15000,
            )
            mid += 1
            rec["steps"].append({"step": f"wait_table_{wait_i}", "data": nrow})
            if isinstance(nrow, dict) and (int(nrow.get("n1") or 0) + int(nrow.get("n2") or 0) + int(nrow.get("n3") or 0)) > 0:
                break
        sleep_human(1.0)
        rec["steps"].append({"step": "probe_before_continue", "data": cdp_eval(ws, PROBE_PAGE_JS, mid, 25000)})
        mid += 1

        rec["steps"].append({"step": "click_continue", "data": cdp_eval(ws, continue_js, mid, 90000)})
        mid += 1
        sleep_human(4.2)
        rec["steps"].append({"step": "after_continue", "data": cdp_eval(ws, PROBE_PAGE_JS, mid, 25000)})
        mid += 1

        last_href = ""
        same = 0
        for i in range(max(0, args.max_back)):
            pr = cdp_eval(ws, PROBE_PAGE_JS, mid, 25000)
            mid += 1
            rec["steps"].append({"step": f"probe_back_{i}", "data": pr})
            if isinstance(pr, dict) and pr.get("hasYunSubmit"):
                rec["steps"].append({"step": "stop_near_yun_submit", "note": "检测到云提交类文案，停止回退以免误操作"})
                break
            bk = cdp_eval(ws, CLICK_PREV_STEP_JS, mid, 20000)
            mid += 1
            rec["steps"].append({"step": f"click_prev_{i}", "data": bk})
            sleep_human(2.2)
            if not isinstance(bk, dict) or not bk.get("ok"):
                rec["steps"].append({"step": "prev_exhausted", "data": {"at": i}})
                break
            href = (pr or {}).get("href") if isinstance(pr, dict) else ""
            if href == last_href:
                same += 1
            else:
                same = 0
                last_href = href
            if same >= 2:
                rec["steps"].append({"step": "href_stagnate_stop", "data": {"at": i}})
                break
    finally:
        try:
            ws.close()
        except Exception:
            pass

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
