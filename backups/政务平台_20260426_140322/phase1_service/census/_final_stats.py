"""Wave 1 最终统计：第一阶段字典/经营范围入库总览。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "phase1_service/data/dictionaries"

print("=" * 72)
print("  第一阶段名称登记服务 · Wave 1 产出总览  (2026-04-22)")
print("=" * 72)

# Tier A 产出
print("\n## Tier A · 无参数字典")
print("-" * 50)
tier_a_files = [
    ("企业类型 type1", "ent_types_type1.json"),
    ("企业类型 type2", "ent_types_type2.json"),
    ("全国行政区划", "regions/root.json"),
    ("行业大类码", "code_lists/MOKINDCODE.json"),
    ("证件类型码", "code_lists/CERTYPECODE.json"),
    ("系统参数", "sys_params.json"),
    ("连号类型", "serial_type_code.json"),
    ("租赁房屋码", "rental_house_code.json"),
    ("登记业务模块", "business_modules.json"),
    ("行业特征提示配置", "sys_configs/noIndSpeTips.json"),
    ("事项类型", "matter_types.json"),
    ("事项状态", "matter_states.json"),
]
for name, rel in tier_a_files:
    p = DATA / rel
    sz = f"{p.stat().st_size/1024:.1f} KB" if p.exists() else "MISSING"
    mark = "✓" if p.exists() else "✗"
    print(f"  {mark}  {name:20s}  {sz:>10s}   {rel}")

# Seeded from dict_cache
print("\n## Seed（从 dict_cache 零消耗移植）")
print("-" * 50)
seed_files = [
    ("industries/4540", "industries/entType_4540_busi_01.json"),
    ("industries/1100", "industries/entType_1100_busi_01.json"),
    ("organizes/4540", "organizes/entType_4540_busi_01.json"),
    ("organizes/1100", "organizes/entType_1100_busi_01.json"),
    ("ent_type_cfg/4540", "ent_type_cfgs/entType_4540.json"),
    ("ent_type_cfg/1100", "ent_type_cfgs/entType_1100.json"),
]
for name, rel in seed_files:
    p = DATA / rel
    sz = f"{p.stat().st_size/1024:.1f} KB" if p.exists() else "MISSING"
    mark = "✓" if p.exists() else "✗"
    print(f"  {mark}  {name:20s}  {sz:>10s}   {rel}")

# Tier D 经营范围
print("\n## Tier D · 经营范围（Wave 1 = L1 seeds × 01）")
print("-" * 50)
scope_dir = DATA / "business_scopes"
total_files = 0
total_rows = 0
for sub in sorted(scope_dir.iterdir()):
    if not sub.is_dir():
        continue
    files = list(sub.glob("*.json"))
    rows = 0
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            resp = d.get("data") or {}
            inner = resp.get("data") if isinstance(resp, dict) else None
            bd = inner.get("busiData") if isinstance(inner, dict) else None
            if bd is None and isinstance(resp, dict):
                bd = resp.get("busiData")
            if isinstance(bd, list):
                rows += len(bd)
        except Exception:
            pass
    print(f"  ✓  {sub.name:35s}  {len(files):>3d} 关键词  {rows:>6d} 条经营范围")
    total_files += len(files)
    total_rows += rows

print("-" * 50)
print(f"  合计:  {total_files} 关键词  /  {total_rows} 条经营范围")
print("=" * 72)

# API 端点演示
print("\n## API 端点（基于本次入库可立即调用）")
print("-" * 50)
endpoints = [
    "GET  /api/phase1/dict/ent-types?level=1       → 企业类型字典",
    "GET  /api/phase1/dict/industries/4540         → 个独企业行业码（1971 条）",
    "GET  /api/phase1/dict/industries/1100         → 有限公司行业码",
    "GET  /api/phase1/dict/organizes/4540          → 个独组织形式",
    "GET  /api/phase1/dict/regions                 → 行政区划树",
    "GET  /api/phase1/scope?entType=4540&busiType=01&keyword=软件开发  ← ★ 19 条",
    "GET  /api/phase1/scope?entType=4540&busiType=01&keyword=农业      ← 300 条",
    "GET  /api/phase1/scope?entType=1100&busiType=01&keyword=食品      ← 待查",
    "POST /api/phase1/register  { case, authorization }    → 执行 7 步拿 busiId",
]
for ep in endpoints:
    print(f"  {ep}")

print()
print(f"Swagger 交互文档:  http://127.0.0.1:8800/docs")
