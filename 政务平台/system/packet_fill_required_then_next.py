#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_fill_required_then_next.json")
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
                reqs.append({"url": (req.get("url") or "")[:260], "method": req.get("method"), "postData": (req.get("postData") or "")[:500]})
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
        rec["error"] = "no_guide_tab"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws)
    c.call("Page.enable", {})
    c.call("Network.enable", {})
    c.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}")
    time.sleep(3)

    rec["steps"].append({"step": "before_network", "data": c.collect_network(1.5)})
    rec["steps"].append(
        {
            "step": "fill_required_runtime",
            "data": c.ev(
                r"""(function(){
                  function walk(vm,d){
                    if(!vm||d>12) return null;
                    var n=(vm.$options&&vm.$options.name)||'';
                    if(n==='index' && typeof vm.flowSave==='function') return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1); if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};

                  function firstNode(tree){
                    if(!tree||!tree.length) return null;
                    var n=tree[0];
                    while(n&&n.children&&n.children.length) n=n.children[0];
                    return n;
                  }
                  var node=firstNode(vm.localdataTree||[]);
                  var distCode=(node&&((node.id||node.code||node.value||'')+''))||'';
                  var distName=(node&&((node.name||node.label||'')+''))||'';

                  vm.form = vm.form || {};
                  vm.$set(vm.form,'nameCode', vm.form.nameCode || '0');
                  vm.$set(vm.form,'havaAdress', vm.form.havaAdress || '1');
                  if(distCode) vm.$set(vm.form,'distCode', distCode);
                  if(distName) vm.$set(vm.form,'address', distName);
                  if(distName) vm.$set(vm.form,'streetName', distName);
                  vm.$set(vm.form,'detAddress', vm.form.detAddress || '容州大道88号');

                  // sync visible text inputs by label to触发前端校验链
                  var labels=['请选择平台、市、区、街道','请选择','街道'];
                  var ins=[...document.querySelectorAll('input.el-input__inner')].filter(i=>!i.disabled);
                  if(ins.length){
                    var i0=ins[ins.length-1];
                    var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    setter.call(i0, distName || '容县');
                    i0.dispatchEvent(new Event('input',{bubbles:true}));
                    i0.dispatchEvent(new Event('change',{bubbles:true}));
                  }

                  return {
                    ok:true,
                    distCode:vm.form.distCode||null,
                    address:vm.form.address||null,
                    detAddress:vm.form.detAddress||null,
                    form:vm.form
                  };
                })()"""
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "click_next",
            "data": c.ev(
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
                  if(!b) return {ok:false};
                  b.click();
                  return {ok:true,text:(b.textContent||'').replace(/\s+/g,' ').trim()};
                })()"""
            ),
        }
    )
    time.sleep(1.0)
    rec["steps"].append({"step": "after_network", "data": c.collect_network(5.0)})
    rec["steps"].append(
        {
            "step": "after_state",
            "data": c.ev(
                r"""(function(){var t=(document.body&&document.body.innerText)||'';return {href:location.href,hash:location.hash,hasYunbangban:t.indexOf('云帮办流程模式选择')>=0,hasNamePrompt:t.indexOf('请选择是否需要名称')>=0};})()"""
            ),
        }
    )

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

