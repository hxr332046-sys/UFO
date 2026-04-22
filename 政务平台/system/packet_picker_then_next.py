#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_picker_then_next.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=20)
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
                reqs.append(
                    {
                        "url": (req.get("url") or "")[:260],
                        "method": req.get("method"),
                        "postData": (req.get("postData") or "")[:500],
                        "type": p.get("type"),
                    }
                )
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                res = p.get("response", {})
                resps.append({"url": (res.get("url") or "")[:260], "status": res.get("status"), "type": p.get("type")})
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

    # 先确保选择了 个人独资企业 + 未申请
    rec["steps"].append(
        {
            "step": "set_type_and_name_code",
            "data": c.ev(
                r"""(function(){
                  function clickByText(txt){
                    var nodes=[...document.querySelectorAll('label,span,div')].filter(n=>n.offsetParent!==null);
                    for(var n of nodes){
                      var t=(n.textContent||'').replace(/\s+/g,' ').trim();
                      if(t===txt||t.indexOf(txt)>=0){
                        var n2=n.closest('label,.tni-radio,.el-radio')||n;
                        ['mousedown','mouseup','click'].forEach(function(tp){n2.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));});
                        return {ok:true,text:t,tag:n2.tagName,cls:(n2.className||'')+''};
                      }
                    }
                    return {ok:false,text:txt};
                  }
                  return {
                    enterprise:clickByText('个人独资企业'),
                    nameCode:clickByText('未申请')
                  };
                })()"""
            ),
        }
    )

    # 处理地址 picker
    rec["steps"].append(
        {
            "step": "picker_select",
            "data": c.ev(
                r"""(async function(){
                  function sleep(ms){return new Promise(r=>setTimeout(r,ms));}
                  function openAddressPicker(){
                    var items=document.querySelectorAll('.el-form-item');
                    for(var i=0;i<items.length;i++){
                      var lb=items[i].querySelector('.el-form-item__label');
                      var tx=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx.indexOf('公司在哪里')>=0||tx.indexOf('企业住所')>=0||tx.indexOf('住所')>=0){
                        var inp=items[i].querySelector('input.el-input__inner,input');
                        if(inp){inp.click();return {ok:true,label:tx};}
                      }
                    }
                    // fallback: first visible input near step3
                    var inp2=[...document.querySelectorAll('input.el-input__inner,input')].find(x=>x.offsetParent!==null);
                    if(inp2){inp2.click();return {ok:true,label:'fallback_input'};}
                    return {ok:false};
                  }
                  function clickSample(name){
                    var pops=[...document.querySelectorAll('.tne-data-picker-popover')].filter(p=>p.offsetParent!==null);
                    for(var p of pops){
                      var samples=[...p.querySelectorAll('.sample-item,.item,li,span,div')].filter(x=>x.offsetParent!==null);
                      for(var s of samples){
                        var t=(s.textContent||'').replace(/\s+/g,' ').trim();
                        if(t===name||t.indexOf(name)>=0){
                          s.click();
                          return {ok:true,name:name,hit:t,cls:(s.className||'')+''};
                        }
                      }
                    }
                    return {ok:false,name:name};
                  }
                  var out={};
                  out.open=openAddressPicker();
                  await sleep(600);
                  out.gx=clickSample('广西壮族自治区');
                  await sleep(400);
                  out.nn=clickSample('南宁市');
                  await sleep(400);
                  out.qx=clickSample('兴宁区');
                  await sleep(600);
                  // sync detail address by VM/form fallback
                  try{
                    function walk(vm,d){
                      if(!vm||d>12) return null;
                      var n=(vm.$options&&vm.$options.name)||'';
                      if(n==='index'&&typeof vm.flowSave==='function') return vm;
                      for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r) return r;}
                      return null;
                    }
                    var app=document.getElementById('app');
                    var vm=app&&app.__vue__?walk(app.__vue__,0):null;
                    if(vm&&vm.form){
                      vm.$set(vm.form,'detAddress', vm.form.detAddress||'容州大道88号');
                    }
                    out.form=vm&&vm.form?vm.form:null;
                  }catch(e){out.formErr=String(e);}
                  return out;
                })()"""
            ),
        }
    )

    rec["steps"].append({"step": "network_before_next", "data": c.collect_network(1.5)})
    rec["steps"].append(
        {
            "step": "click_next",
            "data": c.ev(
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
                  if(!b) return {ok:false};
                  b.click(); return {ok:true,text:(b.textContent||'').replace(/\s+/g,' ').trim()};
                })()"""
            ),
        }
    )
    time.sleep(1.0)
    rec["steps"].append({"step": "network_after_next", "data": c.collect_network(6.0)})
    rec["steps"].append(
        {
            "step": "final_state",
            "data": c.ev(
                r"""(function(){
                  var txt=(document.body&&document.body.innerText)||'';
                  var errs=[...document.querySelectorAll('.el-form-item__error')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  return {href:location.href,hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,errors:errs.slice(0,10),text:txt.slice(0,500)};
                })()"""
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

