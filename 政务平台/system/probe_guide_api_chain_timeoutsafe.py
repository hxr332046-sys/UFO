#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_guide_api_chain_timeoutsafe.json")


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

    def ev(expr, timeout=70000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        end = time.time() + 90
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
                  function tcall(fn,arg,name){
                    if(typeof fn!=='function') return Promise.resolve({name:name,ok:false,err:'no_method'});
                    var timeout = new Promise(function(resolve){ setTimeout(function(){resolve({name:name,ok:false,err:'timeout_8s'});},8000); });
                    var work = Promise.resolve().then(function(){ return fn(arg); }).then(function(r){ return {name:name,ok:true,r:r}; }).catch(function(e){
                      var out={name:name,ok:false,err:String(e)};
                      try{out.err_json=JSON.stringify(e);}catch(_){}
                      return out;
                    });
                    return Promise.race([work, timeout]);
                  }
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm',href:location.href,hash:location.hash};
                  var g=vm.$api.guide;
                  var q=(vm.$route&&vm.$route.query)||{};
                  var form=JSON.parse(JSON.stringify(vm.form||{}));
                  var payload=Object.assign({}, form, {gainError:'1', establishType:q.establishType});
                  var basic={busiType:q.busiType||'02_4',entType:form.entType||q.entType||'4540',extra:'guideData',vipChannel:q.vipChannel||null,ywlbSign:q.ywlbSign||'',busiId:q.busiId||'',extraDto:JSON.stringify({extraDto:form})};
                  var calls=[];
                  calls.push(await tcall(g.nameGuide&&g.nameGuide.bind(g), basic, 'nameGuide'));
                  calls.push(await tcall(g.preProcessDeclare&&g.preProcessDeclare.bind(g), basic, 'preProcessDeclare'));
                  calls.push(await tcall(g.queryExtraDto&&g.queryExtraDto.bind(g), basic, 'queryExtraDto'));
                  calls.push(await tcall(g.matchAddressAndEntType&&g.matchAddressAndEntType.bind(g), {entType:basic.entType,distCode:form.distCode||'',streetCode:form.streetCode||''}, 'matchAddressAndEntType'));
                  calls.push(await tcall(g.checkEstablishName&&g.checkEstablishName.bind(g), payload, 'checkEstablishName'));
                  return {ok:true,href:location.href,hash:location.hash,routeQuery:q,form:form,calls:calls};
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

