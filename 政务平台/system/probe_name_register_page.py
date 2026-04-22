#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path
import time

import requests
import websocket

OUT = Path("G:/UFO/政务平台/data/probe_name_register_page.json")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = None
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "fromProject=name-register" in u:
            target = p
            break
    rec = {"steps": []}
    if not target:
        rec["error"] = "no_name_register_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=8)

    def ev(expr, timeout=20000):
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")

    s1 = ev(
        r"""(function(){
          var app=document.getElementById('app');
          var btns=Array.from(document.querySelectorAll('button,.el-button,a,div')).filter(function(e){return e.offsetParent!==null;}).map(function(e){return (e.textContent||'').trim();}).filter(Boolean).slice(0,60);
          return {href:location.href,hash:location.hash,hasVue:!!(app&&app.__vue__),buttons:btns};
        })()"""
    )
    rec["steps"].append({"step": "S1_snapshot", "data": s1})

    s2 = ev(
        r"""(function(){
          window.__nr_probe={reqs:[],resps:[]};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments)};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('/icpsp-api/')>=0){
              window.__nr_probe.reqs.push({m:this.__m||'GET',u:u.slice(0,220),len:(b||'').length,body:(b||'').slice(0,240)});
              var self=this;
              self.addEventListener('load',function(){window.__nr_probe.resps.push({u:u.slice(0,220),status:self.status,text:(self.responseText||'').slice(0,280)});});
            }
            return os.apply(this,arguments);
          };
          return {ok:true};
        })()"""
    )
    rec["steps"].append({"step": "S2_hook_xhr", "data": s2})

    s3 = ev(
        r"""(function(){
          // 尝试点击最可能触发业务初始化的按钮
          var pats=['开始办理','下一步','继续','同意','确认','设立登记','名称'];
          var els=Array.from(document.querySelectorAll('button,.el-button,a,div,span')).filter(function(e){return e.offsetParent!==null;});
          for(var p=0;p<pats.length;p++){
            for(var i=0;i<els.length;i++){
              var t=(els[i].textContent||'').trim();
              if(t&&t.indexOf(pats[p])>=0&&t.length<30){
                try{ els[i].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return {clicked:true,text:t,pat:pats[p]}; }catch(e){}
              }
            }
          }
          return {clicked:false};
        })()"""
    )
    rec["steps"].append({"step": "S3_click_candidate", "data": s3})
    time.sleep(6)

    s4 = ev(
        r"""(function(){
          return {href:location.href,hash:location.hash,probe:window.__nr_probe||null};
        })()"""
    )
    rec["steps"].append({"step": "S4_after_click", "data": s4})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

