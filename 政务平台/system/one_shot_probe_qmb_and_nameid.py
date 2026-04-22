#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
单次探测（不循环、不点击轰炸）：
- 在 guide/base 上调用名称生成相关 API（企名宝链路）并记录返回码
- 尝试从响应里提取 nameId/serial 等字段

证据落盘：dashboard/data/records/one_shot_probe_qmb_and_nameid.json
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/one_shot_probe_qmb_and_nameid.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    # Prefer guide page
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    # Fallback: any 9087 icpsp-web-pc page
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and ":9087/icpsp-web-pc" in u:
            return p["webSocketDebuggerUrl"], u
    # Last resort: any page
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, ""


def ev(ws_url: str, expr: str, timeout_ms: int = 90000):
    ws = websocket.create_connection(ws_url, timeout=25)
    ws.settimeout(2.0)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": True,
                        "timeout": timeout_ms,
                    },
                }
            )
        )
        end = time.time() + max(30, timeout_ms / 1000 + 20)
        while time.time() < end:
            try:
                m = json.loads(ws.recv())
            except Exception:
                continue
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")
        return {"error": "cdp_eval_timeout"}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    ws, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    rec["steps"].append({"step": "pick", "data": {"url": cur}})
    if not ws:
        rec["error"] = "no_ws"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    # 1) Navigate to guide once (no clicking)
    rec["steps"].append({"step": "nav_guide", "data": ev(ws, f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", 30000)})
    time.sleep(5)

    # 2) One-shot API probe inside page context
    js = r"""(async function(){
      function walk(vm,d){
        if(!vm||d>22) return null;
        var n=(vm.$options&&vm.$options.name)||'';
        if(n==='index' && vm.$api && vm.$api.guide) return vm;
        for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
        return null;
      }
      function safe(v){try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);}}
      async function call(fn,arg,name){
        if(typeof fn!=='function') return {name:name,ok:false,err:'no_method'};
        try{
          var p=fn(arg);
          if(p&&typeof p.then==='function') p=await p;
          return {name:name,ok:true,r:safe(p)};
        }catch(e){
          return {name:name,ok:false,err:String(e),code:e&&e.code,data:safe(e&&e.data),resp:safe(e&&e.response)};
        }
      }
      function deepCollect(obj, out, depth){
        if(!obj||depth>7) return;
        if(Array.isArray(obj)){ for(var i=0;i<obj.length;i++) deepCollect(obj[i], out, depth+1); return; }
        if(typeof obj!=='object') return;
        for(var k in obj){
          var v=obj[k];
          if(v===null||v===undefined) continue;
          var lk=(k+'').toLowerCase();
          if((lk.indexOf('nameid')>=0||lk.indexOf('serial')>=0||lk.indexOf('reserve')>=0||lk.indexOf('number')>=0||lk.indexOf('qmb')>=0) && (typeof v==='string'||typeof v==='number')){
            out.push({k:k,v:String(v)});
          }
          if(typeof v==='object') deepCollect(v, out, depth+1);
        }
      }
      var app=document.getElementById('app');
      var vm=walk(app&&app.__vue__,0);
      if(!vm) return {ok:false,err:'no_guide_vm',href:location.href,hash:location.hash,title:document.title};
      var g=vm.$api.guide;
      var base={
        entType:'4540',
        distCode:'450921',
        streetCode:'450921',
        namePre:'玉林市',
        nameMark:'智信五金',
        industry:'五金批发',
        mainBusinessDesc:'五金批发',
        organize:'市（个人独资）',
        nameCode:'0'
      };
      var calls=[];
      calls.push(await call(g.getOrganizeList&&g.getOrganizeList.bind(g), {entType:'4540'}, 'getOrganizeList'));
      calls.push(await call(g.queryNameEntTypeCfgByEntTypeQmb&&g.queryNameEntTypeCfgByEntTypeQmb.bind(g), {entType:'4540'}, 'queryNameEntTypeCfgByEntTypeQmb'));
      calls.push(await call(g.checkNamePrefixList&&g.checkNamePrefixList.bind(g), {entType:'4540',distCode:base.distCode}, 'checkNamePrefixList'));
      calls.push(await call(g.preCheckCompanyName&&g.preCheckCompanyName.bind(g), base, 'preCheckCompanyName'));
      calls.push(await call(g.checkCompanyName&&g.checkCompanyName.bind(g), base, 'checkCompanyName'));
      calls.push(await call(g.generateCompanyName&&g.generateCompanyName.bind(g), base, 'generateCompanyName'));
      calls.push(await call(g.startGenerateCompanyName&&g.startGenerateCompanyName.bind(g), base, 'startGenerateCompanyName'));
      calls.push(await call(g.getGenerateCompanyNameRedis&&g.getGenerateCompanyNameRedis.bind(g), {}, 'getGenerateCompanyNameRedis'));
      calls.push(await call(g.getGenerateCompanyInfoRedis&&g.getGenerateCompanyInfoRedis.bind(g), {}, 'getGenerateCompanyInfoRedis'));
      calls.push(await call(g.saveNameMarkInfo&&g.saveNameMarkInfo.bind(g), base, 'saveNameMarkInfo'));

      var hits=[];
      for(var i=0;i<calls.length;i++){
        var c=calls[i];
        if(c&&c.r) deepCollect(c.r, hits, 0);
      }
      var uniq={}, dedup=[];
      for(var j=0;j<hits.length;j++){
        var key=hits[j].k+'='+hits[j].v;
        if(!uniq[key]){ uniq[key]=1; dedup.push(hits[j]); }
      }
      var picked = dedup.find(function(x){ return (x.k||'').toLowerCase().indexOf('nameid')>=0; }) || null;
      return {ok:true,href:location.href,hash:location.hash,title:document.title,base:base,calls:calls,hits:dedup.slice(0,30),picked:picked};
    })()"""
    rec["steps"].append({"step": "probe", "data": ev(ws, js, 120000)})

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

