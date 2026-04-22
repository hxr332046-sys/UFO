#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fix_org_zhongjainzhi_and_save.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=18)
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
            "step": "fix_and_save",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  function safe(v){try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);}}
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
                  if(!idx||!org) return {ok:false,msg:'no_idx_or_org'};
                  var code='802';
                  idx.$set(idx.formInfo,'organize',code);
                  org.formInline=org.formInline||{};
                  org.$set(org.formInline,'groupval',code);
                  org.$set(org.formInline,'radio1',code);
                  try{ org.$set(org,'zhongjainzhi',code); }catch(e){ org.zhongjainzhi=code; }
                  try{ org.$emit('input',code); }catch(e){}
                  try{ org.$emit('change',code); }catch(e){}
                  try{ if(typeof org.focusFun==='function') org.focusFun(); }catch(e){}
                  try{ if(typeof org.radioChange==='function') org.radioChange({target:{value:code}}); }catch(e){}
                  var gp1=true,gp2=true,ge1='',ge2='';
                  try{ var p1=idx.getFormPromise(); if(p1&&typeof p1.then==='function') gp1=await p1; else gp1=!!p1; }catch(e){ gp1=false; ge1=String(e); }
                  try{ var p2=idx.getFormPromise(); if(p2&&typeof p2.then==='function') gp2=await p2; else gp2=!!p2; }catch(e){ gp2=false; ge2=String(e); }
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save) save.click();
                  await new Promise(r=>setTimeout(r,400));
                  return {
                    ok:true,
                    gp1:gp1,gp2:gp2,ge1:ge1,ge2:ge2,
                    orgInline:safe(org.formInline),
                    zhongjainzhi:safe(org.zhongjainzhi),
                    organize:idx.formInfo&&idx.formInfo.organize
                  };
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

