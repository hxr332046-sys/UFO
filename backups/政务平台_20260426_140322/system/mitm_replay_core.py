#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared helpers: replay one mitm JSON line (icpsp-api) with captured headers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

SKIP_HDR = frozenset(
    x.lower()
    for x in (
        "Host",
        "Connection",
        "Content-Length",
        "Keep-Alive",
        "Transfer-Encoding",
        "Upgrade",
        "TE",
        "Accept-Encoding",
    )
)


def clean_headers(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or v is None:
            continue
        if k.lower() in SKIP_HDR:
            continue
        out[k] = str(v)
    return out


def pick_body(rec: Dict[str, Any]) -> Tuple[bytes, bool]:
    ct = ""
    rh = rec.get("req_headers")
    if isinstance(rh, dict):
        for a, b in rh.items():
            if isinstance(a, str) and a.lower() == "content-type":
                ct = str(b).lower()
                break
    body = rec.get("req_body")
    if body is None or body == "":
        return b"", "json" in ct
    if isinstance(body, str):
        return body.encode("utf-8"), "json" in ct
    return bytes(body), "json" in ct


def load_icpsp_slice(mitm: Path, skip_lines: int, max_records: int) -> List[Tuple[int, Dict[str, Any]]]:
    """Return list of (1-based line number in file, record dict) for icpsp-api rows."""
    out: List[Tuple[int, Dict[str, Any]]] = []
    line_no = 0
    with mitm.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_no += 1
            if line_no <= skip_lines:
                continue
            if len(out) >= max_records:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = rec.get("url")
            if not isinstance(url, str) or "icpsp-api" not in url:
                continue
            out.append((line_no, rec))
    return out


def replay_one_record(sess: requests.Session, rec: Dict[str, Any], line_no: int) -> Dict[str, Any]:
    url = rec.get("url")
    method = (rec.get("method") or "GET").upper()
    if not isinstance(url, str):
        return {"mitm_line": line_no, "error": "bad url"}
    headers = clean_headers(rec.get("req_headers"))
    body_b, _ = pick_body(rec)
    t0 = time.time()
    try:
        if method == "GET":
            r = sess.request("GET", url, headers=headers, timeout=45)
        elif method == "POST":
            r = sess.request("POST", url, headers=headers, data=body_b, timeout=45)
        else:
            r = sess.request(method, url, headers=headers, data=body_b or None, timeout=45)
        dt = time.time() - t0
        body_text = r.text or ""
        snippet = body_text[:400].replace("\r", " ").replace("\n", " ")
        resp_json: Any = None
        try:
            ct = (r.headers.get("Content-Type") or "").lower()
            if "json" in ct or (body_text[:1] in "{["):
                resp_json = r.json()
        except Exception:
            resp_json = None
        return {
            "mitm_line": line_no,
            "method": method,
            "url": url[:300],
            "http_status": r.status_code,
            "elapsed_sec": round(dt, 3),
            "resp_snippet": snippet,
            "resp_json": resp_json,
        }
    except Exception as e:
        return {"mitm_line": line_no, "method": method, "url": str(url)[:300], "error": repr(e)}
