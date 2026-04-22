#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fix_member_info_and_next_02_4.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=50000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


JS_FILL_MEMBER = r"""(function(){
  function setByLabel(labelKw,val){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
      var lb=items[i].querySelector('.el-form-item__label');
      var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
      if(t.indexOf(labelKw)>=0){
        var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
        if(inp && !inp.disabled){
          var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
          setter.call(inp,val);
          inp.dispatchEvent(new Event('input',{bubbles:true}));
          inp.dispatchEvent(new Event('change',{bubbles:true}));
          return {ok:true,label:t,val:val};
        }
      }
    }
    return {ok:false,label:labelKw};
  }
  var out={};
  out.name=setByLabel('成员名称','黄永裕');
  out.idNo=setByLabel('证件号码','450921198812051251');
  out.nation=setByLabel('民族','汉族');
  out.birth=setByLabel('出生日期','1988-12-05');
  out.organ=setByLabel('发证机关','容县公安局');
  out.validStart=setByLabel('证件有效期起','2010-01-01');
  out.addr=setByLabel('住址','广西玉林市容县容州镇容州大道88号');
  // gender
  var radios=[...document.querySelectorAll('.el-radio,.el-radio__label,span,label')].filter(e=>e.offsetParent!==null);
  for(var r of radios){
    var t=(r.textContent||'').replace(/\s+/g,' ').trim();
    if(t==='男' || t.indexOf('男')>=0){ r.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); out.gender='男'; break; }
  }
  return out;
})()"""


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = pick_ws()
    rec["steps"].append({"step": "S1_start", "data": url})
    if not ws:
        rec["error"] = "no_member_post_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append({"step": "S2_fill_member", "data": ev(ws, JS_FILL_MEMBER)})

    rec["steps"].append(
        {
            "step": "S3_click_member_confirm",
            "data": ev(
                ws,
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null&&!x.disabled);
                  var b=btns.find(x=>((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf('确 定')>=0 || ((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf('确定')>=0);
                  if(!b) return {clicked:false};
                  b.click(); return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(2)

    rec["steps"].append(
        {
            "step": "S4_click_save_next",
            "data": ev(
                ws,
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(!b) return {clicked:false};
                  b.click(); return {clicked:true,text:(b.textContent||'').trim()};
                })()""",
            ),
        }
    )
    time.sleep(8)

    rec["steps"].append(
        {
            "step": "S5_after",
            "data": ev(
                ws,
                r"""(function(){
                  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled}));
                  return {href:location.href,hash:location.hash,errors:errs.slice(0,10),buttons:btns.slice(0,20)};
                })()""",
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

