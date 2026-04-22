#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stage-1 replay: reach "此名称可以申报" (NameCheckInfo resultType=2) via packet evidence.

It extracts the latest successful request from mitm capture jsonl:
  POST /icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo
with resp.code == "00000" and resp.data.resultType == "2",
then replays the same request (auth/cookie/body) and asserts the same outcome.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests


SRC = Path("G:/UFO/政务平台/dashboard/data/records/mitm_ufo_flows.jsonl")
OUT = Path("G:/UFO/政务平台/dashboard/data/records/stage1_replay_namecheck_operation.json")

NEEDLE = "/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo"


def _safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
    try:
        x = json.loads(s)
        return x if isinstance(x, dict) else None
    except Exception:
        return None


def _pick_latest_success() -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    if not SRC.exists():
        raise FileNotFoundError(f"capture not found: {SRC}")

    best_line = -1
    best_req: Optional[Dict[str, Any]] = None
    best_resp: Optional[Dict[str, Any]] = None

    with SRC.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if NEEDLE not in line:
                continue
            rec = _safe_json_loads(line)
            if not rec:
                continue

            if rec.get("method") != "POST":
                continue
            if int(rec.get("status_code") or 0) != 200:
                continue

            resp = _safe_json_loads(rec.get("resp_body") or "")
            if not resp or resp.get("code") != "00000":
                continue
            data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
            if str(data.get("resultType")) != "2":
                continue

            best_line = ln
            best_req = rec
            best_resp = resp

    if best_line < 0 or not best_req or not best_resp:
        raise RuntimeError(f"no successful stage1 packet found in {SRC} (needle={NEEDLE})")
    return best_line, best_req, best_resp


def _mk_replay_headers(req_headers: Dict[str, Any]) -> Dict[str, str]:
    # Keep only what's needed for API auth + CORS expectations.
    keep = (
        "Authorization",
        "language",
        "Content-Type",
        "Origin",
        "Referer",
        "User-Agent",
        "Accept",
        "Cookie",
    )
    out: Dict[str, str] = {}
    for k in keep:
        v = req_headers.get(k)
        if v is None:
            continue
        out[k] = str(v)
    if "Accept" not in out:
        out["Accept"] = "application/json, text/plain, */*"
    if "Content-Type" not in out:
        out["Content-Type"] = "application/json"
    if "language" not in out:
        out["language"] = "CH"
    return out


def _redact_sensitive(h: Dict[str, str]) -> Dict[str, Any]:
    auth = h.get("Authorization") or ""
    cookie = h.get("Cookie") or ""
    return {
        "Authorization_tail": auth[-6:] if auth else "",
        "Authorization_sha1": hashlib.sha1(auth.encode("utf-8")).hexdigest() if auth else "",
        "Cookie_len": len(cookie),
        "Cookie_sha1": hashlib.sha1(cookie.encode("utf-8")).hexdigest() if cookie else "",
        "Referer": h.get("Referer") or "",
        "Origin": h.get("Origin") or "",
        "User-Agent": (h.get("User-Agent") or "")[:80],
        "language": h.get("language") or "",
        "Content-Type": h.get("Content-Type") or "",
    }


def main() -> None:
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    line_no, req, resp0 = _pick_latest_success()

    url = str(req.get("url") or "")
    req_headers = req.get("req_headers") if isinstance(req.get("req_headers"), dict) else {}
    body_raw = str(req.get("req_body") or "")
    body = _safe_json_loads(body_raw)
    if not body:
        raise RuntimeError("request body is not valid json")

    headers = _mk_replay_headers(req_headers)
    if not headers.get("Authorization"):
        raise RuntimeError("missing Authorization in captured request headers")
    if not headers.get("Cookie"):
        # Some sessions rely solely on Authorization, but in this platform Cookie often matters.
        raise RuntimeError("missing Cookie in captured request headers")

    s = requests.Session()
    r = s.post(url, headers=headers, json=body, timeout=30)
    text = r.text
    resp1 = _safe_json_loads(text)

    ok = (
        r.status_code == 200
        and isinstance(resp1, dict)
        and resp1.get("code") == "00000"
        and isinstance(resp1.get("data"), dict)
        and str(resp1["data"].get("resultType")) == "2"
    )

    out = {
        "started_at": started_at,
        "ended_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "picked_from_mitm": {
            "line_no": line_no,
            "url": url,
            "captured_status_code": req.get("status_code"),
            "captured_resp_code": (resp0.get("code") if isinstance(resp0, dict) else None),
            "captured_resultType": (
                (resp0.get("data") or {}).get("resultType")
                if isinstance(resp0, dict) and isinstance(resp0.get("data"), dict)
                else None
            ),
        },
        "replay_request": {
            "headers_redacted": _redact_sensitive(headers),
            "body": body,
        },
        "replay_response": {
            "http_status": r.status_code,
            "json": resp1 if isinstance(resp1, dict) else None,
            "text_cut": text[:2000],
        },
        "assertion": {
            "ok": bool(ok),
            "expect": {"http_status": 200, "code": "00000", "resultType": "2"},
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if not ok:
        raise SystemExit(f"stage1 replay failed, saved: {OUT}")
    print(f"stage1 replay OK, saved: {OUT}")


if __name__ == "__main__":
    main()

