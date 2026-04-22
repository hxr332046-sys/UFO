#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_set_streetcode_then_next.json")


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=8):
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
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}, timeout=10)
        return (((r or {}).get("result") or {}).get("value"))

    def net(self, sec=4):
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
                reqs.append({"url": (req.get("url") or "")[:260], "method": req.get("method"), "postData": (req.get("postData") or "")[:400]})
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                res = p.get("response", {})
                resps.append({"url": (res.get("url") or "")[:260], "status": res.get("status")})
        return {"reqs": reqs, "resps": resps}


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
    c.call("Network.enable", {})
    rec["steps"].append({"step": "net_before", "data": c.net(1.5)})
    rec["steps"].append(
        {
            "step": "set_form_full",
            "data": c.ev(
                r"""(function(){
                  function walk(vm,d){if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var c of (vm.$children||[])){var r=walk(c,d+1);if(r)return r;}return null;}
                  var vm=(function(){var app=document.getElementById('app');return app&&app.__vue__?walk(app.__vue__,0):null;})();
                  if(!vm) return {ok:false,msg:'no_vm'};
                  vm.form=vm.form||{};
                  // cascader 绑定通常依赖 distList（省/市/区/街道）
                  vm.distList=['450000','450100','450102','450102'];
                  vm.$set(vm.form,'distList',vm.distList);
                  vm.$set(vm.form,'entType','4540');
                  vm.$set(vm.form,'nameCode','0');
                  vm.$set(vm.form,'havaAdress','1');
                  vm.$set(vm.form,'distCode','450102');
                  vm.$set(vm.form,'streetCode','450102');
                  vm.$set(vm.form,'streetName','兴宁区');
                  vm.$set(vm.form,'address','兴宁区');
                  vm.$set(vm.form,'detAddress','容州大道88号');
                  // 点击精准label避免点击到容器
                  function clickLabel(t){
                    var labels=[...document.querySelectorAll('label.tni-radio,.tni-radio')].filter(n=>n.offsetParent!==null);
                    for(var n of labels){var tx=(n.textContent||'').replace(/\s+/g,' ').trim();if(tx===t||tx.indexOf(t)>=0){n.click();return tx;}}
                    return null;
                  }
                  var a=clickLabel('个人独资企业');
                  var b=clickLabel('未申请');
                  return {ok:true,a:a,b:b,form:vm.form};
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "click_next",
            "data": c.ev(
                r"""(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,' ').trim()==='下一步'&&!x.disabled);if(!b)return {ok:false};b.click();return {ok:true};})()"""
            ),
        }
    )
    time.sleep(1)
    rec["steps"].append({"step": "net_after", "data": c.net(6)})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

