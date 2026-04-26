"""E2E 测试：用真实 case 调 POST /api/phase1/register，看能否拿到 busiId。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CASE_FILE = ROOT / "docs/case_广西容县李陈梦.json"
API = "http://127.0.0.1:8800/api/phase1/register"

case = json.loads(CASE_FILE.read_text(encoding="utf-8"))
body = {"case": case}  # authorization 省略 → 用服务端 runtime_auth_headers.json 里的

print("=" * 70)
print(f"E2E 测试 POST {API}")
print(f"company_name_phase1_normalized: {case['company_name_phase1_normalized']}")
print(f"entType: {case['entType_default']}  dist_codes: {case['phase1_dist_codes']}")
print("=" * 70)

try:
    r = requests.post(API, json=body, timeout=120)
except Exception as e:
    print(f"HTTP 异常: {e!r}")
    sys.exit(1)

print(f"\nHTTP status: {r.status_code}")
try:
    d = r.json()
except Exception:
    print(r.text[:1500])
    sys.exit(2)

print(f"\nsuccess   : {d.get('success')}")
print(f"busiId    : {d.get('busiId')}")
print(f"checkState: {d.get('checkState')}")
print(f"hit_count : {d.get('hit_count')}")
print(f"latency_ms: {d.get('latency_ms')}")
print(f"reason    : {d.get('reason')}")

print(f"\n-- steps --")
for s in d.get("steps") or []:
    status = "OK" if s.get("ok") else "!!"
    print(f"  [{status}] {s.get('name'):26s}  code={s.get('code'):>8s}  msg={(s.get('msg') or '')[:50]}")

similar = d.get("similar_names") or []
if similar:
    print(f"\n-- similar names ({len(similar)}) --")
    for n in similar[:8]:
        print(f"  - {n}")
