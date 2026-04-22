#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/scan_core_basicinfo_vms_latest.json")


def pick_ws() -> Tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in u:
            return p.get("webSocketDebuggerUrl"), u
    return None, None


def ev(ws_url: str, expr: str, timeout_ms: int = 70000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.settimeout(2.0)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms}}))
    end = time.time() + 45
    try:
        while time.time() < end:
            try:
                m = json.loads(ws.recv())
            except Exception:
                continue
            if m.get("id") == 1:
                return ((m.get("result") or {}).get("result") or {}).get("value")
    finally:
        ws.close()
    return None


JS = r"""(function(){
  var app=document.getElementById('app'); var root=app&&app.__vue__;
  if(!root) return {ok:false,msg:'no_root'};
  var out=[];
  function walk(vm,d){
    if(!vm||d>30||out.length>220) return;
    var n=(vm.$options&&vm.$options.name)||'';
    var dk=Object.keys(vm.$data||{});
    var hasForm = !!(vm.form || vm.formInfo || vm.ruleForm || vm.formData);
    if(hasForm || dk.some(function(k){return /form|ent|address|industry|phone|employee|capital/i.test(k);})){
      out.push({
        d:d,
        name:n,
        dataKeys:dk.slice(0,20),
        has_form:!!vm.form,
        has_formInfo:!!vm.formInfo,
        has_ruleForm:!!vm.ruleForm,
        form_keys: vm.form ? Object.keys(vm.form).slice(0,20) : [],
        formInfo_keys: vm.formInfo ? Object.keys(vm.formInfo).slice(0,20) : []
      });
    }
    for(var ch of (vm.$children||[])) walk(ch,d+1);
  }
  walk(root,0);
  return {ok:true,count:out.length,items:out.slice(0,140)};
})()"""


def main() -> int:
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    rec["start_url"] = cur
    if not ws:
        rec["error"] = "no_basicinfo_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    rec["steps"].append({"step": "scan", "data": ev(ws, JS, 70000)})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

