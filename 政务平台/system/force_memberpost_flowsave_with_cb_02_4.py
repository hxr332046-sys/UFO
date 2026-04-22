#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/force_memberpost_flowsave_with_cb_02_4.json")


def ev(ws_url, expr, timeout=60000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
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
              function walk(vm,d){
                if(!vm||d>12) return null;
                var n=(vm.$options&&vm.$options.name)||'';
                if(n==='MemberPost' && typeof vm.flowSave==='function') return vm;
                for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
                return null;
              }
              var m=walk(document.getElementById('app').__vue__,0);
              if(!m) return {ok:false,msg:'no vm'};
              var called={succ:false,fail:false};
              try{
                m.flowSave({
                  success:function(v){called.succ=true; called.succData=v||null;},
                  fail:function(v){called.fail=true; called.failData=v||null;},
                  error:function(v){called.fail=true; called.errData=v||null;}
                });
                await new Promise(r=>setTimeout(r,5000));
                return {ok:true,called:called,hash:location.hash,href:location.href};
              }catch(e){return {ok:false,msg:String(e)};}
            })()""",
        )
        time.sleep(2)
        rec["after"] = ev(ws, "location.href + ' | ' + location.hash")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

