#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

OUT = Path("G:/UFO/政务平台/dashboard/data/records/core_namecheck_set_target_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 90000) -> Any:
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
    end = time.time() + 60
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


PROBE_JS = r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message__content')].map(e=>clean(e.textContent||'')).filter(Boolean).slice(0,20);
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:clean(b.textContent||''),disabled:!!b.disabled})).filter(b=>b.text).slice(0,20);
  var txt=(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim();
  return {href:location.href,hash:location.hash,errors:errs,buttons:btns,snippet:txt.slice(0,260)};
})()"""

HOOK_JS = r"""(function(){
  window.__nc_hook={items:[]};
  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){this.__ufo={m:m,u:u}; return oo.apply(this,arguments);};
  XMLHttpRequest.prototype.send=function(b){
    var self=this; var u=(self.__ufo&&self.__ufo.u)||'';
    if(String(u).indexOf('/icpsp-api/')>=0){
      window.__nc_hook.items.push({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:String(u).slice(0,220),body:String(b||'').slice(0,800)});
      self.addEventListener('loadend', function(){
        window.__nc_hook.items.push({t:'xhr_end',u:String(u).slice(0,220),status:self.status,resp:String(self.responseText||'').slice(0,800)});
      });
    }
    return os.apply(this,arguments);
  };
  return {ok:true};
})()"""

FILL_JS = r"""(async function(){
  function walk(vm,d,pred){ if(!vm||d>25) return null; if(pred(vm)) return vm; for(var ch of (vm.$children||[])){ var r=walk(ch,d+1,pred); if(r) return r; } return null; }
  var app=document.getElementById('app'); var root=app&&app.__vue__;
  if(!root) return {ok:false,msg:'no_root'};
  var idx=walk(root,0,function(v){return (v.$options&&v.$options.name)==='index' && v.$parent && v.$parent.$options && v.$parent.$options.name==='name-check-info';});
  if(!idx) return {ok:false,msg:'no_namecheck_index'};
  idx.formInfo=idx.formInfo||{};
  var trace=[];
  idx.$set(idx.formInfo,'namePre','广西容县');
  idx.$set(idx.formInfo,'nameMark','李陈梦');
  idx.$set(idx.formInfo,'industrySpecial','软件开发');
  idx.$set(idx.formInfo,'mainBusinessDesc','软件开发');
  idx.$set(idx.formInfo,'distCode','450921');
  idx.$set(idx.formInfo,'streetCode','450921');
  idx.$set(idx.formInfo,'address','容县');
  if(!idx.formInfo.organize) idx.$set(idx.formInfo,'organize','有限公司');
  idx.$set(idx.formInfo,'isCheckBox','Y');
  idx.$set(idx.formInfo,'declarationMode','Y');
  trace.push('set_formInfo_base');

  try{
    if(typeof idx.nameCheckRepeat==='function'){
      var r=idx.nameCheckRepeat();
      if(r&&typeof r.then==='function') await r;
      trace.push('nameCheckRepeat_called');
    }
  }catch(e){ trace.push('nameCheckRepeat_err:'+String(e)); }

  try{
    var agree=[...document.querySelectorAll('label,span,div,.el-checkbox')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0);
    if(agree){ agree.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); trace.push('agree_click'); }
  }catch(e){ trace.push('agree_err:'+String(e)); }

  try{
    var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&!x.disabled&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0);
    if(save){ save.click(); trace.push('click_save_next'); }
    else if(typeof idx.flowSave==='function'){
      var r2=idx.flowSave(); if(r2&&typeof r2.then==='function') await r2; trace.push('flowSave_called');
    } else trace.push('no_save_method');
  }catch(e){ trace.push('save_err:'+String(e)); }

  return {ok:true,trace:trace,formInfo:idx.formInfo};
})()"""


def main() -> int:
    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=False)
    rec: dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_namecheck_tab"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "probe_before", "data": ev(ws, PROBE_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "install_hook", "data": ev(ws, HOOK_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "fill_and_save", "data": ev(ws, FILL_JS, 120000)})
    sleep_human(2.0)
    rec["steps"].append({"step": "probe_after", "data": ev(ws, PROBE_JS, 30000)})
    rec["steps"].append({"step": "hook_tail", "data": ev(ws, r"(function(){return window.__nc_hook?{count:window.__nc_hook.items.length,items:window.__nc_hook.items.slice(-20)}:null;})()", 30000)})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

