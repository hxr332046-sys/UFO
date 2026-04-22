#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于“用户手动跑通一次”留下的真实上下文 URL，做阶段1重放验证：
guide/base -> core(flow/base query) -> name-check-info / name-supplement
不依赖表单重填，直接复用手动成功链路参数。
"""
import json
import time
from pathlib import Path

import requests
import websocket

SRC = Path("G:/UFO/政务平台/dashboard/data/records/listen_current_page_once.json")
OUT = Path("G:/UFO/政务平台/dashboard/data/records/replay_from_manual_context_stage1.json")
FALLBACK_MANUAL_FLOW_URL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base"
    "?fromProject=name-register&fromPage=/guide/base&entType=4540&busiType=01_4"
    "&extra=guideData&vipChannel=null&ywlbSign=&busiId="
    "&extraDto={%22extraDto%22:{%22entType%22:%224540%22,%22nameCode%22:%220%22,"
    "%22distCode%22:%22450921%22,%22streetCode%22:null,%22streetName%22:null,"
    "%22address%22:%22%E5%B9%BF%E8%A5%BF%E5%A3%AE%E6%97%8F%E8%87%AA%E6%B2%BB%E5%8C%BA"
    "%E7%8E%89%E6%9E%97%E5%B8%82%E5%AE%B9%E5%8E%BF%22,%22rcMoneyKindCode%22:%22%22,"
    "%22distCodeArr%22:[%22450000%22,%22450900%22,%22450921%22],%22fzSign%22:%22N%22,"
    "%22parentEntRegno%22:%22%22,%22parentEntName%22:%22%22,%22regCapitalUSD%22:%22%22}}"
)


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=8).json()
    pages = [p for p in pages if p.get("type") == "page"]
    for p in pages:
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:9087" in u:
            return p.get("webSocketDebuggerUrl"), u
    return (pages[0].get("webSocketDebuggerUrl"), pages[0].get("url") or "") if pages else (None, "")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method, params=None, timeout=20):
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

    def ev(self, expr, timeout_ms=60000):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
            timeout=22,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def extract_manual_flow_url():
    if not SRC.exists():
        return None
    data = json.loads(SRC.read_text(encoding="utf-8"))
    for st in data.get("steps", []):
        if st.get("step") == "observed":
            href = ((st.get("data") or {}).get("href") or "").strip()
            if "core.html#/flow/base?" in href and "extraDto=" in href:
                return href
    return FALLBACK_MANUAL_FLOW_URL


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    flow_url = extract_manual_flow_url()
    rec["steps"].append({"step": "extract_manual_context_url", "data": flow_url})
    if not flow_url:
        rec["result"] = "no_manual_context_url"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws, cur = pick_ws()
    rec["steps"].append({"step": "pick_ws", "data": cur})
    if not ws:
        rec["result"] = "no_cdp_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws)
    try:
        rec["steps"].append({"step": "navigate_manual_flow_url", "data": c.ev(f"location.href={json.dumps(flow_url, ensure_ascii=False)}")})
        time.sleep(5)

        timeline = []
        for i in range(25):
            s = c.ev(
                r"""(function(){
                  var href=location.href, h=location.hash||'';
                  return {
                    href: href,
                    hash: h,
                    isNameCheck: h.indexOf('name-check-info')>=0,
                    isNameSupplement: h.indexOf('name-supplement')>=0
                  };
                })()"""
            )
            timeline.append(s)
            if s.get("isNameCheck") or s.get("isNameSupplement"):
                break
            time.sleep(1)
        rec["steps"].append({"step": "timeline_after_replay", "data": timeline})
        last = timeline[-1] if timeline else {}
        rec["result"] = "replayed_to_stage1_ok" if (last.get("isNameCheck") or last.get("isNameSupplement")) else "replay_not_reached_stage1"
    finally:
        c.close()

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

