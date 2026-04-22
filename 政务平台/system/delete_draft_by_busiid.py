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

OUT = Path("G:/UFO/政务平台/dashboard/data/records/delete_draft_by_busiid_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
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
                result = m.get("result") or {}
                if "exceptionDetails" in result:
                    return {"ok": False, "exception": result["exceptionDetails"]}
                return (result.get("result") or {}).get("value")
    finally:
        ws.close()
    return None


def build_js(busi_id: str, keyword: str) -> str:
    bid = json.dumps(busi_id, ensure_ascii=False)
    kw = json.dumps(keyword, ensure_ascii=False)
    return rf"""(async function(){{
  function clean(s){{ return String(s||'').replace(/\s+/g,' ').trim(); }}
  var busiId={bid}, kw={kw};
  var url='/icpsp-api/v4/pc/manager/mattermanager/matters/operate?t='+Date.now();
  if(location.href.indexOf('my-space/space-index')<0){{
    location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/company/my-space/space-index';
    await new Promise(r=>setTimeout(r,3200));
  }}
  var before=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'include',body:JSON.stringify({{busiId:busiId,btnCode:'103',dealFlag:'before'}})}}).then(r=>r.text());
  await new Promise(r=>setTimeout(r,700));
  var after=await fetch('/icpsp-api/v4/pc/manager/mattermanager/matters/operate?t='+(Date.now()+1),{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'include',body:JSON.stringify({{busiId:busiId,btnCode:'103',dealFlag:'after'}})}}).then(r=>r.text());
  await new Promise(r=>setTimeout(r,1200));
  location.reload();
  await new Promise(r=>setTimeout(r,2600));
  var rows=[...document.querySelectorAll('tbody tr,.el-table__row')].filter(r=>r.offsetParent!==null).map(r=>clean(r.innerText||''));
  var still=rows.some(t=>t.indexOf(kw)>=0 && t.indexOf('填写中')>=0);
  return {{ok:!still,busiId:busiId,keyword:kw,still:still,before:before.slice(0,500),after:after.slice(0,500),rows:rows.slice(0,5)}};
}})()"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--busi-id", required=True)
    parser.add_argument("--keyword", required=True)
    args = parser.parse_args()
    rec: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "busi_id": args.busi_id,
        "keyword": args.keyword,
    }
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_9087_tab"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["result"] = ev(ws, build_js(args.busi_id, args.keyword), 120000)
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

