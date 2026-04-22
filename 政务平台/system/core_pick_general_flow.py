#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在 core.html#/flow/base/ybb-select 页面自动选择“一般流程办理”。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402

OUT = Path("G:/UFO/政务平台/dashboard/data/records/core_pick_general_flow_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base/ybb-select" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 60000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=25)
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
    end = time.time() + 40
    out = None
    while time.time() < end:
        try:
            m = json.loads(ws.recv())
        except Exception:
            continue
        if m.get("id") == 1:
            out = ((m.get("result") or {}).get("result") or {}).get("value")
            break
    ws.close()
    return out


PROBE_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  var btns=[...document.querySelectorAll('button,.el-button')].filter(e=>e.offsetParent!==null).map(b=>clean(b.textContent||'')).filter(Boolean).slice(0,20);
  var txt=(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim();
  return {href:location.href,hash:location.hash,buttons:btns,snippet:txt.slice(0,220)};
})()"""

HOOK_JS = r"""(function(){
  window.__ybb_hook={items:[]};
  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return oo.apply(this,arguments); };
  XMLHttpRequest.prototype.send=function(b){
    var self=this; var u=(self.__ufo&&self.__ufo.u)||'';
    if(String(u).indexOf('/icpsp-api/')>=0){
      window.__ybb_hook.items.push({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:String(u).slice(0,220),body:String(b||'').slice(0,500)});
      self.addEventListener('loadend', function(){
        window.__ybb_hook.items.push({t:'xhr_end',u:String(u).slice(0,220),status:self.status,resp:String(self.responseText||'').slice(0,500)});
      });
    }
    return os.apply(this,arguments);
  };
  window.__ybb_hook.restore=function(){XMLHttpRequest.prototype.open=oo;XMLHttpRequest.prototype.send=os;};
  return {ok:true};
})()"""

CLICK_GENERAL_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  var els=[...document.querySelectorAll('button,.el-button,a,div,span')].filter(e=>e.offsetParent!==null);
  var hits=[];
  for(var e of els){
    var t=clean(e.textContent||'');
    if(!t) continue;
    if(t.indexOf('选择一般流程办理')>=0 || t.indexOf('一般流程办理')>=0 || t.indexOf('一般流程')>=0){
      hits.push({e:e,t:t});
    }
  }
  hits.sort((a,b)=>a.t.length-b.t.length);
  if(!hits.length) return {ok:false,msg:'no_general_flow_clickable'};
  var node=(hits[0].e.closest('button,.el-button,a')||hits[0].e);
  node.click();
  return {ok:true,clicked:hits[0].t.slice(0,100)};
})()"""

CLICK_SAVE_OR_NEXT_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null && !b.disabled);
  var keys=['保存并下一步','下一步','保存'];
  for(var k of keys){
    for(var b of btns){
      var t=clean(b.textContent||'');
      if(t.indexOf(k)>=0){
        b.click();
        return {ok:true,clicked:t};
      }
    }
  }
  return {ok:false,msg:'no_save_or_next'};
})()"""

CLICK_DIALOG_OK_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  var box=document.querySelector('.el-message-box__wrapper');
  if(!(box&&box.offsetParent!==null)) return {ok:false,msg:'no_dialog'};
  var ok=[...document.querySelectorAll('button,.el-button')].find(b=>b.offsetParent!==null && !b.disabled && clean(b.textContent||'').indexOf('确定')>=0);
  if(!ok) return {ok:false,msg:'dialog_no_ok'};
  ok.click();
  return {ok:true,clicked:'确定'};
})()"""

DIALOG_AND_ERROR_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message__content')].map(e=>clean(e.textContent||'')).filter(Boolean).slice(0,12);
  var msg=[...document.querySelectorAll('.el-message-box__wrapper')].filter(w=>w.offsetParent!==null).map(w=>clean(w.innerText||'').slice(0,220)).slice(0,3);
  var hook=window.__ybb_hook?window.__ybb_hook.items.slice(-12):[];
  return {errors:errs,dialogs:msg,hook:hook};
})()"""

REFRESH_JS = r"""(function(){
  location.reload();
  return {ok:true,reload:true,href:location.href};
})()"""


def main() -> int:
    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=False)
    ws, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "picked_url": cur, "steps": []}
    if not ws:
        rec["error"] = "no_core_tab"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "probe_before", "data": ev(ws, PROBE_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "install_hook", "data": ev(ws, HOOK_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "click_general_flow", "data": ev(ws, CLICK_GENERAL_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "probe_after_general", "data": ev(ws, PROBE_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "click_save_or_next", "data": ev(ws, CLICK_SAVE_OR_NEXT_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "click_dialog_ok", "data": ev(ws, CLICK_DIALOG_OK_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "dialog_error_and_hook", "data": ev(ws, DIALOG_AND_ERROR_JS, 30000)})
    # 若服务端异常，按用户要求：直接刷新并更新页面数据后再探测一次
    err_probe = rec["steps"][-1]["data"] if rec["steps"] else {}
    hook_items = (err_probe or {}).get("hook") or []
    a0002 = any(isinstance(it, dict) and "A0002" in str(it.get("resp", "")) for it in hook_items)
    ui_err = any("服务出现异常" in str(x) or "服务端异常" in str(x) for x in ((err_probe or {}).get("errors") or []))
    if a0002 or ui_err:
        sleep_human(1.0)
        rec["steps"].append({"step": "refresh_on_service_error", "data": ev(ws, REFRESH_JS, 30000)})
        sleep_human(2.2)
        rec["steps"].append({"step": "probe_after_refresh", "data": ev(ws, PROBE_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append(
        {
            "step": "after_state",
            "data": ev(
                ws,
                r"""(function(){var txt=(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim();return {href:location.href,hash:location.hash,title:document.title,hasNameCheck:location.href.indexOf('name-check-info')>=0,hasYunSubmit:/云提交|云端提交/.test(txt),snippet:txt.slice(0,260)};})()""",
                30000,
            ),
        }
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

