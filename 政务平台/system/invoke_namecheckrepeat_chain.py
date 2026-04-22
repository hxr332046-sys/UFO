#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/invoke_namecheckrepeat_chain.json")


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
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 80000},
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
    rec["steps"].append({"step": "before", "data": ev(ws, r"""(function(){var t=(document.body.innerText||'');return {hash:location.hash,hasNotice:t.indexOf('请阅读《名称登记自主申报须知》并勾选')>=0};})()""")})
    rec["steps"].append(
        {
            "step": "invoke_chain",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  if(!idx) return {ok:false,msg:'no_index'};
                  var trace=[];
                  function s(v){try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);}}
                  try{
                    var p=idx.getFormPromise&&idx.getFormPromise();
                    if(p&&typeof p.then==='function'){trace.push(['getFormPromise',await p]);}
                    else trace.push(['getFormPromise',!!p]);
                  }catch(e){trace.push(['getFormPromise_err',String(e)]);}
                  try{
                    if(typeof idx.nameCheckRepeat==='function'){
                      var r1=idx.nameCheckRepeat();
                      if(r1&&typeof r1.then==='function'){trace.push(['nameCheckRepeat',s(await r1)]);}
                      else trace.push(['nameCheckRepeat_ret',s(r1)]);
                    }else trace.push(['no_nameCheckRepeat']);
                  }catch(e){trace.push(['nameCheckRepeat_err',String(e)]);}
                  // close notice if any
                  var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
                  if(ok){ok.click(); trace.push(['click_ok']);}
                  try{
                    if(typeof idx.flowSave==='function'){
                      var r2=idx.flowSave();
                      if(r2&&typeof r2.then==='function'){trace.push(['flowSave',s(await r2)]);}
                      else trace.push(['flowSave_ret',s(r2)]);
                    }else trace.push(['no_flowSave']);
                  }catch(e){trace.push(['flowSave_err',String(e)]);}
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save){save.click(); trace.push(['click_save']);}
                  return {ok:true,trace:trace};
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "after", "data": ev(ws, r"""(function(){var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,hasNotice:txt.indexOf('请阅读《名称登记自主申报须知》并勾选')>=0,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

