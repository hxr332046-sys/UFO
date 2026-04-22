#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
设立登记链路现场快照：用于「到云提交/云帮办附近就停」时的判定与归档。

用法：
  python live_snapshot_yun_submit.py              # 只快照当前最佳 9087 页签
  python live_snapshot_yun_submit.py --open-entry # 若不在 9087，则整页拉到企业专区入口（便于登录后进办件）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "data" / "records" / "live_snapshot_yun_submit.json"

_SNAPSHOT_JS = r"""(function(){
  var t = document.body.innerText || '';
  var keys = ['云提交','云端提交','云帮办','云帮办流程模式选择','保存并下一步','下一步','提交','确定','系统服务出现异常','请勿多次重复提交'];
  var hit = {};
  keys.forEach(function(k){ hit[k] = t.indexOf(k) >= 0; });
  var errs = [].slice.call(document.querySelectorAll('.el-form-item__error,.el-message,.el-message-box__message')).map(function(e){
    return (e.textContent || '').replace(/\s+/g,' ').trim();
  }).filter(Boolean).slice(0, 40);
  var btns = [].slice.call(document.querySelectorAll('button,.el-button')).filter(function(x){ return x.offsetParent !== null; }).map(function(b){
    return { text: (b.textContent || '').replace(/\s+/g,' ').trim().slice(0, 100), disabled: !!b.disabled };
  }).slice(0, 50);
  return {
    href: location.href,
    hash: location.hash,
    hit: hit,
    hasYunbangbanMode: t.indexOf('云帮办流程模式选择') >= 0,
    errorsVisible: errs,
    buttons: btns,
    title: document.title || '',
    textHead: t.slice(0, 1200)
  };
})()"""


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=25)
        self._n = 1

    def call(self, method: str, params=None, timeout: float = 20.0):
        if params is None:
            params = {}
        cid = self._n
        self._n += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == cid:
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})
        return {"error": {"message": "timeout " + method}}

    def ev(self, expr: str, timeout_ms: int = 60000):
        r = self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
                "timeout": timeout_ms,
            },
            timeout=25,
        )
        return ((r or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def _pick_ws_fallback() -> tuple[str | None, str | None]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") != "page":
            continue
        u = p.get("url") or ""
        if "zhjg.scjdglj.gxzf.gov.cn:9087" in u and "icpsp-web-pc" in u:
            return p["webSocketDebuggerUrl"], u
    for p in pages:
        if p.get("type") == "page" and "chrome://" not in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url") or ""
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open-entry", action="store_true", help="Navigate to 9087 enterprise-zone entry when not on ICPSP 9087")
    args = ap.parse_args()

    rec: dict = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}

    ws_url = None
    url_hint = None
    if args.open_entry:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from icpsp_entry import ensure_icpsp_entry

            nav = ensure_icpsp_entry(9225, busi_type="02_4", navigate_policy="host_only", wait_after_nav_sec=3.0)
            rec["steps"].append({"step": "ensure_icpsp_entry", "data": nav})
            if nav.get("ok"):
                ws_url = nav.get("ws_url")
                url_hint = nav.get("url_after")
        except Exception as e:
            rec["steps"].append({"step": "ensure_icpsp_entry_error", "data": str(e)})

    if not ws_url:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from icpsp_entry import get_ws_url_for_icpsp

            ws_url = get_ws_url_for_icpsp(9225, busi_type="02_4", navigate_policy="host_only")
        except Exception:
            ws_url = None
    if not ws_url:
        ws_url, url_hint = _pick_ws_fallback()

    if not ws_url:
        rec["error"] = "no_cdp_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print("no_cdp_page ->", OUT)
        return 1

    c = CDP(ws_url)
    try:
        snap = c.ev(_SNAPSHOT_JS)
        rec["snapshot"] = snap
        rec["ws_hint"] = url_hint
    finally:
        c.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT)
    if isinstance(rec.get("snapshot"), dict):
        print("href:", (rec["snapshot"] or {}).get("href"))
        print("markers:", json.dumps((rec["snapshot"] or {}).get("hit"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
