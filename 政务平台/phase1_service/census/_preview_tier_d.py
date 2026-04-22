"""Tier D 预览：不发请求，仅统计将要跑的 (entType, busiType, hyPecul) 组合数量。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from phase1_service.census.registry.tier_d import (  # noqa: E402
    _load_seed_keywords,
    _collect_from_industry_names,
    _extract_hypecul_from_industries,
)

DATA_DIR = ROOT / "phase1_service/data"
PLAN_PATH = ROOT / "phase1_service/census/census_plan.json"

plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
td = plan["tier_d_business_scope"]
busi_types = td.get("busi_types", ["01"])

# 扫描已有的 entType 数据
industries_dir = DATA_DIR / "dictionaries/industries"
ent_types = sorted({
    fn.stem.split("_")[1]
    for fn in industries_dir.glob("entType_*_busi_*.json")
})

print("=" * 70)
print(f"Tier D · 经营范围预览")
print("=" * 70)
print(f"已就绪 entType:   {ent_types}")
print(f"busiType(plan):  {busi_types}")
print()

seeds = _load_seed_keywords()
print(f"L1 种子关键词 (hypecul_seeds.json): {len(seeds)}")
print(f"  示例: {sorted(seeds)[:10]}")

total = 0
for et in ent_types:
    for bt in busi_types:
        names_kws = _collect_from_industry_names(DATA_DIR, et, bt)
        all_kws = _extract_hypecul_from_industries(DATA_DIR, et, bt)
        print(f"\nentType={et}  busiType={bt}:")
        print(f"  industry-name 切片贡献: {len(names_kws)}")
        print(f"  合并总关键词数:      {len(all_kws)}")
        print(f"  样本（前 15）:       {sorted(all_kws)[:15]}")
        total += len(all_kws)

print()
print("-" * 70)
print(f"合计请求数估算: {total}")
print(f"按 2.5s/请求，预估耗时: {total * 2.5 / 60:.1f} 分钟 = {total * 2.5 / 3600:.2f} 小时")
print(f"建议: 如 > 1500，可用 --limit_per_ent_type N 限制每个 entType 的前 N 个关键词")
print("-" * 70)
