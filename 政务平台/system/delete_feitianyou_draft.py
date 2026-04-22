#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/delete_feitianyou_draft_latest.json")


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


DELETE_JS = r"""(async function(){
  function clean(s){ return String(s||'').replace(/\s+/g,' ').trim(); }
  if(location.href.indexOf('my-space/space-index')<0){
    location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/company/my-space/space-index';
    await new Promise(r=>setTimeout(r,3500));
  }
  var rows=[...document.querySelectorAll('tbody tr,.el-table__row')].filter(r=>r.offsetParent!==null);
  var row=rows.find(r=>{
    var t=clean(r.innerText||'');
    return t.indexOf('飞天有')>=0 && t.indexOf('个人独资')>=0 && t.indexOf('填写中')>=0;
  });
  if(!row) return {ok:true,msg:'already_removed'};
  // 先触发 before，拿到确认提示
  var delBtn=[...row.querySelectorAll('button,.el-button')].find(b=>b.offsetParent!==null&&clean(b.textContent||'')==='删除');
  if(!delBtn) return {ok:false,msg:'delete_button_not_found'};
  delBtn.click();
  await new Promise(r=>setTimeout(r,900));

  var busiId='2046220094765400064';
  try{
    // 二次确认（after）直接调用接口，避免前端确认框丢失
    var url='/icpsp-api/v4/pc/manager/mattermanager/matters/operate?t='+Date.now();
    var body=JSON.stringify({busiId:busiId,btnCode:'103',dealFlag:'after'});
    var rsp=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:body,credentials:'include'});
    var txt=await rsp.text();
    await new Promise(r=>setTimeout(r,1500));
    if(location.href.indexOf('my-space/space-index')>=0){ location.reload(); await new Promise(r=>setTimeout(r,2600)); }
    var still=[...document.querySelectorAll('tbody tr,.el-table__row')].some(r=>{
      var t=clean(r.innerText||'');
      return t.indexOf('飞天有')>=0 && t.indexOf('个人独资')>=0 && t.indexOf('填写中')>=0;
    });
    return {ok:!still,busiId:busiId,status:rsp.status,response:txt.slice(0,500),still:still};
  }catch(e){
    return {ok:false,msg:'after_call_failed',err:String(e),busiId:busiId};
  }
})()"""


def main() -> int:
    rec: dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_9087_tab"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["result"] = ev(ws, DELETE_JS, 120000)
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

