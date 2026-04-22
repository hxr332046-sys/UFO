#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/delete_draft_by_keyword_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "my-space/space-index" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and ":9087" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 120000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.settimeout(2.0)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            }
        )
    )
    end = time.time() + 150
    try:
        while time.time() < end:
            try:
                m = json.loads(ws.recv())
            except Exception:
                continue
            if m.get("id") == 1:
                return ((m.get("result") or {}).get("result") or {}).get("value")
    finally:
        ws.close()
    return None


def build_delete_js(keyword: str) -> str:
    kw = json.dumps(keyword, ensure_ascii=False)
    return rf"""(async function(){{
  function clean(s){{ return String(s||'').replace(/\s+/g,' ').trim(); }}
  var kw={kw};
  if(location.href.indexOf('my-space/space-index')<0){{
    location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/company/my-space/space-index';
    await new Promise(r=>setTimeout(r,3500));
  }}
  function rows(){{ return [...document.querySelectorAll('tbody tr,.el-table__row')].filter(r=>r.offsetParent!==null); }}
  var row=rows().find(r=>{{ var t=clean(r.innerText||''); return t.indexOf(kw)>=0 && t.indexOf('填写中')>=0; }});
  if(!row) return {{ok:true,msg:'not_found',keyword:kw}};
  var beforeText=clean(row.innerText||'');
  var delBtn=[...row.querySelectorAll('button,.el-button')].find(b=>b.offsetParent!==null&&clean(b.textContent||'')==='删除');
  if(!delBtn) return {{ok:false,msg:'delete_button_not_found',row:beforeText}};
  delBtn.click();
  await new Promise(r=>setTimeout(r,1000));
  var dlgBtns=[...document.querySelectorAll('.el-message-box__wrapper button,.el-dialog__wrapper button,button,.el-button')].filter(b=>b.offsetParent!==null);
  var okBtn=dlgBtns.find(b=>{{ var t=clean(b.textContent||''); return t==='确定' || t==='是' || t==='继续' || t==='确认'; }});
  var clickedConfirm=false;
  if(okBtn){{ okBtn.click(); clickedConfirm=true; }}
  await new Promise(r=>setTimeout(r,2200));
  if(location.href.indexOf('my-space/space-index')>=0){{ location.reload(); await new Promise(r=>setTimeout(r,2600)); }}
  var still=rows().some(r=>{{ var t=clean(r.innerText||''); return t.indexOf(kw)>=0 && t.indexOf('填写中')>=0; }});
  return {{ok:!still,keyword:kw,beforeText:beforeText,clickedConfirm:clickedConfirm,still:still,href:location.href}};
}})()"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True, help="Row keyword in my-space, e.g. 陈飞李")
    args = parser.parse_args()

    rec: dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "keyword": args.keyword}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_9087_tab"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["result"] = ev(ws, build_delete_js(args.keyword), 120000)
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

