#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_capture_frontend_errors.json")


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
        reqs = []
        end = time.time() + sec
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                r = p.get("request", {})
                reqs.append({"url": (r.get("url") or "")[:260], "method": r.get("method"), "postData": (r.get("postData") or "")[:400]})
        return reqs


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
    rec["steps"].append(
        {
            "step": "install_error_hooks",
            "data": c.ev(
                r"""(function(){
                  window.__err_cap=[];
                  window.onerror=function(msg,src,line,col,err){
                    window.__err_cap.push({t:Date.now(),type:'onerror',msg:String(msg||''),src:String(src||''),line:line||0,col:col||0,stack:err&&err.stack?String(err.stack).slice(0,500):''});
                  };
                  window.onunhandledrejection=function(e){
                    var r=e&&e.reason;
                    window.__err_cap.push({t:Date.now(),type:'unhandledrejection',reason:typeof r==='string'?r:JSON.stringify(r||{}).slice(0,500)});
                  };
                  return {ok:true};
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "click_next_force",
            "data": c.ev(
                r"""(function(){
                  var b=[...document.querySelectorAll('button.el-button.sub-btn,.el-button.sub-btn,button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
                  if(!b) return {ok:false};
                  b.click();
                  return {ok:true,cls:(b.className||'')+'',disabled:!!b.disabled,text:(b.textContent||'').replace(/\s+/g,' ').trim()};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "net_after", "data": c.net(6)})
    rec["steps"].append({"step": "errors", "data": c.ev("window.__err_cap||[]")})
    rec["steps"].append({"step": "button_state", "data": c.ev(r"""(function(){var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);return b?{cls:(b.className||'')+'',disabled:!!b.disabled,text:(b.textContent||'').replace(/\s+/g,' ').trim()}:null;})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

