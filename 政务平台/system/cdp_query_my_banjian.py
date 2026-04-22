#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CDP：打开门户「办件进度」列表，抓取表格行摘要，并可检测案例企业名是否出现。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_entry import pick_icpsp_target_prefer_logged_portal  # noqa: E402

HOST = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
PROGRESS = f"{HOST}#/company/my-space/selecthandle-progress"
SPACE_INDEX = f"{HOST}#/company/my-space/space-index"

OUT_JSON = ROOT / "dashboard" / "data" / "records" / "cdp_my_space_query_latest.json"

SCRAPE_ROWS_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  function rowTexts(){
    var sel=['.el-table__body-wrapper tbody tr','.el-table__body tbody tr','tbody tr.el-table__row'];
    var seen=new Set(); var rows=[];
    for(var si=0;si<sel.length;si++){
      var nodes=document.querySelectorAll(sel[si]);
      for(var i=0;i<nodes.length;i++){
        var el=nodes[i];
        if(!el.offsetParent) continue;
        var t=clean(el.innerText||'');
        if(t.length<3) continue;
        if(seen.has(t)) continue;
        seen.add(t);
        rows.push(t.slice(0,500));
      }
    }
    return rows;
  }
  var body=(document.body&&document.body.innerText)||'';
  return {
    href:location.href,
    hash:location.hash,
    title:(document.title||'').slice(0,120),
    rowCount:rowTexts().length,
    rows:rowTexts().slice(0,40),
    bodySample:clean(body).slice(0,3500),
    hasLoginBar:/登录\s*\/\s*注册/.test(body.slice(0,900)),
    hasBanjiCenter:body.indexOf('办件中心')>=0
  };
})()"""

NAV_WAIT_JS = (
    "(async function(){"
    f"location.href={json.dumps(PROGRESS, ensure_ascii=False)};"
    "await new Promise(function(r){setTimeout(r,3500);});"
    "return {href:location.href,hash:location.hash};"
    "})()"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=Path, default=ROOT / "docs" / "case_广西容县李陈梦.json")
    ap.add_argument("--port", type=int, default=9225)
    ap.add_argument("--also-space-index", action="store_true", help="再打开 space-index 抓一份摘要")
    args = ap.parse_args()

    needle = ""
    if args.case.is_file():
        try:
            case = json.loads(args.case.read_text(encoding="utf-8"))
            needle = str(case.get("company_name_full") or "").strip()
        except Exception:
            pass

    rec: Dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "needle_company_name_full": needle,
        "steps": [],
    }

    best, debug = pick_icpsp_target_prefer_logged_portal(args.port)
    rec["tab_pick_debug"] = debug
    ws_url = best.get("webSocketDebuggerUrl") if isinstance(best, dict) else None
    rec["picked_tab_url"] = best.get("url") if isinstance(best, dict) else None

    if not ws_url:
        rec["error"] = "no_cdp_icpsp_tab"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 2

    ws = websocket.create_connection(ws_url, timeout=25)
    try:

        def ev(expr: str, timeout_ms: int = 45000) -> Any:
            ws.send(
                json.dumps(
                    {
                        "id": 1,
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
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == 1:
                    return ((msg.get("result") or {}).get("result") or {}).get("value")

        rec["steps"].append({"step": "before_nav", "data": ev(SCRAPE_ROWS_JS, 15000)})
        rec["steps"].append({"step": "goto_progress", "data": ev(NAV_WAIT_JS, 60000)})
        time.sleep(1.5)
        scrape = ev(SCRAPE_ROWS_JS, 20000)
        rec["steps"].append({"step": "after_progress_scrape", "data": scrape})

        if args.also_space_index:
            ev(
                "(async function(){"
                f"location.href={json.dumps(SPACE_INDEX, ensure_ascii=False)};"
                "await new Promise(function(r){setTimeout(r,3000);});"
                "return {href:location.href};"
                "})()",
                55000,
            )
            time.sleep(1.0)
            rec["steps"].append({"step": "after_space_index_scrape", "data": ev(SCRAPE_ROWS_JS, 20000)})

        body_sample = ""
        rows: list = []
        if isinstance(scrape, dict):
            body_sample = str(scrape.get("bodySample") or "")
            rows = scrape.get("rows") or []

        match_needle = bool(needle) and (
            any(needle in r for r in rows) or (needle in body_sample)
        )
        rec["match"] = {
            "needle": needle,
            "found_in_rows_or_body": match_needle,
            "note": "办件列表未出现该企业名 ≠ 核名失败；新设草稿可能滞后或仍在名称阶段。",
        }
    finally:
        try:
            ws.close()
        except Exception:
            pass

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"Saved: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
