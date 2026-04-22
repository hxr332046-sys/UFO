#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/inspect_next_button_vm_chain.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws_url = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not ws_url:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    expr = r"""(function(){
      function methodsOf(vm){
        var arr=[]; for(var k in vm){ if(typeof vm[k]==='function' && /next|save|submit|flow|step|check|valid/i.test(k)) arr.push(k); }
        return arr.slice(0,80);
      }
      var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
      if(!btn) return {ok:false,msg:'no_next_btn'};
      var chain=[];
      var node=btn;
      var hops=0;
      while(node && hops<20){
        var vm=node.__vue__;
        chain.push({
          tag:node.tagName||'',
          cls:(node.className||'')+'',
          hasVue:!!vm,
          vmName:vm&&vm.$options?((vm.$options.name||'')):null,
          vmMethods:vm?methodsOf(vm):[]
        });
        node=node.parentElement; hops++;
      }
      return {
        ok:true,
        btnClass:(btn.className||'')+'',
        btnText:(btn.textContent||'').replace(/\s+/g,' ').trim(),
        chain:chain
      };
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    out = None
    end = time.time() + 10
    while time.time() < end:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            out = msg.get("result", {}).get("result", {}).get("value")
            break
    ws.close()
    rec["data"] = out
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

