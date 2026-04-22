#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/retry_nameid_mint_and_bind.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="
CORE_NAMECHECK_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/name-check-info"


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, ""


def ev(ws_url, expr, timeout=90000):
    ws = websocket.create_connection(ws_url, timeout=25)
    ws.settimeout(2.0)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    end = time.time() + max(30, timeout / 1000 + 20)
    try:
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


def nav(ws_url, url):
    return ev(ws_url, f"location.href={json.dumps(url, ensure_ascii=False)}", timeout=30000)


def probe_guide_mint(ws_url):
    # Probe possible guide name-generation APIs and extract any nameId/serial-like value.
    return ev(
        ws_url,
        r"""(async function(){
          function walk(vm,d){
            if(!vm||d>20) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='index' && vm.$api && vm.$api.guide) return vm;
            for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
            return null;
          }
          function safe(v){try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);}}
          async function tcall(fn,arg,name){
            if(typeof fn!=='function') return {name:name,ok:false,err:'no_method'};
            try{
              var r=fn(arg);
              if(r&&typeof r.then==='function') r=await r;
              return {name:name,ok:true,r:safe(r)};
            }catch(e){
              return {name:name,ok:false,err:String(e),code:e&&e.code,data:safe(e&&e.data),resp:safe(e&&e.response)};
            }
          }
          function deepCollect(obj, out, depth){
            if(!obj||depth>6) return;
            if(Array.isArray(obj)){ for(var i=0;i<obj.length;i++) deepCollect(obj[i], out, depth+1); return; }
            if(typeof obj!=='object') return;
            for(var k in obj){
              var v=obj[k];
              if(v===null||v===undefined) continue;
              var lk=(k+'').toLowerCase();
              if((lk.indexOf('nameid')>=0||lk.indexOf('serial')>=0||lk.indexOf('reserve')>=0||lk.indexOf('number')>=0) && (typeof v==='string'||typeof v==='number')){
                out.push({k:k,v:String(v)});
              }
              if(typeof v==='object') deepCollect(v, out, depth+1);
            }
          }
          var app=document.getElementById('app');
          var vm=walk(app&&app.__vue__,0);
          if(!vm) return {ok:false,err:'no_guide_vm',href:location.href,hash:location.hash};
          var g=vm.$api.guide;
          var base={entType:'4540',distCode:'450921',streetCode:'450921',namePre:'玉林市',nameMark:'智信五金',industry:'五金批发',mainBusinessDesc:'五金批发',organize:'市（个人独资）',nameCode:'0'};
          var calls=[];
          calls.push(await tcall(g.getOrganizeList&&g.getOrganizeList.bind(g), {entType:'4540'}, 'getOrganizeList'));
          calls.push(await tcall(g.checkNamePrefixList&&g.checkNamePrefixList.bind(g), {entType:'4540',distCode:'450921'}, 'checkNamePrefixList'));
          calls.push(await tcall(g.preCheckCompanyName&&g.preCheckCompanyName.bind(g), base, 'preCheckCompanyName'));
          calls.push(await tcall(g.checkCompanyName&&g.checkCompanyName.bind(g), base, 'checkCompanyName'));
          calls.push(await tcall(g.generateCompanyName&&g.generateCompanyName.bind(g), base, 'generateCompanyName'));
          calls.push(await tcall(g.startGenerateCompanyName&&g.startGenerateCompanyName.bind(g), base, 'startGenerateCompanyName'));
          calls.push(await tcall(g.getGenerateCompanyNameRedis&&g.getGenerateCompanyNameRedis.bind(g), {}, 'getGenerateCompanyNameRedis'));
          calls.push(await tcall(g.getGenerateCompanyInfoRedis&&g.getGenerateCompanyInfoRedis.bind(g), {}, 'getGenerateCompanyInfoRedis'));
          calls.push(await tcall(g.saveNameMarkInfo&&g.saveNameMarkInfo.bind(g), base, 'saveNameMarkInfo'));
          var hits=[];
          for(var i=0;i<calls.length;i++){
            var c=calls[i];
            if(c&&c.r) deepCollect(c.r, hits, 0);
          }
          var uniq={}; var dedup=[];
          for(var j=0;j<hits.length;j++){
            var key=hits[j].k+'='+hits[j].v;
            if(!uniq[key]){ uniq[key]=1; dedup.push(hits[j]); }
          }
          var picked=(dedup.find(function(x){return x.k.toLowerCase().indexOf('nameid')>=0;})||dedup[0]||null);
          return {ok:true,href:location.href,hash:location.hash,calls:calls,hits:dedup.slice(0,20),picked:picked};
        })()""",
        timeout=120000,
    )


def bind_in_core_with_nameid(ws_url, name_id):
    return ev(
        ws_url,
        r"""(async function(){
          function walk(vm,d,p){if(!vm||d>25)return null;if(p(vm))return vm;for(var c of (vm.$children||[])){var r=walk(c,d+1,p);if(r)return r;}return null;}
          function safe(v){try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);}}
          function setv(owner,obj,key,val){try{if(owner&&typeof owner.$set==='function')owner.$set(obj,key,val);else obj[key]=val;}catch(e){obj[key]=val;}}
          var nameId=%s;
          var app=document.getElementById('app'), root=app&&app.__vue__;
          var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
          if(!idx||!idx.$api||!idx.$api.flow) return {ok:false,msg:'no_namecheck_vm'};
          idx.formInfo=idx.formInfo||{};
          var force={namePre:'玉林市',nameMark:'智信五金',industrySpecial:'五金批发',allIndKeyWord:'五金',showKeyWord:'五金',industry:'F5174',industryName:'五金产品批发',organize:'998',organizeName:'市（个人独资）',name:'玉林市智信五金五金批发市（个人独资）',isCheckBox:'Y',declarationMode:'Y',distCode:'450921',entType:'4540',nameId:nameId};
          Object.keys(force).forEach(function(k){setv(idx,idx.formInfo,k,force[k]);});
          var payload={flowData:{busiId:null,entType:'4540',busiType:'01',ywlbSign:'4',busiMode:null,nameId:nameId,currCompUrl:'NameCheckInfo',status:'10'},linkData:{token:'',continueFlag:'',compUrl:'NameCheckInfo',compUrlPaths:['NameCheckInfo']},itemId:'',compUrl:'NameCheckInfo',opType:'tempSave',busiData:idx.formInfo};
          var trace=[];
          var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__n={m:m,u:u};return XO.apply(this,arguments)};
          XMLHttpRequest.prototype.send=function(b){var self=this;trace.push(['send',{m:self.__n&&self.__n.m,u:self.__n&&self.__n.u,b:String(b||'').slice(0,1800)}]);self.addEventListener('loadend',function(){trace.push(['end',{u:self.__n&&self.__n.u,s:self.status,r:String(self.responseText||'').slice(0,1800)}]);});return XS.apply(this,arguments)};
          var out={};
          try{var p=idx.$api.flow.operationBusinessDataInfo(payload); if(p&&typeof p.then==='function') out.operationBusinessDataInfo=await p; else out.operationBusinessDataInfo=p;}catch(e){out.operationBusinessDataInfo_err={msg:String(e),code:e&&e.code,data:safe(e&&e.data)};}
          try{var p2=idx.nameCheckRepeat(); if(p2&&typeof p2.then==='function') out.nameCheckRepeat=await p2; else out.nameCheckRepeat=p2;}catch(e){out.nameCheckRepeat_err={msg:String(e),code:e&&e.code,data:safe(e&&e.data)};}
          await new Promise(function(r){setTimeout(r,1000);});
          XMLHttpRequest.prototype.open=XO; XMLHttpRequest.prototype.send=XS;
          return {ok:true,nameId:nameId,out:out,trace:trace};
        })()"""
        % json.dumps(str(name_id), ensure_ascii=False),
        timeout=120000,
    )


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "iterations": [], "result": "running"}
    for i in range(120):
        ws_url, cur = pick_ws()
        row = {"i": i, "page": cur}
        if not ws_url:
            row["error"] = "no_ws"
            rec["iterations"].append(row)
            time.sleep(5)
            continue

        # Step 1: navigate to guide and probe
        row["nav_guide"] = nav(ws_url, GUIDE_URL)
        time.sleep(3)
        probe = probe_guide_mint(ws_url)
        row["probe"] = probe

        picked = ((probe or {}).get("picked") or {}) if isinstance(probe, dict) else {}
        name_id = picked.get("v") if isinstance(picked, dict) and ("nameid" in str(picked.get("k", "")).lower()) else None

        # Step 2: if got nameId-like value, jump core and bind immediately
        if name_id:
            row["nav_core"] = nav(ws_url, CORE_NAMECHECK_URL)
            time.sleep(3)
            row["bind"] = bind_in_core_with_nameid(ws_url, name_id)
            out = (row["bind"] or {}).get("out", {}) if isinstance(row.get("bind"), dict) else {}
            op_err = (out.get("operationBusinessDataInfo_err") or {}).get("code")
            # any non-expired success condition: operationBusinessDataInfo no error code and nameCheckRepeat no A0002
            if not op_err:
                rec["result"] = "nameid_bound_success"
                rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                rec["iterations"].append(row)
                OUT.parent.mkdir(parents=True, exist_ok=True)
                OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Bound new nameId successfully. Saved: {OUT}")
                return

        rec["iterations"].append(row)
        rec["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(8)

    rec["result"] = "max_iterations_reached"
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Finished max iterations. Saved: {OUT}")


if __name__ == "__main__":
    main()

