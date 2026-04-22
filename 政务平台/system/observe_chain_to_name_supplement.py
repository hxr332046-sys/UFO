#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分阶段观察链路（不自动点击）：
6087 第一入口 -> 9087 guide/base -> 9087 core/name-check-info -> 9087 core/name-supplement
用于验证“从头到这里”的上下文打通，不继续到云帮办。
"""
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/observe_chain_to_name_supplement.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=8).json()
    pages = [p for p in pages if p.get("type") == "page"]
    # 优先 6087 顶层入口
    for p in pages:
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:6087" in u:
            return p.get("webSocketDebuggerUrl"), u
    # 其次 9087
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


def stage_from_href(href: str) -> str:
    h = href or ""
    if "6087/TopIP/web/web-portal.html#/index/page" in h:
        return "S0_topip_entry"
    if "9087/icpsp-web-pc/name-register.html#/guide/base" in h:
        return "S1_guide_base"
    if "9087/icpsp-web-pc/core.html#/flow/base/name-check-info" in h:
        return "S2_name_check_info"
    if "9087/icpsp-web-pc/core.html#/flow/base/name-supplement" in h:
        return "S3_name_supplement"
    return "Sx_other"


def main():
    ws_url, start_url = pick_ws()
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_url": start_url,
        "transitions": [],
        "result": "running",
    }
    if not ws_url:
        rec["result"] = "no_cdp_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws_url)
    try:
        last_href = None
        deadline = time.time() + 300  # 5分钟观察窗口
        while time.time() < deadline:
            snap = c.ev(
                r"""(function(){
                  var t=(document.body&&document.body.innerText)||'';
                  return {
                    href:location.href,
                    hash:location.hash,
                    title:document.title||'',
                    hasTaskCenter:t.indexOf('办件中心')>=0,
                    snippet:t.replace(/\s+/g,' ').trim().slice(0,180)
                  };
                })()"""
            )
            href = (snap or {}).get("href") if isinstance(snap, dict) else None
            if href and href != last_href:
                rec["transitions"].append(
                    {
                        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "stage": stage_from_href(href),
                        "data": snap,
                    }
                )
                last_href = href
                if "core.html#/flow/base/name-supplement" in href:
                    rec["result"] = "reached_name_supplement"
                    break
            time.sleep(1)
        if rec["result"] == "running":
            rec["result"] = "timeout_not_reached_name_supplement"
    finally:
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        c.close()


if __name__ == "__main__":
    main()

