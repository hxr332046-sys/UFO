#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/inspect_org_error_binding.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    if not ws:
        OUT.write_text(json.dumps({"error": "no_namecheck_page"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    data = ev(
        ws,
        r"""(function(){
          function text(n){return (n&&n.textContent||'').replace(/\s+/g,' ').trim();}
          function flat(o){
            var r={}; if(!o||typeof o!=='object') return r;
            Object.keys(o).forEach(function(k){
              try{
                var v=o[k];
                if(v===null||v===undefined||typeof v==='string'||typeof v==='number'||typeof v==='boolean'){r[k]=v;}
              }catch(e){}
            });
            return r;
          }
          var errNode=[...document.querySelectorAll('.el-form-item__error')].find(e=>text(e).indexOf('请选择组织形式')>=0);
          if(!errNode) return {ok:false,msg:'no_org_error_node'};
          var item=errNode.closest('.el-form-item');
          var html=item?item.outerHTML.slice(0,6000):'';
          var label=item?text(item.querySelector('.el-form-item__label')):'';
          var vm=item&&item.__vue__?item.__vue__:null;
          var vmInfo=vm?{
            name:(vm.$options&&vm.$options.name)||'',
            data:flat(vm.$data||{}),
            propData:flat(vm.$props||{}),
            parentName:(vm.$parent&&vm.$parent.$options&&vm.$parent.$options.name)||'',
            parentData:flat(vm.$parent&&vm.$parent.$data||{})
          }:null;
          // inspect inputs and radio/select descendants
          var controls=item?[...item.querySelectorAll('input,textarea,select,label,span,div')].slice(0,80).map(n=>({
            tag:n.tagName,cls:(n.className||'')+'',txt:text(n).slice(0,80),val:(n.value||'')+''
          })):[];
          return {ok:true,label:label,vmInfo:vmInfo,controls:controls,html:html};
        })()""",
    )
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

