#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 mitm JSONL 中归纳「登录态」在协议层的落点（脱敏），供逆向/自动化对接用。
不写回明文 Token；输出到 out/login_context_report.json
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

MITM = Path(os.environ.get("MITM_JSONL", "/data/mitm_ufo_flows.jsonl"))
OUT_DIR = Path(os.environ.get("LAB_OUT", "/lab/out"))
OUT = OUT_DIR / "login_context_report.json"


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _cookie_names(cookie: str) -> List[str]:
    out: List[str] = []
    for part in (cookie or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        out.append(part.split("=", 1)[0].strip())
    return out


def main() -> None:
    if not MITM.is_file():
        raise SystemExit(f"mitm file not found: {MITM}")

    last_auth: Optional[str] = None
    last_cookie: Optional[str] = None
    auth_hashes: Set[str] = set()
    lines_seen = 0

    with MITM.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            lines_seen += 1
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            h = o.get("req_headers")
            if not isinstance(h, dict):
                continue
            auth = h.get("Authorization")
            if isinstance(auth, str) and auth.strip():
                last_auth = auth.strip()
                auth_hashes.add(_sha256(last_auth))
            ck = h.get("Cookie")
            if isinstance(ck, str) and ck.strip():
                last_cookie = ck.strip()

    report: Dict[str, Any] = {
        "mitm_path": str(MITM),
        "lines_scanned": lines_seen,
        "login_state_on_wire": {
            "summary": "Primary: Authorization (32 hex) + Cookie; aligns with portal localStorage (see 政务平台/README.md auth table).",
            "authorization": {
                "present": bool(last_auth),
                "len": len(last_auth or ""),
                "sha256": _sha256(last_auth) if last_auth else None,
                "tail6": (last_auth or "")[-6:] if last_auth else None,
            },
            "cookie": {
                "present": bool(last_cookie),
                "len_bytes": len((last_cookie or "").encode("utf-8")),
                "name_list": _cookie_names(last_cookie or "") if last_cookie else [],
                "sha256": _sha256(last_cookie) if last_cookie else None,
            },
            "distinct_authorization_sha256_count": len(auth_hashes),
        },
        "automation_guidance": [
            "Automation: inject headers from CDP Runtime localStorage, or use scripts/api_gateway.py token sync.",
            "Lab hygiene: analyze redacted copies; do not commit raw mitm lines with secrets to remote git.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
