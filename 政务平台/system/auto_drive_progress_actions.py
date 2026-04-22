#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP 一键触发办件相关动作：
1) 自动连接已登录的 9087 政务页签
2) 跳到办件进度列表
3) 依次点击：办件进度 / 通知书 / 承诺书（命中则点）
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import websocket

from icpsp_entry import ensure_icpsp_entry

OUT = Path("G:/UFO/政务平台/dashboard/data/records/auto_drive_progress_actions.json")


def cdp_eval(ws: websocket.WebSocket, expression: str, msg_id: int = 1, timeout_ms: int = 20000) -> Any:
    ws.send(
        json.dumps(
            {
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                    "timeout": timeout_ms,
                },
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == msg_id:
            return msg.get("result", {}).get("result", {}).get("value")


def click_one(ws: websocket.WebSocket, keyword: str, msg_id: int) -> Dict[str, Any]:
    js = f"""(async function(){{
      function tx(e){{ return ((e && e.textContent) || '').replace(/\\s+/g,' ').trim(); }}
      function visible(e){{
        if(!e) return false;
        var st = window.getComputedStyle(e);
        return e.offsetParent !== null && st.visibility !== 'hidden' && st.display !== 'none';
      }}
      var cands = Array.from(document.querySelectorAll('button,a,.el-button,[role="button"],span,div'))
        .filter(function(e){{
          if(!visible(e)) return false;
          var t = tx(e);
          return t.indexOf({json.dumps(keyword, ensure_ascii=False)}) >= 0;
        }});
      if(!cands.length) return {{ok:false, keyword:{json.dumps(keyword, ensure_ascii=False)}, reason:'not_found'}};
      var node = cands[0];
      var text = tx(node).slice(0,120);
      try {{
        node.scrollIntoView({{block:'center', inline:'center'}});
      }} catch(_e) {{}}
      await new Promise(function(r){{setTimeout(r, 150);}});
      node.click();
      await new Promise(function(r){{setTimeout(r, 1200);}});
      return {{
        ok:true,
        keyword:{json.dumps(keyword, ensure_ascii=False)},
        clicked_text:text,
        href:location.href,
        hash:location.hash,
        title:document.title
      }};
    }})()"""
    return cdp_eval(ws, js, msg_id=msg_id, timeout_ms=45000) or {"ok": False, "keyword": keyword, "reason": "empty_result"}


def main() -> None:
    rec: Dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    try:
        nav = ensure_icpsp_entry(9225, busi_type="02_4", navigate_policy="host_only", wait_after_nav_sec=2.0)
        rec["steps"].append({"step": "ensure_icpsp_entry", "data": nav})
        if not nav.get("ok") or not nav.get("ws_url"):
            rec["error"] = "no_cdp_target"
            return

        ws_url: Optional[str] = nav.get("ws_url")
        ws = websocket.create_connection(ws_url, timeout=12)
        try:
            route_res = cdp_eval(
                ws,
                """(async function(){
                  try{
                    var app=document.getElementById('app');
                    if(app && app.__vue__ && app.__vue__.$router){
                      await app.__vue__.$router.push('/company/my-space/selecthandle-progress');
                      await new Promise(function(r){setTimeout(r, 1800);});
                      return {ok:true, mode:'router', href:location.href, hash:location.hash};
                    }
                  }catch(e){}
                  location.hash = '#/company/my-space/selecthandle-progress';
                  await new Promise(function(r){setTimeout(r, 1800);});
                  return {ok:true, mode:'hash', href:location.href, hash:location.hash};
                })()""",
                msg_id=11,
                timeout_ms=45000,
            )
            rec["steps"].append({"step": "goto_selecthandle_progress", "data": route_res})
            page_probe = cdp_eval(
                ws,
                """(function(){
                  function tx(e){ return ((e && e.textContent) || '').replace(/\\s+/g,' ').trim(); }
                  var rows = document.querySelectorAll('.el-table__body tr').length;
                  var empty = document.querySelector('.el-table__empty-text');
                  var clicks = Array.from(document.querySelectorAll('button,a,.el-button,[role="button"]'))
                    .filter(function(e){ return e.offsetParent!==null; })
                    .map(function(e){ return tx(e); })
                    .filter(Boolean)
                    .slice(0, 80);
                  return {
                    href: location.href,
                    hash: location.hash,
                    title: document.title,
                    row_count: rows,
                    empty_text: empty ? tx(empty) : null,
                    clickable_texts_top: clicks
                  };
                })()""",
                msg_id=15,
                timeout_ms=20000,
            )
            rec["steps"].append({"step": "page_probe", "data": page_probe})

            for idx, kw in enumerate(["办件进度", "通知书", "承诺书"], start=1):
                res = click_one(ws, kw, msg_id=20 + idx)
                rec["steps"].append({"step": f"click_{kw}", "data": res})
        finally:
            try:
                ws.close()
            except Exception:
                pass
    except Exception as e:
        rec["error"] = str(e)
    finally:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(OUT))
        print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
