#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/round2_submit_success_evidence.json")
ROUND2_JSON = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round2.json")
ROUND2_MD = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round2.md")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/submit-success" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=40000):
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"captured_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ws, url = pick_ws()
    rec["url"] = url
    if not ws:
        rec["error"] = "no_core_page"
    else:
        rec["snapshot"] = ev(
            ws,
            r"""(function(){
              function find(vm,d){
                if(!vm||d>20) return null;
                var n=(vm.$options&&vm.$options.name)||'';
                if(n==='flow-control') return vm;
                for(var c of (vm.$children||[])){var r=find(c,d+1); if(r) return r;}
                return null;
              }
              var app=document.getElementById('app');
              var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
              return {
                href:location.href, hash:location.hash, title:document.title,
                text:(document.body.innerText||'').slice(0,1500),
                flowData:fc&&fc.params?fc.params.flowData:null
              };
            })()""",
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    # update round2 main record if exists
    if ROUND2_JSON.exists():
        data = json.loads(ROUND2_JSON.read_text(encoding="utf-8"))
        data["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["result"] = "success_submit_page"
        data["final_hash"] = (rec.get("snapshot") or {}).get("hash")
        fd = ((rec.get("snapshot") or {}).get("flowData") or {})
        data["busiId"] = fd.get("busiId", data.get("busiId"))
        data["nameId"] = fd.get("nameId", data.get("nameId"))
        data.setdefault("steps", []).append({"step": "S9_submit_success_capture", "note": rec.get("url", "")})
        ROUND2_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        md = [
            "# 02_4 Round2 全链路重测",
            "",
            f"- started_at: {data.get('started_at','')}",
            f"- ended_at: {data.get('ended_at','')}",
            f"- result: {data.get('result','')}",
            f"- final_hash: {data.get('final_hash','')}",
            "",
            "## 关键ID",
            f"- busiId: {data.get('busiId','')}",
            f"- nameId: {data.get('nameId','')}",
            "",
            "## 成功证据",
            f"- submit_success_url: {rec.get('url','')}",
            f"- evidence_file: {OUT.as_posix()}",
            "",
        ]
        ROUND2_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"Saved: {OUT}")
    print(f"Updated: {ROUND2_JSON}")
    print(f"Updated: {ROUND2_MD}")


if __name__ == "__main__":
    main()

