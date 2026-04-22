#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
guide/base 单次“未申请 -> 下一步”回放，并抓取真实请求/响应包（XHR/fetch hook）。
用于给出“数据包方式打通”的证据，不依赖 CDP Network 事件。
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_replay_guide_base_once.json")


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

    def call(self, method, params=None, timeout=15):
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

    def ev(self, expr: str, timeout_ms=90000):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            timeout=15,
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
                "step": "install_hook",
                "data": c.ev(
                    r"""(function(){
                      window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
                      function pushOne(x){
                        try{
                          x.ts = Date.now();
                          window.__ufo_cap.items.push(x);
                          if(window.__ufo_cap.items.length>120) window.__ufo_cap.items.shift();
                        }catch(e){}
                      }
                      if(!window.__ufo_cap.installed){
                        var XO = XMLHttpRequest.prototype.open;
                        var XS = XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.open = function(m,u){ this.__ufo={m:m,u:u}; return XO.apply(this, arguments); };
                        XMLHttpRequest.prototype.send = function(body){
                          var self=this;
                          try{
                            var u=(self.__ufo&&self.__ufo.u)||'';
                            if(String(u).indexOf('/icpsp-api/')>=0){
                              pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u,body:String(body||'').slice(0,30000)});
                              self.addEventListener('loadend', function(){
                                pushOne({t:'xhr_end',u:u,status:self.status,resp:String(self.responseText||'').slice(0,30000)});
                              });
                            }
                          }catch(e){}
                          return XS.apply(this, arguments);
                        };
                        var OF = window.fetch;
                        if(typeof OF === 'function'){
                          window.fetch = function(input, init){
                            try{
                              var u = (typeof input==='string') ? input : (input && input.url) || '';
                              if(String(u).indexOf('/icpsp-api/')>=0){
                                var m = (init && init.method) || 'GET';
                                var b = (init && init.body) ? String(init.body).slice(0,30000) : '';
                                pushOne({t:'fetch',m:m,u:u,body:b});
                                return OF.apply(this, arguments).then(function(res){
                                  try{
                                    return res.clone().text().then(function(txt){
                                      pushOne({t:'fetch_end',u:u,status:res.status,resp:String(txt||'').slice(0,30000)});
                                      return res;
                                    });
                                  }catch(e){
                                    return res;
                                  }
                                });
                              }
                            }catch(e){}
                            return OF.apply(this, arguments);
                          };
                        }
                        window.__ufo_cap.installed = true;
                      }
                      var prev=(window.__ufo_cap.items||[]).length;
                      window.__ufo_cap.items = [];
                      return {ok:true,prev:prev};
                    })()"""
                ),
            }
        )

        rec["steps"].append(
            {
                "step": "prefill_and_click_path",
                "data": c.ev(
                    r"""(function(){
                      function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                      function vis(x){return !!(x&&x.offsetParent!==null);}
                      function click(el){if(!el)return false; ['mousedown','mouseup','click'].forEach(function(tp){el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));}); return true;}
                      function walk(vm,d,p){ if(!vm||d>20) return null; if(p(vm)) return vm; var ch=vm.$children||[]; for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1,p); if(r) return r;} return null; }
                      var out={};
                      // prefill guide form through vm to satisfy "下一步" guards
                      try{
                        var app=document.getElementById('app');
                        var root=app&&app.__vue__;
                        var idx=walk(root,0,function(v){return (v.$options&&v.$options.name)==='index' && v.$data && v.$data.form;});
                        if(idx){
                          idx.form = idx.form || {};
                          if(typeof idx.$set==='function'){
                            idx.$set(idx.form,'entType','4540');
                            idx.$set(idx.form,'nameCode','0');
                            idx.$set(idx.form,'havaAdress','0');
                            idx.$set(idx.form,'distCode','450102');
                            idx.$set(idx.form,'streetCode','450102');
                            idx.$set(idx.form,'streetName','兴宁区');
                            idx.$set(idx.form,'detAddress','容州大道88号');
                            idx.$set(idx.form,'address','兴宁区');
                          }else{
                            idx.form.entType='4540';
                            idx.form.nameCode='0';
                            idx.form.havaAdress='0';
                            idx.form.distCode='450102';
                            idx.form.streetCode='450102';
                            idx.form.streetName='兴宁区';
                            idx.form.detAddress='容州大道88号';
                            idx.form.address='兴宁区';
                          }
                          if(typeof idx.$forceUpdate==='function') idx.$forceUpdate();
                          out.prefill=true;
                        }else{
                          out.prefill=false;
                        }
                      }catch(e){
                        out.prefill_err=String(e);
                      }
                      var r=[...document.querySelectorAll('label,span,div')].find(x=>vis(x)&&clean(x.textContent).indexOf('未申请')>=0);
                      out.pickNotApply = !!r; if(r) click(r);
                      var n=[...document.querySelectorAll('button,.el-button,span,div')].find(x=>vis(x)&&clean(x.textContent).replace(/\s+/g,'').indexOf('下一步')>=0);
                      out.clickNext = !!n; if(n) click(n.closest && n.closest('button,.el-button') ? n.closest('button,.el-button') : n);
                      return out;
                    })()"""
                ),
            }
        )

        time.sleep(3)
        rec["steps"].append(
            {
                "step": "captured_packets",
                "data": c.ev(r"""(function(){var c=window.__ufo_cap||{items:[]}; return {count:(c.items||[]).length,items:(c.items||[])};})()"""),
            }
        )
        rec["steps"].append(
            {
                "step": "state_after",
                "data": c.ev(
                    r"""(function(){
                      var txt=(document.body&&document.body.innerText)||'';
                      return {href:location.href,hash:location.hash,hasNamePrompt:txt.indexOf('请选择是否需要名称')>=0,hasCore:location.href.indexOf('/core.html#')>=0};
                    })()"""
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

