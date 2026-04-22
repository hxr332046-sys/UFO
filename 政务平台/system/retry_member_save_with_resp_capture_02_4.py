#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/retry_member_save_with_resp_capture_02_4.json")


def ev(ws_url, expr, timeout=90000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        try:
            m = json.loads(ws.recv())
        except Exception:
            continue
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/member-post" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ws = pick_ws()
    if not ws:
        rec["error"] = "no_member_page"
    else:
        rec["hook"] = ev(
            ws,
            r"""(function(){
              window.__mcap={req:[],resp:[]};
              if(!window.__mcap_hooked){
                window.__mcap_hooked=true;
                var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments)};
                XMLHttpRequest.prototype.send=function(b){
                  var u=this.__u||'';
                  if(u.indexOf('/icpsp-api/')>=0){
                    window.__mcap.req.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,700)});
                    var self=this;
                    self.addEventListener('load',function(){
                      window.__mcap.resp.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,900)});
                    });
                  }
                  return os.apply(this,arguments);
                };
              }
              return {ok:true};
            })()""",
        )
        time.sleep(5)
        rec["click"] = ev(
            ws,
            r"""(function(){
              var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null && (x.textContent||'').indexOf('保存并下一步')>=0 && !x.disabled);
              if(!b) return {clicked:false};
              b.click(); return {clicked:true};
            })()""",
        )
        time.sleep(10)
        rec["after"] = ev(
            ws,
            r"""(function(){
              return {
                href:location.href, hash:location.hash,
                errors:[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean).slice(0,10),
                lastReq:(window.__mcap&&window.__mcap.req||[]).slice(-6),
                lastResp:(window.__mcap&&window.__mcap.resp||[]).slice(-6)
              };
            })()""",
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

