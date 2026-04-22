#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/final_breakthrough_push_next.json")


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=10):
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
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}, timeout=12)
        return (((r or {}).get("result") or {}).get("value"))

    def net(self, sec=6):
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
    rec["steps"].append({"step": "state_before", "data": c.ev(r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,600)};})()""")})
    rec["steps"].append(
        {
            "step": "fill_and_click_listener",
            "data": c.ev(
                r"""(async function(){
                  function walk(vm,d){if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}return null;}
                  function clickLabel(t){
                    var labels=[...document.querySelectorAll('label.tni-radio,.tni-radio,.tni-radio__label')].filter(n=>n.offsetParent!==null);
                    for(var n of labels){var tx=(n.textContent||'').replace(/\s+/g,' ').trim();if(tx===t||tx.indexOf(t)>=0){(n.closest('label.tni-radio,.tni-radio')||n).click();return tx;}}
                    return null;
                  }
                  var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                  if(!vm) return {ok:false,msg:'no_vm'};
                  var s1=clickLabel('个人独资企业');
                  var s2=clickLabel('未申请');
                  vm.form=vm.form||{};
                  vm.$set(vm.form,'entType','4540');
                  vm.$set(vm.form,'nameCode','0');
                  vm.$set(vm.form,'havaAdress','0');
                  vm.$set(vm.form,'distCode','450102');
                  vm.$set(vm.form,'streetCode','450102');
                  vm.$set(vm.form,'streetName','兴宁区');
                  vm.$set(vm.form,'address','兴宁区');
                  vm.$set(vm.form,'detAddress','容州大道88号');
                  // input sync for address visible control
                  var ins=[...document.querySelectorAll('input.el-input__inner,input')].filter(x=>x.offsetParent!==null&&!x.disabled);
                  if(ins.length){
                    var target=ins[ins.length-1];
                    var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    setter.call(target,'兴宁区');
                    target.dispatchEvent(new Event('input',{bubbles:true}));
                    target.dispatchEvent(new Event('change',{bubbles:true}));
                  }
                  var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!btn) return {ok:false,msg:'no_btn',s1:s1,s2:s2,form:vm.form};
                  var bvm=btn.__vue__;
                  var fn=bvm&&(bvm.$listeners||{}).click;
                  var call='none';
                  if(fn){
                    try{
                      var r=fn({type:'click',target:btn,currentTarget:btn});
                      call='listener_click_called';
                      if(r&&typeof r.then==='function'){
                        try{await r; call='listener_click_resolved';}
                        catch(e){call='listener_click_rejected:'+String(e);}
                      }
                    }catch(e){call='listener_click_throw:'+String(e);}
                  }else{
                    btn.click(); call='btn_click';
                  }
                  return {ok:true,s1:s1,s2:s2,call:call,btn:{cls:(btn.className||'')+'',disabled:!!btn.disabled},form:vm.form};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "net_after", "data": c.net(8)})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,errors:errs.slice(0,10)};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

