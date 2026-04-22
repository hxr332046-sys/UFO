#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/submit_memberpost_via_flowcontrol_02_4.json")


def ev(ws_url, expr, timeout=90000):
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
        rec["invoke"] = ev(
            ws,
            r"""(async function(){
              function find(vm,d,name){
                if(!vm||d>20) return null;
                var n=(vm.$options&&vm.$options.name)||'';
                if(n===name) return vm;
                for(var c of (vm.$children||[])){var r=find(c,d+1,name); if(r) return r;}
                return null;
              }
              var root=document.getElementById('app').__vue__;
              var fc=find(root,0,'flow-control');
              var mp=(function walk(vm,d){if(!vm||d>20)return null; var n=(vm.$options&&vm.$options.name)||''; if(n==='MemberPost'&&typeof vm.flowSave==='function') return vm; for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;} return null;})(root,0);
              if(!fc||!mp) return {ok:false,msg:'fc/mp missing'};

              var saveData=null;
              mp.flowSave({
                success:function(v){saveData=v||null;},
                fail:function(){},
                error:function(){}
              });
              await new Promise(r=>setTimeout(r,2000));
              if(!saveData || !saveData.busiData) return {ok:false,msg:'no_save_data',hash:location.hash};

              var p=fc.params||{};
              p.busiData = saveData.busiData;
              p.itemId = '2044029370544291840';
              p.compUrl = 'MemberPost';
              p.currCompUrl = 'MemberPost';
              if(fc.busiCompUrlPaths && fc.busiCompUrlPaths.length){
                for(var i=0;i<fc.busiCompUrlPaths.length;i++){
                  if(fc.busiCompUrlPaths[i].compUrl==='MemberPost'){fc.$set(fc.busiCompUrlPaths[i],'id','2044029370544291840');}
                }
              }
              var opRet=null, opErr=null;
              try{
                opRet = fc.operationBusinessDataInfo(p);
              }catch(e){opErr=String(e);}
              await new Promise(r=>setTimeout(r,6000));
              return {ok:true,opRetType:typeof opRet,opErr:opErr,hash:location.hash,href:location.href};
            })()""",
        )
        rec["after"] = ev(
            ws,
            r"""(function(){
              var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled}));
              return {href:location.href,hash:location.hash,errors:errs.slice(0,12),buttons:btns.slice(0,12)};
            })()""",
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

