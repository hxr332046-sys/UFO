"""快速检视 Tier D 已产出的经营范围数据。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
base = ROOT / "phase1_service/data/dictionaries/business_scopes/entType_4540_busi_01"

if not base.exists():
    print(f"{base} 不存在")
    sys.exit(1)

files = sorted(base.glob("*.json"))
print(f"entType=4540  busiType=01  已产出文件数: {len(files)}")
if not files:
    sys.exit(0)

# 看 3 个样本（前/中/末）
for idx in (0, len(files) // 2, len(files) - 1):
    f = files[idx]
    d = json.loads(f.read_text(encoding="utf-8"))
    meta = d.get("meta", {}) or {}
    kw = meta.get("keyword") or "?"
    resp = d.get("data") or {}
    bd = None
    inner = resp.get("data") if isinstance(resp, dict) else None
    if isinstance(inner, dict):
        bd = inner.get("busiData")
    if bd is None and isinstance(resp, dict):
        bd = resp.get("busiData")

    print("\n" + "-" * 60)
    print(f"样本 [{idx}]  kw='{kw}'  文件={f.name}")
    print(f"  resp.code={resp.get('code')}  resp.msg={resp.get('msg')}")
    if isinstance(bd, list):
        print(f"  busiData 是 list，共 {len(bd)} 条")
        if bd:
            first = bd[0]
            if isinstance(first, dict):
                print(f"  首条 keys: {list(first.keys())[:12]}")
                print(f"  首条: {json.dumps(first, ensure_ascii=False)[:300]}")
    elif isinstance(bd, dict):
        print(f"  busiData 是 dict, keys: {list(bd.keys())[:10]}")
        print(f"  内容预览: {json.dumps(bd, ensure_ascii=False)[:400]}")
    elif bd is None:
        print(f"  busiData = None (服务端无匹配)")
    else:
        print(f"  busiData = {type(bd).__name__}: {str(bd)[:200]}")

# 统计有效/空
empty = 0
non_empty = 0
total_rows = 0
for f in files:
    d = json.loads(f.read_text(encoding="utf-8"))
    resp = d.get("data") or {}
    inner = resp.get("data") if isinstance(resp, dict) else None
    bd = inner.get("busiData") if isinstance(inner, dict) else None
    if bd is None:
        bd = resp.get("busiData") if isinstance(resp, dict) else None
    if isinstance(bd, list):
        if bd:
            non_empty += 1
            total_rows += len(bd)
        else:
            empty += 1
    else:
        empty += 1

print("\n" + "=" * 60)
print(f"汇总: {len(files)} 个关键词 / 非空 {non_empty} / 空 {empty} / 总条数 {total_rows}")
print(f"命中率: {non_empty * 100 // max(1, len(files))}%")
