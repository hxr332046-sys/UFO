#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/force_memberpost_next_with_itemid_02_4.json")
ITEM_ID = "2044029370544291840"


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        try:
            m = json.loads(ws.recv())
        except Exception:
            continue
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_member_post"
    else:
        rec["set_ids"] = ev(
            ws,
            f"""(function(){{
              function find(vm,d){{if(!vm||d>20)return null; var n=(vm.$options&&vm.$options.name)||''; if(n==='flow-control')return vm; for(var c of (vm.$children||[])){{var r=find(c,d+1); if(r) return r;}} return null;}}
              var fc=find(document.getElementById('app').__vue__,0);
              if(!fc) return {{ok:false,msg:'no fc'}};
              var arr=fc.busiCompUrlPaths||[];
              for(var i=0;i<arr.length;i++){{ if(arr[i].compUrl==='MemberPost' || i===arr.length-1) fc.$set(arr[i],'id','{ITEM_ID}'); }}
              return {{ok:true,paths:arr,hash:location.hash}};
            }})()""",
        )
        rec["invoke_next"] = ev(
            ws,
            r"""(async function(){
              function find(vm,d){if(!vm||d>20)return null; var n=(vm.$options&&vm.$options.name)||''; if(n==='flow-control')return vm; for(var c of (vm.$children||[])){var r=find(c,d+1); if(r) return r;} return null;}
              var fc=find(document.getElementById('app').__vue__,0);
              if(!fc) return {ok:false,msg:'no fc'};
              var ret={ok:true,actions:[]};
              try{ if(typeof fc.handleStepsNext==='function'){ fc.handleStepsNext(); ret.actions.push('handleStepsNext'); } }catch(e){ ret.actions.push('handleStepsNext_err:'+String(e));}
              await new Promise(r=>setTimeout(r,5000));
              try{ if(typeof fc.operationBusinessDataInfo==='function'){ fc.operationBusinessDataInfo(fc.params || {}); ret.actions.push('operationBusinessDataInfo'); } }catch(e){ ret.actions.push('operation_err:'+String(e));}
              await new Promise(r=>setTimeout(r,5000));
              ret.href=location.href; ret.hash=location.hash;
              return ret;
            })()""",
        )
        rec["after"] = ev(
            ws,
            r"""(function(){
              var btn=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled}));
              var err=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              return {href:location.href,hash:location.hash,buttons:btn.slice(0,12),errors:err.slice(0,10)};
            })()""",
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

