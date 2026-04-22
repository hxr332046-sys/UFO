#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/probe_name_generation_chain.json")


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

    def ev(expr, timeout=90000):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        end = time.time() + 110
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
            "step": "probe_methods",
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
                    var timeout = new Promise(function(resolve){ setTimeout(function(){resolve({name:name,ok:false,err:'timeout_10s'});},10000); });
                    var work = Promise.resolve().then(function(){ return fn(arg); }).then(function(r){ return {name:name,ok:true,arg:arg,r:r}; }).catch(function(e){
                      var out={name:name,ok:false,arg:arg,err:String(e)};
                      try{out.err_json=JSON.stringify(e);}catch(_){}
                      return out;
                    });
                    return Promise.race([work, timeout]);
                  }
                  var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
                  if(!vm) return {ok:false,err:'no_vm',href:location.href,hash:location.hash};
                  var g=vm.$api.guide;
                  var base={entType:'4540',distCode:'450102',streetCode:'450102',namePre:'广西',nameMark:'智信',industry:'科技',mainBusinessDesc:'软件开发',organize:'个人独资企业'};
                  var out={href:location.href,hash:location.hash,calls:[]};
                  out.calls.push(await tcall(g.getOrganizeList&&g.getOrganizeList.bind(g), {entType:'4540'}, 'getOrganizeList'));
                  out.calls.push(await tcall(g.queryNameEntTypeCfgByEntTypeQmb&&g.queryNameEntTypeCfgByEntTypeQmb.bind(g), {entType:'4540'}, 'queryNameEntTypeCfgByEntTypeQmb'));
                  out.calls.push(await tcall(g.checkNamePrefixList&&g.checkNamePrefixList.bind(g), {entType:'4540',distCode:'450102'}, 'checkNamePrefixList'));
                  out.calls.push(await tcall(g.preCheckCompanyName&&g.preCheckCompanyName.bind(g), base, 'preCheckCompanyName'));
                  out.calls.push(await tcall(g.checkCompanyName&&g.checkCompanyName.bind(g), base, 'checkCompanyName'));
                  out.calls.push(await tcall(g.generateCompanyName&&g.generateCompanyName.bind(g), base, 'generateCompanyName'));
                  out.calls.push(await tcall(g.startGenerateCompanyName&&g.startGenerateCompanyName.bind(g), base, 'startGenerateCompanyName'));
                  out.calls.push(await tcall(g.getGenerateCompanyNameRedis&&g.getGenerateCompanyNameRedis.bind(g), {}, 'getGenerateCompanyNameRedis'));
                  out.calls.push(await tcall(g.getGenerateCompanyInfoRedis&&g.getGenerateCompanyInfoRedis.bind(g), {}, 'getGenerateCompanyInfoRedis'));
                  out.calls.push(await tcall(g.saveNameMarkInfo&&g.saveNameMarkInfo.bind(g), base, 'saveNameMarkInfo'));
                  return out;
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

