#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP multi-target watcher (aggregated capture).

Use this when browser actions may jump across tabs/targets.
It attaches to all matching page targets and writes events into one JSONL file.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
import websocket


OUT_DIR = Path("G:/UFO/政务平台/dashboard/data/records")
WATCH_KEYWORDS = (
    "icpsp-api",
    "icpsp-web-pc",
    "TopIP",
    "oauth",
    "authorize",
    "am/auth/",
)


def _list_targets(port: int) -> List[Dict[str, Any]]:
    arr = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
    out: List[Dict[str, Any]] = []
    for t in arr:
        if not isinstance(t, dict):
            continue
        if t.get("type") != "page":
            continue
        ws = t.get("webSocketDebuggerUrl")
        if not ws:
            continue
        out.append(t)
    return out


def _match_targets(targets: List[Dict[str, Any]], keyword: str) -> List[Dict[str, Any]]:
    if not keyword:
        return targets
    out: List[Dict[str, Any]] = []
    for t in targets:
        u = str(t.get("url") or "")
        title = str(t.get("title") or "")
        if keyword in u or keyword in title:
            out.append(t)
    return out


def _connect_target(t: Dict[str, Any]) -> websocket.WebSocket:
    ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=25)
    ws.settimeout(0.1)
    return ws


def _send(ws: websocket.WebSocket, i: int, method: str, params: Dict[str, Any] | None = None) -> None:
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))


def run(seconds: float, out_path: Path, keyword: str, cdp_port: int) -> int:
    targets = _match_targets(_list_targets(cdp_port), keyword)
    if not targets:
        print(f"ERROR: no targets matched keyword={keyword!r}")
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    f = out_path.open("w", encoding="utf-8")
    meta = {
        "type": "meta",
        "wall_time_start": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": seconds,
        "keyword": keyword,
        "cdp_port": cdp_port,
        "targets": [
            {"id": t.get("id"), "title": t.get("title"), "url": str(t.get("url") or "")[:300]}
            for t in targets
        ],
    }
    f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    f.flush()

    conns: List[Dict[str, Any]] = []
    for idx, t in enumerate(targets, start=1):
        ws = _connect_target(t)
        _send(ws, idx * 10 + 1, "Network.enable", {"maxTotalBufferSize": 10000000, "maxResourceBufferSize": 5000000})
        _send(ws, idx * 10 + 2, "Page.enable", {})
        conns.append({"ws": ws, "target_id": t.get("id"), "target_url": str(t.get("url") or ""), "req_urls": {}})

    t_end = time.time() + seconds
    line_count = 1
    try:
        while time.time() < t_end:
            idle = True
            for c in conns:
                ws = c["ws"]
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception:
                    continue
                idle = False
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                m = msg.get("method")
                if not m:
                    continue

                row: Dict[str, Any] | None = None
                if m == "Network.requestWillBeSent":
                    p = msg.get("params") or {}
                    req = p.get("request") or {}
                    rid = p.get("requestId")
                    url = str(req.get("url") or "")
                    if isinstance(rid, str):
                        c["req_urls"][rid] = url
                    if any(k in url for k in WATCH_KEYWORDS):
                        h = req.get("headers") if isinstance(req.get("headers"), dict) else {}
                        row = {
                            "type": "req",
                            "t": time.time(),
                            "target_id": c["target_id"],
                            "target_url": c["target_url"][:300],
                            "method": req.get("method"),
                            "url": url[:800],
                            "req_headers": {
                                "Authorization": str(h.get("Authorization") or "").strip(),
                                "Cookie": str(h.get("Cookie") or "").strip(),
                                "Referer": str(h.get("Referer") or "").strip(),
                                "Origin": str(h.get("Origin") or "").strip(),
                                "User-Agent": str(h.get("User-Agent") or "").strip(),
                                "language": str(h.get("language") or h.get("Language") or "").strip(),
                            },
                        }
                elif m == "Network.responseReceived":
                    p = msg.get("params") or {}
                    rid = p.get("requestId")
                    resp = p.get("response") or {}
                    url = str(resp.get("url") or c["req_urls"].get(rid, "") or "")
                    if any(k in url for k in WATCH_KEYWORDS):
                        row = {
                            "type": "resp",
                            "t": time.time(),
                            "target_id": c["target_id"],
                            "target_url": c["target_url"][:300],
                            "status": resp.get("status"),
                            "mime": resp.get("mimeType"),
                            "url": url[:800],
                        }
                elif m == "Page.frameNavigated":
                    p = msg.get("params") or {}
                    frame = p.get("frame") or {}
                    u = str(frame.get("url") or "")
                    if u and not u.startswith("devtools://"):
                        row = {
                            "type": "nav",
                            "t": time.time(),
                            "target_id": c["target_id"],
                            "target_url": c["target_url"][:300],
                            "url": u[:800],
                        }
                elif m == "Page.loadEventFired":
                    row = {
                        "type": "load",
                        "t": time.time(),
                        "target_id": c["target_id"],
                        "target_url": c["target_url"][:300],
                    }

                if row:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    line_count += 1

            if idle:
                time.sleep(0.02)
    finally:
        for c in conns:
            try:
                c["ws"].close()
            except Exception:
                pass
        try:
            f.close()
        except Exception:
            pass

    print("targets:", len(targets))
    print("lines:", line_count)
    print("saved:", out_path)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--keyword", default="icpsp-web-pc")
    ap.add_argument("--cdp-port", type=int, default=9225)
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = args.output or (OUT_DIR / f"manual_cdp_watch_multi_{ts}.jsonl")
    raise SystemExit(run(args.seconds, out, str(args.keyword or ""), int(args.cdp_port)))


if __name__ == "__main__":
    main()

