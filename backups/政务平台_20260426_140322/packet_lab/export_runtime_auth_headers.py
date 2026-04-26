#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export latest usable auth headers for container runtime.

Purpose:
- Keep official login flow unchanged (user scans in browser).
- Extract latest Authorization/Cookie from local capture artifacts.
- Write a runtime-only headers file for container automation.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path("G:/UFO/政务平台")
RECORDS = ROOT / "dashboard" / "data" / "records"
DEFAULT_OUT = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except FileNotFoundError:
        return


def _is_auth32(v: str) -> bool:
    v = (v or "").strip()
    return len(v) == 32


def _pack_headers(h: Dict[str, Any], url: str = "") -> Optional[Dict[str, str]]:
    auth = str(h.get("Authorization") or "").strip()
    if not _is_auth32(auth):
        return None
    cookie = str(h.get("Cookie") or "").strip()
    referer = str(h.get("Referer") or "").strip()
    origin = str(h.get("Origin") or "https://zhjg.scjdglj.gxzf.gov.cn:9087").strip()
    out = {
        "Authorization": auth,
        "language": str(h.get("language") or h.get("Language") or "CH"),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": origin,
        "Referer": referer or "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
        "User-Agent": str(h.get("User-Agent") or "Mozilla/5.0"),
    }
    if cookie:
        out["Cookie"] = cookie
    return out


def pick_from_cdp(records_dir: Path) -> Optional[Dict[str, str]]:
    files = sorted(records_dir.glob("manual_cdp_watch*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for fp in files:
        rows = list(_iter_jsonl(fp))
        for rec in reversed(rows):
            if rec.get("type") != "req":
                continue
            url = str(rec.get("url") or "")
            if "/icpsp-api/" not in url:
                continue
            h = rec.get("req_headers")
            if not isinstance(h, dict):
                continue
            packed = _pack_headers(h, url=url)
            if packed:
                return {"headers": packed, "source_file": str(fp), "source_url": url}
    return None


def pick_from_mitm(mitm_path: Path) -> Optional[Dict[str, str]]:
    rows = list(_iter_jsonl(mitm_path))
    for rec in reversed(rows):
        h = rec.get("req_headers")
        if not isinstance(h, dict):
            continue
        packed = _pack_headers(h, url=str(rec.get("url") or ""))
        if packed:
            return {"headers": packed, "source_file": str(mitm_path), "source_url": str(rec.get("url") or "")}
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Export runtime auth headers for container use")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON file path")
    ap.add_argument("--mitm", type=Path, default=RECORDS / "mitm_ufo_flows.jsonl", help="Fallback mitm jsonl")
    args = ap.parse_args()

    picked = pick_from_cdp(RECORDS) or pick_from_mitm(args.mitm)
    if not picked:
        raise SystemExit("ERROR: no usable Authorization found in CDP or mitm artifacts")
    headers = dict(picked.get("headers") or {})

    payload = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Runtime-only auth headers extracted from local captures. Do not commit.",
        "base_url": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "source": {
            "file": picked.get("source_file"),
            "url": picked.get("source_url"),
        },
        "headers": headers,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", args.out)
    print("source", payload.get("source"))


if __name__ == "__main__":
    main()
