#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
纯数据包方式重放 guide/base 关键 API，做三分支单次验证：
1) nameCode=0（未申请）
2) nameCode=1（已办理预保留）
3) 绕过 qimingbao，仅测试 guide 链路
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_api_breakthrough_guide_base.json")
GUIDE_TARGET = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, ""


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method, params=None, timeout=16):
        if params is None:
            params = {}
        cid = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == cid:
                return msg
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr: str, timeout_ms=120000):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            timeout=20,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "page": cur, "steps": []}
    if not ws_url:
        rec["error"] = "no_guide_base_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws_url)
    try:
        rec["steps"].append(
            {
                "step": "force_target_route",
                "data": c.ev(f"location.href={json.dumps(GUIDE_TARGET, ensure_ascii=False)}"),
            }
        )
        time.sleep(4)
        rec["steps"].append(
            {
                "step": "install_hook",
                "data": c.ev(
                    r"""(function(){
                      window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
                      function pushOne(x){
                        try{x.ts=Date.now();window.__ufo_cap.items.push(x);if(window.__ufo_cap.items.length>120)window.__ufo_cap.items.shift();}catch(e){}
                      }
                      if(!window.__ufo_cap.installed){
                        var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.open=function(m,u){this.__ufo={m:m,u:u};return XO.apply(this,arguments);};
                        XMLHttpRequest.prototype.send=function(body){
                          var self=this; var u=(self.__ufo&&self.__ufo.u)||'';
                          if(String(u).indexOf('/icpsp-api/')>=0){
                            pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u,body:String(body||'').slice(0,30000)});
                            self.addEventListener('loadend',function(){pushOne({t:'xhr_end',u:u,status:self.status,resp:String(self.responseText||'').slice(0,30000)});});
                          }
                          return XS.apply(this,arguments);
                        };
                        window.__ufo_cap.installed=true;
                      }
                      window.__ufo_cap.items=[];
                      return {ok:true};
                    })()"""
                ),
            }
        )

        # Directly call guide APIs with complete payloads (packet-driven).
        rec["steps"].append(
            {
                "step": "api_replay_branches",
                "data": c.ev(
                    r"""(async function(){
                      function walk(vm,d){
                        if(!vm||d>20) return null;
                        var n=(vm.$options&&vm.$options.name)||'';
                        if(n==='index' && vm.$api && vm.$api.guide) return vm;
                        var ch=vm.$children||[];
                        for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
                        return null;
                      }
                      function safe(v){ try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);} }
                      async function call(name, fn, arg){
                        if(typeof fn!=='function') return {name:name,ok:false,err:'no_method'};
                        try{
                          var r=fn(arg);
                          if(r&&typeof r.then==='function') r=await r;
                          return {name:name,ok:true,res:safe(r)};
                        }catch(e){
                          var out={name:name,ok:false,err:String(e)};
                          try{out.code=e&&e.code;}catch(_){}
                          try{out.data=safe(e&&e.data);}catch(_){}
                          try{out.response=safe(e&&e.response);}catch(_){}
                          return out;
                        }
                      }
                      var app=document.getElementById('app');
                      var vm=walk(app&&app.__vue__,0);
                      if(!vm) return {ok:false,err:'no_vm'};
                      var g=vm.$api.guide;
                      var q=(vm.$route&&vm.$route.query)||{};
                      function mkForm(nameCode){
                        return {
                          entType:'4540',
                          distCode:'450102',
                          streetCode:'450102',
                          nameCode:String(nameCode),
                          havaAdress:'0',
                          namePre:'广西',
                          nameMark:'星有',
                          industry:'5132',
                          industryName:'服装批发',
                          industrySpecial:'服装批发',
                          mainBusinessDesc:'服装批发',
                          organize:'分部（个人独资）',
                          address:'兴宁区',
                          detAddress:'容州大道88号'
                        };
                      }
                      function mkBasic(form){
                        return {
                          busiType:q.busiType||'02_4',
                          entType:'4540',
                          extra:'guideData',
                          vipChannel:q.vipChannel||null,
                          ywlbSign:q.ywlbSign||'',
                          busiId:q.busiId||'',
                          extraDto:JSON.stringify({extraDto:form})
                        };
                      }
                      async function runBranch(id, nameCode, withQimingbao){
                        var form=mkForm(nameCode);
                        var basic=mkBasic(form);
                        var establish=Object.assign({}, form, {gainError:'1', establishType:q.establishType||''});
                        var calls=[];
                        calls.push(await call('checkEstablishName', g.checkEstablishName&&g.checkEstablishName.bind(g), establish));
                        if(withQimingbao){
                          calls.push(await call('preProcessDeclare', g.preProcessDeclare&&g.preProcessDeclare.bind(g), basic));
                        }
                        calls.push(await call('queryExtraDto', g.queryExtraDto&&g.queryExtraDto.bind(g), basic));
                        var okAny = calls.some(function(x){
                          var rr = x && x.res;
                          return x && x.ok && rr && typeof rr === 'object' && rr.code === '00000';
                        });
                        return {branch:id,payload:{basic:basic,establish:establish},calls:calls,okAny:okAny};
                      }
                      var branches=[];
                      branches.push(await runBranch('A_nameCode0_with_qimingbao', 0, true));
                      branches.push(await runBranch('B_nameCode1_with_qimingbao', 1, true));
                      branches.push(await runBranch('C_nameCode0_no_qimingbao', 0, false));
                      var any00000 = branches.some(function(b){return !!b.okAny;});
                      return {ok:true,routeQuery:q,branches:branches,any00000:any00000};
                    })()"""
                ),
            }
        )

        time.sleep(2)
        rec["steps"].append(
            {
                "step": "captured_packets",
                "data": c.ev(r"""(function(){var c=window.__ufo_cap||{items:[]};return {count:(c.items||[]).length,items:(c.items||[])};})()"""),
            }
        )
        rec["steps"].append(
            {
                "step": "state_after",
                "data": c.ev(
                    r"""(function(){return {href:location.href,hash:location.hash};})()"""
                ),
            }
        )

        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
    finally:
        c.close()


if __name__ == "__main__":
    main()

