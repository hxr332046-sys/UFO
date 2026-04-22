#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_attack_guide_base.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method: str, params=None, timeout=8):
        if params is None:
            params = {}
        my_id = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        start = time.time()
        while True:
            if time.time() - start > timeout:
                return {"error": {"message": f"timeout {method}"}}
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == my_id:
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})

    def ev(self, expr: str, timeout=60000):
        ret = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            timeout=10,
        )
        return (((ret or {}).get("result") or {}).get("value"))

    def collect_events(self, seconds=2.0):
        end = time.time() + seconds
        events = []
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if "method" in msg and msg["method"].startswith("Network."):
                events.append(msg)
        return events

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "icpsp-web-pc/name-register.html#/guide/base" in u:
            return p.get("webSocketDebuggerUrl"), u
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def summarize_network(events):
    out = {"requestWillBeSent": [], "responseReceived": []}
    for e in events:
        m = e.get("method")
        p = e.get("params", {})
        if m == "Network.requestWillBeSent":
            req = p.get("request", {})
            out["requestWillBeSent"].append(
                {
                    "url": (req.get("url") or "")[:260],
                    "method": req.get("method"),
                    "postData": (req.get("postData") or "")[:500],
                    "type": p.get("type"),
                }
            )
        elif m == "Network.responseReceived":
            res = p.get("response", {})
            out["responseReceived"].append(
                {
                    "url": (res.get("url") or "")[:260],
                    "status": res.get("status"),
                    "mimeType": res.get("mimeType"),
                    "type": p.get("type"),
                }
            )
    return out


def page_state(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          var txt=(document.body&&document.body.innerText)||'';
          return {
            href:location.href,hash:location.hash,
            hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
            hasNamePrompt:txt.indexOf('请选择是否需要名称')>=0,
            selectedNotApply:(function(){
              var nodes=[...document.querySelectorAll('*')].filter(n=>n.offsetParent!==null&&((n.textContent||'').replace(/\s+/g,' ').trim()==='未申请'));
              for(var n of nodes){
                var c=(n.className||'')+'';
                var p=n.parentElement;
                if(/active|checked|is-checked|selected/.test(c)) return true;
                if(p&&/active|checked|is-checked|selected/.test((p.className||'')+'')) return true;
              }
              return false;
            })(),
            buttons:[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled})).slice(0,20)
          };
        })()"""
    )


def do_click_chain(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          function clickTxt(t){
            var els=[...document.querySelectorAll('button,.el-button,label,span,div,a,li')].filter(e=>e.offsetParent!==null);
            for(var e of els){
              var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
              if(tx===t||tx.indexOf(t)>=0){ e.click(); return tx; }
            }
            return null;
          }
          return {notApply:clickTxt('未申请'),next:clickTxt('下一步'),confirm:clickTxt('确定')};
        })()"""
    )


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws_url, current = pick_ws()
    rec["steps"].append({"step": "pick_ws", "data": {"url": current}})
    if not ws_url:
        rec["error"] = "no_9087_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    cdp = CDP(ws_url)
    cdp.call("Page.enable", {})
    cdp.call("Network.enable", {"maxTotalBufferSize": 10000000, "maxResourceBufferSize": 5000000})
    cdp.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}")
    time.sleep(3)

    before = page_state(cdp)
    events_before = cdp.collect_events(2.5)
    rec["steps"].append({"step": "before_state", "data": before})
    rec["steps"].append({"step": "before_network", "data": summarize_network(events_before)})

    clicks = do_click_chain(cdp)
    time.sleep(1.2)
    events_after_click = cdp.collect_events(4.0)
    after = page_state(cdp)
    rec["steps"].append({"step": "click_chain", "data": clicks})
    rec["steps"].append({"step": "after_state", "data": after})
    rec["steps"].append({"step": "after_network", "data": summarize_network(events_after_click)})

    rec["result"] = "reached_yunbangban" if after.get("hasYunbangban") else "still_blocked_guide"
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

