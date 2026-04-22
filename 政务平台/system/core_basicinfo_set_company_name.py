#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在 core basic-info 页面尝试填写公司名并保存下一步，输出完整证据。
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

OUT = Path("G:/UFO/政务平台/dashboard/data/records/core_basicinfo_set_company_name_latest.json")
TARGET_NAME = "广西容县李陈梦软件开发有限公司"


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 60000) -> Any:
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
    end = time.time() + 45
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
  var items=[...document.querySelectorAll('.el-form-item')].map(function(it){
    var lb=it.querySelector('.el-form-item__label');
    var inp=it.querySelector('input.el-input__inner,textarea.el-textarea__inner');
    return {
      label: clean(lb&&lb.textContent||''),
      value: inp ? String(inp.value||'') : '',
      disabled: !!(inp&&inp.disabled),
      readonly: !!(inp&&inp.readOnly)
    };
  }).filter(function(x){return x.label;}).slice(0,40);
  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message__content')].map(e=>clean(e.textContent||'')).filter(Boolean).slice(0,20);
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:clean(b.textContent||''),disabled:!!b.disabled})).filter(b=>b.text).slice(0,20);
  return {href:location.href,hash:location.hash,items:items,errors:errs,buttons:btns};
})()"""

HOOK_JS = r"""(function(){
  window.__bi_hook={items:[]};
  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){this.__ufo={m:m,u:u}; return oo.apply(this,arguments);};
  XMLHttpRequest.prototype.send=function(b){
    var self=this; var u=(self.__ufo&&self.__ufo.u)||'';
    if(String(u).indexOf('/icpsp-api/')>=0){
      window.__bi_hook.items.push({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:String(u).slice(0,220),body:String(b||'').slice(0,800)});
      self.addEventListener('loadend', function(){
        window.__bi_hook.items.push({t:'xhr_end',u:String(u).slice(0,220),status:self.status,resp:String(self.responseText||'').slice(0,800)});
      });
    }
    return os.apply(this,arguments);
  };
  return {ok:true};
})()"""

FILL_AND_SAVE_JS = (
    r"""(function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  function setVal(inp,val){
    if(!inp) return false;
    var p = inp.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    var d = Object.getOwnPropertyDescriptor(p,'value');
    if(!d||!d.set) return false;
    d.set.call(inp,val);
    inp.dispatchEvent(new Event('input',{bubbles:true}));
    inp.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
  }
  var targetName="""
    + json.dumps(TARGET_NAME, ensure_ascii=False)
    + r""";
  var filled=false, mode='none';
  var items=[...document.querySelectorAll('.el-form-item')];
  for(var i=0;i<items.length;i++){
    var lb=items[i].querySelector('.el-form-item__label');
    var t=clean(lb&&lb.textContent||'');
    if(t.indexOf('企业名称')>=0){
      var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
      if(inp && !inp.disabled && !inp.readOnly){
        filled=setVal(inp,targetName);
        mode='by_label_input';
      }else{
        mode='name_input_disabled_or_readonly';
      }
      break;
    }
  }
  // VM 兜底
  try{
    var app=document.getElementById('app');
    var root=app&&app.__vue__;
    function walk(vm,d){
      if(!vm||d>20) return null;
      var n=(vm.$options&&vm.$options.name)||'';
      if(n==='index' && vm.formInfo) return vm;
      for(var ch of (vm.$children||[])){ var r=walk(ch,d+1); if(r) return r; }
      return null;
    }
    var idx=walk(root,0);
    if(idx && idx.formInfo){
      if(!filled){ idx.$set(idx.formInfo,'entName',targetName); mode='vm_formInfo_entName'; filled=true; }
      idx.$set(idx.formInfo,'name',targetName);
    }
  }catch(e){}
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled);
  var b=btns.find(x=>clean(x.textContent||'').indexOf('保存并下一步')>=0)
      || btns.find(x=>clean(x.textContent||'').indexOf('下一步')>=0)
      || btns.find(x=>clean(x.textContent||'').indexOf('保存')>=0);
  if(b){ b.click(); return {ok:true,filled:filled,mode:mode,clicked:clean(b.textContent||'')}; }
  return {ok:false,filled:filled,mode:mode,msg:'no_save_next_btn'};
})()"""
)


def main() -> int:
    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=False)
    rec: dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_core_basicinfo_tab"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "probe_before", "data": ev(ws, PROBE_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "install_hook", "data": ev(ws, HOOK_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "fill_and_save", "data": ev(ws, FILL_AND_SAVE_JS, 60000)})
    sleep_human(2.0)
    rec["steps"].append({"step": "probe_after", "data": ev(ws, PROBE_JS, 30000)})
    rec["steps"].append({"step": "hook_tail", "data": ev(ws, r"(function(){return window.__bi_hook?{count:window.__bi_hook.items.length,items:window.__bi_hook.items.slice(-20)}:null;})()", 30000)})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

