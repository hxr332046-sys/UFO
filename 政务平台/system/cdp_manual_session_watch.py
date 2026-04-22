#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
短时 CDP 监察：连接 9225 上优先选中的 9087 页签，记录 Network（icpsp-api 相关）与 Page 导航。
用于人工操作一次时并行落盘，供事后对照分析。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import websocket

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("icpsp_entry", _HERE / "icpsp_entry.py")
_icpsp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_icpsp)
pick_icpsp_target_prefer_logged_portal = _icpsp.pick_icpsp_target_prefer_logged_portal

OUT_DIR = Path(__file__).resolve().parents[1] / "dashboard" / "data" / "records"
WATCH_KEYWORDS = ("icpsp-api", "9087", "tyrz.zwfw.gxzf.gov.cn", "/TopIP/", "/oauth", "/authorize", "/am/auth/")


def _connect(ws_url: str) -> websocket.WebSocket:
    ws = websocket.create_connection(ws_url, timeout=25)
    ws.settimeout(0.5)
    return ws


def _call(ws: websocket.WebSocket, i: int, method: str, params: Optional[dict] = None) -> None:
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))


def run_watch(duration_sec: float, out_path: Path, url_keyword: str = "", strict_keyword: bool = False) -> int:
    best = None
    dbg: List[Dict[str, Any]] = []
    if url_keyword:
        try:
            import requests

            arr = requests.get("http://127.0.0.1:9225/json", timeout=4).json()
            for t in arr:
                if not isinstance(t, dict):
                    continue
                u = str(t.get("url") or "")
                if url_keyword in u and t.get("webSocketDebuggerUrl"):
                    best = t
                    break
                dbg.append({"id": t.get("id"), "title": t.get("title"), "url": u[:160]})
        except Exception:
            best = None

    if not best and url_keyword and strict_keyword:
        print(f"ERROR: 未找到 URL 包含关键字的页签: {url_keyword}", file=sys.stderr)
        print("debug:", dbg, file=sys.stderr)
        return 3

    if not best:
        best, dbg = pick_icpsp_target_prefer_logged_portal(9225)
    if not best or not best.get("webSocketDebuggerUrl"):
        print("ERROR: 无可用 CDP 页签（请先开 Chrome --remote-debugging-port=9225 并打开 9087 站点）", file=sys.stderr)
        print("debug:", dbg, file=sys.stderr)
        return 2

    ws_url = best["webSocketDebuggerUrl"]
    print("监察目标:", best.get("url", "")[:120])
    print("时长:", duration_sec, "秒 — 请在此期间在浏览器中完成你的操作")
    print("写入:", out_path)

    ws = _connect(ws_url)
    n = 1
    _call(ws, n, "Network.enable", {"maxTotalBufferSize": 10000000, "maxResourceBufferSize": 5000000})
    n += 1
    _call(ws, n, "Page.enable", {})
    n += 1

    req_urls: Dict[str, str] = {}
    t_end = time.time() + duration_sec

    meta = {
        "type": "meta",
        "wall_time_start": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cdp_target_url": best.get("url"),
        "duration_sec": duration_sec,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fout = out_path.open("w", encoding="utf-8")
    fout.write(json.dumps(meta, ensure_ascii=False) + "\n")
    fout.flush()

    while time.time() < t_end:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            break
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        m = msg.get("method")
        if not m:
            continue
        if m == "Network.requestWillBeSent":
            p = msg.get("params") or {}
            rid = p.get("requestId")
            req_obj = p.get("request") or {}
            url = req_obj.get("url") or ""
            if isinstance(rid, str):
                req_urls[rid] = url
            if any(k in url for k in WATCH_KEYWORDS):
                raw_h = req_obj.get("headers") or {}
                h = raw_h if isinstance(raw_h, dict) else {}
                row = {
                    "type": "req",
                    "t": time.time(),
                    "url": url[:500],
                    "method": req_obj.get("method"),
                    "req_headers": {
                        "Authorization": str(h.get("Authorization") or "").strip(),
                        "Cookie": str(h.get("Cookie") or "").strip(),
                        "Referer": str(h.get("Referer") or "").strip(),
                        "Origin": str(h.get("Origin") or "").strip(),
                        "User-Agent": str(h.get("User-Agent") or "").strip(),
                        "language": str(h.get("language") or h.get("Language") or "").strip(),
                    },
                }
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
        elif m == "Network.responseReceived":
            p = msg.get("params") or {}
            rid = p.get("requestId")
            resp = p.get("response") or {}
            url = resp.get("url") or (req_urls.get(rid) if isinstance(rid, str) else "") or ""
            if any(k in url for k in WATCH_KEYWORDS):
                row = {
                    "type": "resp",
                    "t": time.time(),
                    "status": resp.get("status"),
                    "mime": resp.get("mimeType"),
                    "url": url[:500],
                }
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
        elif m == "Page.frameNavigated":
            p = msg.get("params") or {}
            frame = p.get("frame") or {}
            u = frame.get("url") or ""
            if u and not u.startswith("devtools://"):
                row = {"type": "nav", "t": time.time(), "url": u[:500]}
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
        elif m == "Page.loadEventFired":
            row = {"type": "load", "t": time.time()}
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()

    try:
        ws.close()
    except Exception:
        pass
    try:
        fout.close()
    except Exception:
        pass
    line_count = sum(1 for _ in out_path.open("r", encoding="utf-8"))
    print("记录条数（含 meta）:", line_count)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="CDP 短时监察记录（人工操作时并行运行）")
    ap.add_argument("--seconds", type=float, default=90.0, help="记录时长（秒）")
    ap.add_argument("-o", "--output", type=Path, default=None, help="JSONL 输出路径")
    ap.add_argument("--url-keyword", default="", help="优先选择 URL 包含该关键字的页签，例如 TopIP 或 6087")
    ap.add_argument("--strict-keyword", action="store_true", help="当 --url-keyword 未匹配到页签时直接报错，不回退")
    args = ap.parse_args()
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = args.output or (OUT_DIR / f"manual_cdp_watch_{ts}.jsonl")
    raise SystemExit(
        run_watch(
            args.seconds,
            out,
            url_keyword=str(args.url_keyword or ""),
            strict_keyword=bool(args.strict_keyword),
        )
    )


if __name__ == "__main__":
    main()
