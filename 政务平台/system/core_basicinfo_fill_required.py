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

OUT = Path("G:/UFO/政务平台/dashboard/data/records/core_basicinfo_fill_required_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 70000) -> Any:
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
    end = time.time() + 50
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
  return {href:location.href,hash:location.hash,errors:errs,buttons:btns};
})()"""

FILL_JS = r"""(async function(){
  function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
  function setVal(inp,val){
    if(!inp) return false;
    var p = inp.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    var d = Object.getOwnPropertyDescriptor(p,'value');
    if(!d||!d.set) return false;
    d.set.call(inp,String(val||''));
    inp.dispatchEvent(new Event('input',{bubbles:true}));
    inp.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
  }
  function setByLabel(labelPart,val){
    var items=[...document.querySelectorAll('.el-form-item')].filter(function(it){ return it.offsetParent!==null; });
    for(var it of items){
      var lb=it.querySelector('.el-form-item__label');
      var t=clean(lb&&lb.textContent||'');
      if(t.indexOf(labelPart)>=0){
        var inp=it.querySelector('input.el-input__inner,textarea.el-textarea__inner');
        if(inp && !inp.disabled){
          var ok=setVal(inp,val);
          inp.dispatchEvent(new Event('blur',{bubbles:true}));
          return {ok:ok,label:t,value:String(inp.value||'')};
        }
      }
    }
    return {ok:false,label:labelPart};
  }
  function clickOptionByText(text){
    var els=[...document.querySelectorAll('.el-cascader-node,.el-cascader-node__label,.el-select-dropdown__item,li[role=option],.tne-data-picker-popover li,.tne-data-picker-popover .sample-item')].filter(e=>e.offsetParent!==null);
    for(var e of els){
      var t=clean(e.textContent||'');
      if(t===text || (t.indexOf(text)>=0 && t.length<30)){
        (e.closest('.el-cascader-node,.el-select-dropdown__item,li[role=option],li,.sample-item')||e).click();
        return {ok:true,text:t};
      }
    }
    return {ok:false,text:text};
  }
  async function pickAddress(labelPart){
    var items=[...document.querySelectorAll('.el-form-item')].filter(function(it){ return it.offsetParent!==null; });
    var target=null;
    for(var it of items){
      var lb=it.querySelector('.el-form-item__label');
      var t=clean(lb&&lb.textContent||'');
      if(t.indexOf(labelPart)>=0){ target=it; break; }
    }
    if(!target) return {ok:false,msg:'no_label:'+labelPart};
    var inp=target.querySelector('input.el-input__inner,.el-cascader .el-input__inner');
    if(inp){ inp.click(); } else { target.click(); }
    await new Promise(r=>setTimeout(r,600));
    var r1=clickOptionByText('广西壮族自治区'); await new Promise(r=>setTimeout(r,350));
    var r2=clickOptionByText('玉林市'); await new Promise(r=>setTimeout(r,350));
    var r3=clickOptionByText('容县');
    return {ok:true,r1:r1,r2:r2,r3:r3};
  }
  async function pickIndustry(){
    var items=[...document.querySelectorAll('.el-form-item')].filter(function(it){ return it.offsetParent!==null; });
    var target=null;
    for(var it of items){
      var lb=it.querySelector('.el-form-item__label');
      var t=clean(lb&&lb.textContent||'');
      if(t.indexOf('行业类型')>=0){ target=it; break; }
    }
    if(!target) return {ok:false,msg:'no_industry_label'};
    var inp=target.querySelector('input.el-input__inner');
    if(inp){ inp.click(); } else { target.click(); }
    await new Promise(r=>setTimeout(r,700));
    var r=clickOptionByText('软件开发');
    if(!r.ok) r=clickOptionByText('软件和信息技术服务业');
    if(!r.ok) r=clickOptionByText('软件');
    return {ok:r.ok,hit:r.text};
  }
  var log=[];
  log.push(['entName', setByLabel('企业名称', '广西容县李陈梦软件开发有限公司')]);
  log.push(['capital', setByLabel('注册资本', '5')]);
  log.push(['emp', setByLabel('从业人数', '1')]);
  log.push(['phone', setByLabel('联系电话', '18977514335')]);
  log.push(['postcode', setByLabel('邮政编码', '537500')]);
  log.push(['detail', setByLabel('详细地址', '容州镇车站西路富盛广场1幢3203号房')]);
  log.push(['biz_detail', setByLabel('生产经营地详细地址', '容州镇车站西路富盛广场1幢3203号房')]);
  var scope = setByLabel('经营范围（许可经营项目）', '软件开发；信息技术咨询服务。');
  if(!scope.ok) scope = setByLabel('经营范围', '软件开发；信息技术咨询服务。');
  log.push(['scope', scope]);
  log.push(['addr_main', await pickAddress('企业住所')]);
  log.push(['addr_biz', await pickAddress('生产经营地址')]);
  log.push(['industry', await pickIndustry()]);
  await new Promise(r=>setTimeout(r,500));
  var btn=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled).find(b=>clean(b.textContent||'').indexOf('保存并下一步')>=0)
       || [...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled).find(b=>clean(b.textContent||'').indexOf('下一步')>=0);
  if(btn){ btn.click(); log.push(['click',clean(btn.textContent||'')]); }
  return {ok:true,log:log,clicked:!!btn};
})()"""


def main() -> int:
    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=False)
    rec: dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_basicinfo_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "probe_before", "data": ev(ws, PROBE_JS, 30000)})
    sleep_human(1.0)
    rec["steps"].append({"step": "fill_and_save", "data": ev(ws, FILL_JS, 120000)})
    sleep_human(2.0)
    rec["steps"].append({"step": "probe_after", "data": ev(ws, PROBE_JS, 30000)})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

