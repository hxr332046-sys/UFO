#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/single_retry_capture_namecheck.json")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=12):
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

    def ev(self, expr):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            timeout=15,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def capture_network(self, seconds=8):
        reqs, resps = [], []
        end = time.time() + seconds
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            method = msg.get("method")
            if method == "Network.requestWillBeSent":
                p = msg.get("params", {})
                r = p.get("request", {})
                reqs.append(
                    {
                        "url": (r.get("url") or "")[:260],
                        "method": r.get("method"),
                        "postData": (r.get("postData") or "")[:1200],
                    }
                )
            elif method == "Network.responseReceived":
                p = msg.get("params", {})
                r = p.get("response", {})
                req_id = p.get("requestId")
                body_text = ""
                if req_id:
                    rb = self.call("Network.getResponseBody", {"requestId": req_id}, timeout=2)
                    body_text = ((rb.get("result") or {}).get("body") or "")[:2000]
                resps.append({"url": (r.get("url") or "")[:260], "status": r.get("status"), "body": body_text})
        return {"reqs": reqs, "resps": resps}


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})
    rec["steps"].append(
        {
            "step": "before",
            "data": c.ev(
                r"""(function(){var txt=(document.body.innerText||'');var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasNotice:txt.indexOf('请阅读《名称登记自主申报须知》并勾选')>=0};})()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "single_submit_action",
            "data": c.ev(
                r"""(function(){
                  var acts=[];
                  function clickContains(t){
                    var els=[...document.querySelectorAll('button,.el-button,label,span,div')].filter(x=>x.offsetParent!==null);
                    for(var e of els){
                      var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
                      if(tx.indexOf(t)>=0){
                        e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                        return true;
                      }
                    }
                    return false;
                  }
                  if(clickContains('我已阅读并同意')) acts.push('agree');
                  if(clickContains('确定')) acts.push('ok');
                  if(clickContains('保存并下一步')) acts.push('save_next');
                  return {actions:acts};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "network_after_submit", "data": c.capture_network(10)})
    rec["steps"].append(
        {
            "step": "after",
            "data": c.ev(
                r"""(function(){var txt=(document.body.innerText||'');var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasNotice:txt.indexOf('请阅读《名称登记自主申报须知》并勾选')>=0,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()"""
            ),
        }
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

