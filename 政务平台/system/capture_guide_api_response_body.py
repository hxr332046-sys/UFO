#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/capture_guide_api_response_body.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=25)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=12):
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

    def ev(self, expr, timeout=90000):
        msg = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            timeout=15,
        )
        return ((msg.get("result") or {}).get("result") or {}).get("value")

    def collect_with_bodies(self, sec=10):
        end = time.time() + sec
        reqs = []
        resps = []
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            m = msg.get("method")
            if m == "Network.requestWillBeSent":
                p = msg.get("params", {})
                r = p.get("request", {})
                reqs.append(
                    {
                        "requestId": p.get("requestId"),
                        "url": (r.get("url") or "")[:260],
                        "method": r.get("method"),
                        "postData": (r.get("postData") or "")[:1200],
                    }
                )
            elif m == "Network.responseReceived":
                p = msg.get("params", {})
                r = p.get("response", {})
                rid = p.get("requestId")
                body = None
                if rid and "/icpsp-api/" in (r.get("url") or ""):
                    b = self.call("Network.getResponseBody", {"requestId": rid}, timeout=5)
                    body = ((b.get("result") or {}).get("body") or "")[:60000]
                resps.append({"requestId": rid, "url": (r.get("url") or "")[:260], "status": r.get("status"), "body": body})
        return {"reqs": reqs, "resps": resps}

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main():
    ws, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "picked_url": cur, "steps": []}
    if not ws:
        rec["error"] = "no_ws"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Page.enable", {})
    c.call("Network.enable", {})
    c.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", timeout=20000)
    time.sleep(4)
    rec["steps"].append({"step": "before", "data": c.ev(r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,900)};})()""")})
    rec["steps"].append(
        {
            "step": "act",
            "data": c.ev(
                r"""(async function(){
                  function clickBtn(kw){
                    var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&!x.disabled&&((x.textContent||'').replace(/\s+/g,'').indexOf(kw.replace(/\s+/g,''))>=0));
                    if(!b) return false;
                    b.click(); return true;
                  }
                  function clickText(kw){
                    var nodes=[...document.querySelectorAll('label,.tni-radio,.tni-radio__label,span,div')].filter(x=>x.offsetParent!==null);
                    for(var n of nodes){
                      var t=(n.textContent||'').replace(/\s+/g,' ').trim();
                      if(t===kw||t.indexOf(kw)>=0){
                        ['mousedown','mouseup','click'].forEach(function(tp){n.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));});
                        return true;
                      }
                    }
                    return false;
                  }
                  for(var i=0;i<3;i++){clickBtn('关 闭'); clickBtn('确定'); await new Promise(function(r){setTimeout(r,200);});}
                  clickText('个人独资企业');
                  clickText('未申请');
                  function walk(vm,d){
                    if(!vm||d>15) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index'&&typeof vm.flowSave==='function') return vm;
                    for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r)return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(vm&&vm.form){
                    vm.$set(vm.form,'entType','4540');
                    vm.$set(vm.form,'nameCode','0');
                    vm.$set(vm.form,'havaAdress','0');
                    vm.$set(vm.form,'distCode','450102');
                    vm.$set(vm.form,'streetCode','450102');
                    vm.$set(vm.form,'streetName','兴宁区');
                    vm.$set(vm.form,'address','兴宁区');
                    vm.$set(vm.form,'detAddress','容州大道88号');
                  }
                  var next=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(next&&next.__vue__&&next.__vue__.$listeners&&next.__vue__.$listeners.click){
                    try{
                      var p=next.__vue__.$listeners.click({type:'click',target:next,currentTarget:next});
                      if(p&&typeof p.then==='function'){try{await p;}catch(e){}}
                    }catch(e){}
                  }else if(next){ next.click(); }
                  await new Promise(function(r){setTimeout(r,500);});
                  clickBtn('确定');
                  return {ok:true};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "network", "data": c.collect_with_bodies(12)})
    rec["steps"].append({"step": "after", "data": c.ev(r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,900)};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
