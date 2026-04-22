#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_set_personal_type_then_next.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=8):
        if params is None:
            params = {}
        my_id = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == my_id:
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr, timeout=60000):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}, timeout=10)
        return (((r or {}).get("result") or {}).get("value"))

    def collect_network(self, sec=4.0):
        reqs, resps = [], []
        end = time.time() + sec
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                req = p.get("request", {})
                reqs.append({"url": (req.get("url") or "")[:260], "method": req.get("method"), "postData": (req.get("postData") or "")[:300]})
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                res = p.get("response", {})
                resps.append({"url": (res.get("url") or "")[:260], "status": res.get("status")})
        return {"reqs": reqs, "resps": resps}

    def close(self):
        self.ws.close()


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Page.enable", {})
    c.call("Network.enable", {})
    c.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}")
    time.sleep(3)

    rec["steps"].append({"step": "network_before", "data": c.collect_network(1.5)})
    rec["steps"].append(
        {
            "step": "set_personal_type_and_required",
            "data": c.ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1); if(r) return r;}
                    return null;
                  }
                  function clickText(t){
                    var nodes=[...document.querySelectorAll('label,span,div')].filter(n=>n.offsetParent!==null);
                    for(var n of nodes){
                      var tx=(n.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx===t||tx.indexOf(t)>=0){ n.click(); return tx; }
                    }
                    return null;
                  }
                  var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};
                  var c1=clickText('个人独资企业');
                  var c2=clickText('未申请');
                  vm.form = vm.form || {};
                  vm.$set(vm.form,'entType','4540');
                  vm.$set(vm.form,'nameCode','0');
                  vm.$set(vm.form,'havaAdress','1');
                  vm.$set(vm.form,'distCode','450102');
                  vm.$set(vm.form,'streetName','兴宁区');
                  vm.$set(vm.form,'address','兴宁区');
                  vm.$set(vm.form,'detAddress','容州大道88号');
                  try{ vm.checkchange && vm.checkchange(); }catch(e){}
                  try{ vm.validateEntType && vm.validateEntType(); }catch(e){}
                  return {ok:true,clickType:c1,clickNameType:c2,form:vm.form};
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "next_click",
            "data": c.ev(
                r"""(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);if(!b)return {ok:false};b.click();return {ok:true,text:(b.textContent||'').replace(/\s+/g,' ').trim()};})()"""
            ),
        }
    )
    time.sleep(1.0)
    rec["steps"].append({"step": "network_after", "data": c.collect_network(5.0)})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,600)};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

