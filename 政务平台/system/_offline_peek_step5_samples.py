"""详看 4 条首次保存样本的关键字段，找差异规律。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))
from phase1_protocol_driver import API_NC_OP  # noqa: E402

mitm = ROOT / "dashboard/data/records/mitm_ufo_flows_backup_20260421_231343.jsonl"
samples: List[Dict[str, Any]] = []
with mitm.open("r", encoding="utf-8", errors="replace") as f:
    for ln, line in enumerate(f, 1):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if API_NC_OP not in str(rec.get("url") or ""):
            continue
        if rec.get("method") != "POST":
            continue
        req_body = rec.get("req_body") or ""
        try:
            body = json.loads(req_body) if isinstance(req_body, str) else req_body
        except Exception:
            continue
        samples.append({"line": ln, "status": rec.get("status_code"), "body": body, "resp_body": rec.get("resp_body", "")[:300]})

first = [s for s in samples if not s["body"].get("nameCheckDTO")]

KEYS = ["nameMark", "namePre", "spellType", "industry", "industryName", "industrySpecial", "organize", "entType", "name", "distCode", "signInfo", "checkState"]

print(f"=== {len(first)} 条首次保存样本 ===\n")
for s in first:
    b = s["body"]
    print(f"L{s['line']} status={s['status']}")
    for k in KEYS:
        v = b.get(k, "__MISSING__")
        print(f"  {k:18s}: {json.dumps(v, ensure_ascii=False)}")
    # 响应码
    try:
        resp = json.loads(s["resp_body"]) if s["resp_body"] else {}
        rcode = resp.get("code")
        rtype = (resp.get("data") or {}).get("resultType")
    except Exception:
        rcode = rtype = None
    print(f"  ├─ resp.code={rcode}  resultType={rtype}")
    print()
