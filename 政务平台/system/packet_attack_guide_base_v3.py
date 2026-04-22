#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_attack_guide_base_v3.json")
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

    def collect_network(self, seconds=3.0):
        end = time.time() + seconds
        reqs, resps = [], []
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                r = p.get("request", {})
                reqs.append({"url": (r.get("url") or "")[:260], "method": r.get("method"), "type": p.get("type")})
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                r = p.get("response", {})
                resps.append({"url": (r.get("url") or "")[:260], "status": r.get("status"), "type": p.get("type")})
        return {"requestWillBeSent": reqs, "responseReceived": resps}

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
    return None, None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws_url, u = pick_ws()
    rec["steps"].append({"step": "pick_ws", "data": u})
    if not ws_url:
        rec["error"] = "no_guide_tab"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    cdp = CDP(ws_url)
    cdp.call("Page.enable", {})
    cdp.call("Network.enable", {})
    cdp.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}")
    time.sleep(3)

    rec["steps"].append(
        {
            "step": "radio_structure",
            "data": cdp.ev(
                r"""(function(){
                  var groups=[...document.querySelectorAll('.tni-radio-group,.el-radio-group')].filter(g=>g.offsetParent!==null);
                  var out=[];
                  for(var g of groups){
                    var items=[...g.querySelectorAll('.tni-radio,.el-radio,label,span,div')].filter(x=>x.offsetParent!==null);
                    out.push({
                      cls:(g.className||'')+'',
                      text:(g.textContent||'').replace(/\s+/g,' ').trim().slice(0,200),
                      items:items.map(it=>({tag:it.tagName,cls:(it.className||'')+'',text:(it.textContent||'').replace(/\s+/g,' ').trim().slice(0,60)})).slice(0,20)
                    });
                  }
                  return out;
                })()"""
            ),
        }
    )

    rec["steps"].append({"step": "network_before", "data": cdp.collect_network(2.0)})

    rec["steps"].append(
        {
            "step": "target_clicks",
            "data": cdp.ev(
                r"""(function(){
                  function clickByTextInsideGroup(keyword){
                    var groups=[...document.querySelectorAll('.tni-radio-group,.el-radio-group')].filter(g=>g.offsetParent!==null);
                    for(var g of groups){
                      var items=[...g.querySelectorAll('.tni-radio,.el-radio,label,span,div')].filter(x=>x.offsetParent!==null);
                      for(var it of items){
                        var tx=(it.textContent||'').replace(/\s+/g,' ').trim();
                        if(tx===keyword||tx.indexOf(keyword)>=0){
                          ['mousedown','mouseup','click'].forEach(function(tp){it.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));});
                          return {ok:true,kw:keyword,tag:it.tagName,cls:(it.className||'')+'',text:tx};
                        }
                      }
                    }
                    return {ok:false,kw:keyword};
                  }
                  function clickBtn(kw){
                    var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf(kw)>=0&&!x.disabled);
                    if(!b) return {ok:false,kw:kw};
                    b.click(); return {ok:true,kw:kw,text:(b.textContent||'').replace(/\s+/g,' ').trim()};
                  }
                  return {
                    r1:clickByTextInsideGroup('未申请'),
                    b1:clickBtn('下一步'),
                    b2:clickBtn('确定')
                  };
                })()"""
            ),
        }
    )
    time.sleep(1.0)
    rec["steps"].append({"step": "network_after", "data": cdp.collect_network(4.0)})
    rec["steps"].append(
        {
            "step": "state_after",
            "data": cdp.ev(
                r"""(function(){
                  var txt=(document.body&&document.body.innerText)||'';
                  return {
                    href:location.href,hash:location.hash,
                    hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
                    hasNamePrompt:txt.indexOf('请选择是否需要名称')>=0
                  };
                })()"""
            ),
        }
    )

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

