#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_attack_guide_base_v2.json")
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
                reqs.append(
                    {
                        "url": (r.get("url") or "")[:260],
                        "method": r.get("method"),
                        "postData": (r.get("postData") or "")[:500],
                        "type": p.get("type"),
                    }
                )
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                r = p.get("response", {})
                resps.append(
                    {
                        "url": (r.get("url") or "")[:260],
                        "status": r.get("status"),
                        "type": p.get("type"),
                    }
                )
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


def state(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          var txt=(document.body&&document.body.innerText)||'';
          function sel(){
            var cands=[...document.querySelectorAll('.el-radio,.el-radio-button,label,span,div')].filter(e=>e.offsetParent!==null);
            for(var e of cands){
              var t=(e.textContent||'').replace(/\s+/g,' ').trim();
              if(t==='未申请'||t.indexOf('未申请')>=0){
                var cls=((e.className||'')+' '+((e.parentElement&&e.parentElement.className)||''));
                if(/active|checked|is-checked|selected/.test(cls)) return true;
              }
            }
            return false;
          }
          return {
            href:location.href,hash:location.hash,
            hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
            selectedNotApply:sel(),
            buttons:[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled})).slice(0,20)
          };
        })()"""
    )


def precise_click(cdp: CDP, keyword: str):
    return cdp.ev(
        f"""(function(){{
          function norm(s){{return (s||'').replace(/\\s+/g,' ').trim();}}
          var cand=[...document.querySelectorAll('label,span,div,button,.el-button,.el-radio,.el-radio-button')].filter(e=>e.offsetParent!==null);
          var tgt=null,tx='';
          for(var e of cand){{
            var t=norm(e.textContent||'');
            if(t==='{keyword}'||t.indexOf('{keyword}')>=0){{
              tx=t; tgt=e; break;
            }}
          }}
          if(!tgt) return {{ok:false,why:'not_found'}};
          var clickNode=tgt.closest('label,button,.el-button,.el-radio,.el-radio-button')||tgt;
          var r=clickNode.getBoundingClientRect();
          var x=Math.floor(r.left+r.width/2), y=Math.floor(r.top+r.height/2);
          var p=document.elementFromPoint(x,y);
          if(p){{
            ['mousedown','mouseup','click'].forEach(function(tp){{
              p.dispatchEvent(new MouseEvent(tp,{{bubbles:true,cancelable:true,view:window,clientX:x,clientY:y}}));
            }});
          }}
          ['mousedown','mouseup','click'].forEach(function(tp){{
            clickNode.dispatchEvent(new MouseEvent(tp,{{bubbles:true,cancelable:true,view:window,clientX:x,clientY:y}}));
          }});
          return {{ok:true,text:tx,clickedTag:clickNode.tagName,x:x,y:y,pointTag:(p&&p.tagName)||null,pointClass:(p&&p.className)||null}};
        }})()"""
    )


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

    rec["steps"].append({"step": "before_state", "data": state(cdp)})
    rec["steps"].append({"step": "network_idle_before", "data": cdp.collect_network(2.0)})

    rec["steps"].append({"step": "click_not_apply", "data": precise_click(cdp, "未申请")})
    time.sleep(0.8)
    rec["steps"].append({"step": "click_next", "data": precise_click(cdp, "下一步")})
    time.sleep(0.8)
    rec["steps"].append({"step": "click_confirm", "data": precise_click(cdp, "确定")})
    time.sleep(1.2)

    rec["steps"].append({"step": "after_network", "data": cdp.collect_network(4.0)})
    rec["steps"].append({"step": "after_state", "data": state(cdp)})
    rec["result"] = "done"
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

