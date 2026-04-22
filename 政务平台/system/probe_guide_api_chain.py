#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_guide_api_chain.json")


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
    ws.settimeout(2.0)
    mid = 0

    def ev(expr, timeout=120000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        end = time.time() + max(20, timeout / 1000 + 20)
        while True:
            if time.time() > end:
                return {"error": "cdp_eval_timeout"}
            try:
                m = json.loads(ws.recv())
            except Exception:
                continue
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    rec["steps"].append(
        {
            "step": "probe",
            "data": ev(
                r"""(async function(){
                  function walk(vm,d){
                    if(!vm||d>18) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && vm.$api && vm.$api.guide) return vm;
                    var ch=vm.$children||[];
                    for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
                    return null;
                  }
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm'};
                  var g=vm.$api.guide;
                  var q=(vm.$route&&vm.$route.query)||{};
                  var form=JSON.parse(JSON.stringify(vm.form||{}));
                  var payload=Object.assign({}, form, {gainError:'1', establishType:q.establishType});
                  var basic={
                    busiType:q.busiType||'02_4',
                    entType:form.entType||q.entType||'4540',
                    extra:'guideData',
                    vipChannel:q.vipChannel||null,
                    ywlbSign:q.ywlbSign||'',
                    busiId:q.busiId||'',
                    extraDto:JSON.stringify({extraDto:form})
                  };
                  var result={href:location.href,hash:location.hash,routeQuery:q,form:form,calls:[]};
                  async function call(name,arg){
                    if(typeof g[name]!=='function'){ result.calls.push({name:name,skip:'no_method'}); return null; }
                    try{
                      var r=await g[name](arg);
                      result.calls.push({name:name,ok:true,arg:arg,r:(function(x){try{return JSON.parse(JSON.stringify(x));}catch(e){return String(x);}})(r)});
                      return r;
                    }catch(e){
                      var item={name:name,ok:false,arg:arg,err:String(e)};
                      try{item.err_json=JSON.stringify(e);}catch(_){}
                      result.calls.push(item);
                      return null;
                    }
                  }

                  // 候选链路：先做预处理/引导，再做检查
                  await call('nameGuide', basic);
                  await call('preProcessDeclare', basic);
                  await call('queryExtraDto', basic);
                  await call('matchAddressAndEntType', {entType:basic.entType, distCode:form.distCode||'', streetCode:form.streetCode||''});
                  await call('checkEstablishName', payload);
                  return result;
                })()"""
            ),
        }
    )

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

