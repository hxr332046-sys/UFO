#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mitmproxy addon: capture target hosts to JSONL
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from mitmproxy import ctx, http

# 与脚本位置绑定，避免从其它 cwd 启动 mitmdump 时写错路径
_OUT_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records"
OUT = _OUT_DIR / "mitm_ufo_flows.jsonl"
TARGET_KEYS = (
    "zhjg.scjdglj.gxzf.gov.cn:6087",
    "zhjg.scjdglj.gxzf.gov.cn:9087",
    "/icpsp-api/",
    "/TopIP/",
)


def _hit(url: str) -> bool:
    u = (url or "").lower()
    return any(k.lower() in u for k in TARGET_KEYS)


def _cut(v: bytes | str | None, n: int = 50000) -> str:
    if v is None:
        return ""
    if isinstance(v, bytes):
        try:
            s = v.decode("utf-8", "replace")
        except Exception:
            s = repr(v)
    else:
        s = str(v)
    return s[:n]


def response(flow: http.HTTPFlow) -> None:
    url = flow.request.pretty_url
    if not _hit(url):
        return
    rec = {
        "ts": int(time.time() * 1000),
        "method": flow.request.method,
        "url": url,
        "req_headers": dict(flow.request.headers),
        "req_body": _cut(flow.request.raw_content),
        "status_code": flow.response.status_code if flow.response else None,
        "resp_headers": dict(flow.response.headers) if flow.response else {},
        "resp_body": _cut(flow.response.raw_content if flow.response else b""),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    ctx.log.info(f"[mitm] {rec['method']} {rec['url']} -> {rec['status_code']}")

