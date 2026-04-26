#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

try:
    import websocket  # type: ignore
except Exception:  # pragma: no cover
    websocket = None

CDP_JSON = "http://127.0.0.1:9225/json"


def _cdp_pages() -> list[dict[str, Any]]:
    with urllib.request.urlopen(CDP_JSON, timeout=3) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _pick_core_page() -> Tuple[Optional[str], Optional[str]]:
    pages = _cdp_pages()
    for page in pages:
        url = str(page.get("url") or "")
        if page.get("type") == "page" and "core.html#/flow/base/ybb-select" in url:
            return str(page.get("webSocketDebuggerUrl") or ""), url
    for page in pages:
        url = str(page.get("url") or "")
        if page.get("type") == "page" and "core.html#/" in url:
            return str(page.get("webSocketDebuggerUrl") or ""), url
    return None, None


def _call(ws: Any, method: str, params: Optional[dict[str, Any]] = None, msg_id: int = 1) -> dict[str, Any]:
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except Exception:
            continue
        if msg.get("id") == msg_id:
            return msg.get("result") or {}
    return {"_err": "timeout"}


def _eval(ws: Any, expr: str, msg_id: int, timeout_ms: int = 30000) -> Any:
    result = _call(
        ws,
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
        msg_id=msg_id,
    )
    if result.get("exceptionDetails"):
        return {"ok": False, "exception": str(result.get("exceptionDetails"))[:500]}
    return (result.get("result") or {}).get("value")


CLICK_YBB_GENERAL_AND_SAVE_JS = r"""
(async function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  function visible(e){
    if(!e) return false;
    var s=getComputedStyle(e);
    var r=e.getBoundingClientRect();
    return s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0;
  }
  function clickText(keys, selector){
    var els=[...document.querySelectorAll(selector||'button,.el-button,a,div,span,label')].filter(visible);
    for(var key of keys){
      var hits=[];
      for(var e of els){
        var t=clean(e.textContent||'');
        if(t && t.indexOf(key)>=0) hits.push({e:e,t:t});
      }
      hits.sort((a,b)=>a.t.length-b.t.length);
      if(hits.length){
        var node=hits[0].e.closest('button,.el-button,a,label')||hits[0].e;
        node.scrollIntoView({block:'center'});
        node.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
        return {ok:true,key:key,text:hits[0].t.slice(0,120)};
      }
    }
    return {ok:false,keys:keys};
  }
  var before={href:location.href,hash:location.hash,text:clean(document.body&&document.body.innerText||'').slice(0,260)};
  var general=clickText(['选择一般流程办理','一般流程办理','一般流程']);
  await new Promise(r=>setTimeout(r,600));
  var save=clickText(['保存并下一步','下一步','保存'],'button,.el-button');
  await new Promise(r=>setTimeout(r,900));
  var ok=clickText(['确定'],'button,.el-button');
  await new Promise(r=>setTimeout(r,1600));
  var after={href:location.href,hash:location.hash,text:clean(document.body&&document.body.innerText||'').slice(0,320)};
  return {ok:true,before:before,general:general,save:save,confirm:ok,after:after};
})()
"""


def run_ybb_select_general_flow() -> Dict[str, Any]:
    if websocket is None:
        return {"success": False, "stage": "dependency", "error": "websocket-client not installed"}
    try:
        ws_url, url = _pick_core_page()
    except Exception as exc:
        return {"success": False, "stage": "connect", "error": f"{type(exc).__name__}: {exc}"}
    if not ws_url:
        return {"success": False, "stage": "connect", "error": "no core.html CDP page", "url": url}
    ws = websocket.create_connection(ws_url, timeout=10)
    counter = 0
    try:
        counter += 1
        _call(ws, "Runtime.enable", msg_id=counter)
        counter += 1
        result = _eval(ws, CLICK_YBB_GENERAL_AND_SAVE_JS, counter, timeout_ms=45000)
        ok = isinstance(result, dict) and bool(result.get("ok"))
        return {"success": ok, "stage": "clicked", "url": url, "result": result}
    except Exception as exc:
        return {"success": False, "stage": "click", "url": url, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            ws.close()
        except Exception:
            pass
