#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_popup_targeted_close.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = pick_ws()
    rec["steps"].append({"step": "start", "data": url})
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append(
        {
            "step": "hook",
            "data": ev(
                ws,
                r"""(function(){
                  window.__popup_cap={req:[],resp:[]};
                  if(!window.__popup_hook){
                    window.__popup_hook=true;
                    var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
                    XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
                    XMLHttpRequest.prototype.send=function(b){
                      var u=this.__u||'';
                      if(u.indexOf('/icpsp-api/')>=0){
                        window.__popup_cap.req.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,700)});
                        var self=this; self.addEventListener('load',function(){
                          window.__popup_cap.resp.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,1000)});
                        });
                      }
                      return os.apply(this,arguments);
                    };
                  }
                  return true;
                })()""",
            ),
        }
    )

    # try targeted popup close + confirm + option + next
    rec["steps"].append(
        {
            "step": "targeted_actions",
            "data": ev(
                ws,
                r"""(async function(){
                  var out=[];
                  function clickInDialog(keyword){
                    var wrappers=[...document.querySelectorAll('.el-dialog__wrapper')].filter(w=>w.offsetParent!==null);
                    for(var w of wrappers){
                      var els=[...w.querySelectorAll('button,.el-button,.el-dialog__headerbtn,.el-dialog__close,span,div')].filter(e=>e.offsetParent!==null);
                      for(var e of els){
                        var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                        var cls=(e.className||'')+'';
                        if(tx.indexOf(keyword)>=0 || cls.indexOf(keyword)>=0){
                          e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                          return true;
                        }
                      }
                    }
                    return false;
                  }
                  function clickGlobal(keyword){
                    var els=[...document.querySelectorAll('button,.el-button,label,span,div,a,li')].filter(e=>e.offsetParent!==null);
                    for(var e of els){
                      var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx===keyword || tx.indexOf(keyword)>=0){
                        e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                        return true;
                      }
                    }
                    return false;
                  }
                  if(clickInDialog('el-icon-close')||clickInDialog('关闭')) out.push('dialog_close');
                  await new Promise(r=>setTimeout(r,500));
                  if(clickInDialog('确定')) out.push('dialog_ok');
                  await new Promise(r=>setTimeout(r,500));
                  if(clickGlobal('未申请')) out.push('select_not_apply');
                  await new Promise(r=>setTimeout(r,500));
                  if(clickGlobal('下一步')) out.push('next');
                  await new Promise(r=>setTimeout(r,800));
                  if(clickGlobal('确定')) out.push('confirm');
                  await new Promise(r=>setTimeout(r,2500));
                  return {
                    actions:out,
                    href:location.href,hash:location.hash,
                    text:(document.body.innerText||'').slice(0,1000),
                    reqs:(window.__popup_cap&&window.__popup_cap.req||[]).slice(-8),
                    resps:(window.__popup_cap&&window.__popup_cap.resp||[]).slice(-8)
                  };
                })()""",
            ),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

