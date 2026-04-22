#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/manual_call_check_establish_name.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws_url:
        rec["error"] = "no_guide_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=90000):
        nonlocal mid
        mid += 1
        ws.send(
            json.dumps(
                {
                    "id": mid,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    rec["steps"].append(
        {
            "step": "call",
            "data": ev(
                r"""(async function(){
                  function walk(vm,d){
                    if(!vm||d>18) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    var ch=vm.$children||[];
                    for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
                    return null;
                  }
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  var q=(vm.$route&&vm.$route.query)||{};
                  var u=JSON.parse(JSON.stringify(vm.form||{}));
                  // 对齐 flowSave 分支：nameCode=0 时删除 name/number
                  if(String(u.nameCode)!=='1'){ delete u.name; delete u.number; }
                  // 强制补齐关键字段：entType/busiType 等（有些场景 form 里没有但后端需要）
                  var payload=Object.assign({}, u, {
                    gainError:'1',
                    establishType:q.establishType,
                    entType: (u.entType||q.entType||''),
                    busiType: (u.busiType||q.busiType||''),
                    marPrId: (u.marPrId||q.marPrId||''),
                    marUniscId: (u.marUniscId||q.marUniscId||'')
                  });
                  var out={payload:payload, routeQuery:q, hasApi:!!(vm.$api&&vm.$api.guide&&vm.$api.guide.checkEstablishName)};
                  if(!(vm.$api&&vm.$api.guide&&vm.$api.guide.checkEstablishName)) return Object.assign({ok:false,err:'no_checkEstablishName'}, out);
                  try{
                    var rsp=await vm.$api.guide.checkEstablishName(payload);
                    out.ok=true;
                    out.code=rsp&&rsp.code;
                    out.msg=rsp&&rsp.msg;
                    out.data=(rsp&&rsp.data)||null;
                    return out;
                  }catch(e){
                    out.ok=false;
                    out.err=String(e);
                    try{out.err_json=JSON.stringify(e);}catch(_){}
                    return out;
                  }
                })()"""
            ),
        }
    )

    # if possible jump manually
    rec["steps"].append(
        {
            "step": "manual_jump_core",
            "data": ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>18) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    var ch=vm.$children||[];
                    for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
                    return null;
                  }
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  var q=(vm.$route&&vm.$route.query)||{};
                  var l=q.busiType || '02_4';
                  var o=q.vipChannel || null;
                  var d=q.ywlbSign || '';
                  var c=q.busiId || '';
                  var u=JSON.parse(JSON.stringify(vm.form||{}));
                  if(String(u.nameCode)!=='1'){ delete u.name; delete u.number; }
                  var p={entType:u.entType,busiType:l,extra:'guideData',vipChannel:o,ywlbSign:d,busiId:c,extraDto:JSON.stringify({extraDto:u})};
                  if(vm.$router&&vm.$router.jump){
                    vm.$router.jump({project:'core',path:'/flow/base',target:'_self',params:p});
                    return {ok:true,params:p};
                  }
                  return {ok:false,err:'no_router_jump',params:p};
                })()"""
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "after", "data": ev(r"""(function(){return {href:location.href,hash:location.hash,title:document.title,text:(document.body.innerText||'').slice(0,260)};})()""", 15000)})

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

