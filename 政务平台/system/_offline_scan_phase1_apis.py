"""扫描 mitm 备份，列出第一阶段（guide/namecheck）可能用到的所有接口，
带上采样 URL、请求参数、响应 keys、经营范围相关 flag。"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
mitm = ROOT / "dashboard/data/records/mitm_ufo_flows_backup_20260421_231343.jsonl"

# 第一阶段的接口前缀（guide + common/synchrdata + name/register + 与核名直接相关）
PHASE1_PATH_FRAGMENTS = [
    "/register/guide/",
    "/register/name/",
    "/register/verifidata/",
    "/common/synchrdata/",
    "/common/configdata/",
    "/common/codedata/",
    "/common/tools/",
]

# 经营范围相关关键词（用于在 resp 里高亮）
SCOPE_KEYWORDS = ["industryFeat", "businessScope", "scope", "desc", "jyfwms", "jyfw"]

api_bucket: dict[str, list] = defaultdict(list)

with mitm.open("r", encoding="utf-8", errors="replace") as f:
    for ln, line in enumerate(f, 1):
        try:
            r = json.loads(line)
        except Exception:
            continue
        u = str(r.get("url") or "")
        if "/icpsp-api/" not in u:
            continue
        path = u.split("?")[0]
        qs = u.split("?")[1] if "?" in u else ""
        if not any(frag in path for frag in PHASE1_PATH_FRAGMENTS):
            continue
        status = r.get("status_code")
        req_body = r.get("req_body") or ""
        resp_body = r.get("resp_body") or ""
        api_bucket[path].append({
            "line": ln,
            "method": r.get("method"),
            "qs": qs[:200],
            "req_len": len(req_body),
            "resp_len": len(resp_body),
            "status": status,
            "req_body": req_body[:400],
            "resp_body": resp_body[:800],
        })

print("=" * 80)
print(f"第一阶段可能涉及的接口总计：{len(api_bucket)} 个")
print("=" * 80)

# 按调用频次排序
for path, samples in sorted(api_bucket.items(), key=lambda x: -len(x[1])):
    s = samples[0]
    short = path.replace("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/", "")
    print(f"\n● {short}   ({len(samples)} 次调用)")
    print(f"  method={s['method']}  status={s['status']}  req={s['req_len']}B  resp={s['resp_len']}B")
    if s["qs"]:
        print(f"  qs: {s['qs'][:120]}")
    # 探测经营范围关键字
    scope_hits = [kw for kw in SCOPE_KEYWORDS if kw.lower() in s["resp_body"].lower()]
    if scope_hits:
        print(f"  ★ 经营范围相关 keywords: {scope_hits}")
    # 请求参数 keys
    if s["method"] == "POST" and s["req_body"]:
        try:
            b = json.loads(s["req_body"].rstrip())
            if isinstance(b, dict):
                print(f"  req keys: {sorted(b.keys())[:12]}")
        except Exception:
            pass
    # 响应 data key 预览
    try:
        rp = json.loads(s["resp_body"].rstrip())
        d = rp.get("data") if isinstance(rp, dict) else None
        if isinstance(d, dict):
            print(f"  resp.data keys: {sorted(d.keys())[:10]}")
            bd = d.get("busiData")
            if isinstance(bd, list) and bd:
                print(f"  resp.data.busiData is list, len={len(bd)}, item0 keys: {sorted(list(bd[0].keys())[:8]) if isinstance(bd[0], dict) else type(bd[0]).__name__}")
            elif isinstance(bd, dict):
                print(f"  resp.data.busiData is dict, keys: {sorted(bd.keys())[:10]}")
    except Exception:
        pass
