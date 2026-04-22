#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fix_org_by_label_and_input.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["steps"].append({"step": "before", "data": ev(ws, r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {errors:errs.slice(0,10),hash:location.hash};})()""")})
    rec["steps"].append(
        {
            "step": "fill_org_label",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
                  if(!idx||!org) return {ok:false,msg:'no_idx_or_org'};
                  var first=(org.groupList||[])[0]||{};
                  var code=String(first.code||'802');
                  var label=String(first.name||'院');
                  idx.$set(idx.formInfo,'organize',code);
                  org.formInline=org.formInline||{};
                  org.$set(org.formInline,'groupval',code);
                  org.$set(org.formInline,'radio1',code);
                  org.$set(org,'searchvalue',label);
                  org.$set(org,'zhongjainzhi',label);
                  // sync visible input under organization-select
                  var orgWrap=[...document.querySelectorAll('.organization-select')].find(x=>x.offsetParent!==null);
                  if(orgWrap){
                    var inp=orgWrap.querySelector('input.el-input__inner,input');
                    if(inp){
                      var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                      setter.call(inp,label);
                      inp.dispatchEvent(new Event('input',{bubbles:true}));
                      inp.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                  }
                  try{ if(typeof org.focusFun==='function') org.focusFun(); }catch(e){}
                  try{ if(typeof org.radioChange==='function') org.radioChange({target:{value:code,_value:code}}); }catch(e){}
                  // name setting preview
                  idx.$set(idx.formInfo,'name', '广西南宁桂柚百货'+label);
                  var gp=true, ge='';
                  try{ var p=idx.getFormPromise(); if(p&&typeof p.then==='function') gp=await p; else gp=!!p; }catch(e){ gp=false; ge=String(e); }
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save) save.click();
                  return {ok:true,code:code,label:label,gp:gp,ge:ge,organize:idx.formInfo&&idx.formInfo.organize,searchvalue:org.searchvalue,zhongjainzhi:org.zhongjainzhi,name:idx.formInfo&&idx.formInfo.name};
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "after", "data": ev(ws, r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {errors:errs.slice(0,10),hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

