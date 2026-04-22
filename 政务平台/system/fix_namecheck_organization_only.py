#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fix_namecheck_organization_only.json")


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

    rec["steps"].append(
        {
            "step": "before",
            "data": ev(
                ws,
                r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10)};})()""",
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "set_org_and_save",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
                  if(!idx||!org) return {ok:false,msg:'no_idx_or_org'};
                  var trace=[];
                  var code='802';
                  // set parent model
                  idx.$set(idx.formInfo,'organize',code);
                  trace.push('idx.formInfo.organize=802');
                  // set child model
                  org.formInline=org.formInline||{};
                  org.$set(org.formInline,'groupval',code);
                  org.$set(org.formInline,'radio1',code);
                  trace.push('org.formInline set');
                  // method attempts
                  try{ if(typeof org.focusFun==='function'){ org.focusFun(); trace.push('org.focusFun'); } }catch(e){ trace.push('focus_err:'+String(e)); }
                  try{ if(typeof org.radioChange==='function'){ org.radioChange({target:{value:code}}); trace.push('org.radioChange(evt)'); } }catch(e){ trace.push('radio_evt_err:'+String(e)); }
                  try{ if(typeof org.radioChange==='function'){ org.radioChange(code); trace.push('org.radioChange(code)'); } }catch(e){ trace.push('radio_code_err:'+String(e)); }
                  // emit to parent
                  try{ org.$emit('input',code); trace.push('emit_input'); }catch(e){ trace.push('emit_input_err:'+String(e)); }
                  try{ org.$emit('change',code); trace.push('emit_change'); }catch(e){ trace.push('emit_change_err:'+String(e)); }
                  try{ if(idx&&typeof idx.$forceUpdate==='function'){ idx.$forceUpdate(); trace.push('idx.forceUpdate'); } }catch(e){}
                  await new Promise(r=>setTimeout(r,200));
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save){ save.click(); trace.push('click_save'); }
                  return {ok:true,trace:trace,orgInline:{groupval:org.formInline&&org.formInline.groupval,radio1:org.formInline&&org.formInline.radio1},parentOrganize:idx.formInfo&&idx.formInfo.organize};
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append(
        {
            "step": "after",
            "data": ev(
                ws,
                r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""",
            ),
        }
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

