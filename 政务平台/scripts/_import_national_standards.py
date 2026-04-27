"""把 data/national_standard_enums.json 合并进 OptionDict。

策略：upsert 模式 — 对每个字段，新 code 添加，已存在的 code 保留（Scout 数据优先）。
保证 Scout 学到的实际值不会被覆盖。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'system')
from governance import OptionDict


def main():
    src = Path("data/national_standard_enums.json")
    if not src.exists():
        print(f"❌ 找不到 {src}")
        return 1

    raw = json.load(open(src, "r", encoding="utf-8"))
    od = OptionDict.load()

    print(f"=== 国标枚举包合并 ===\n")
    total_added = 0
    total_fields = 0
    for fname, fdata in raw["fields"].items():
        opts = fdata.get("options", [])
        label = fdata.get("label", fname)
        std = fdata.get("standard", "")
        existing = od.get_field(fname)
        before = len(existing.options) if existing else 0

        added = od.upsert_options(
            field_name=fname,
            options=opts,
            label=label,
            source=f"national_standard:{std}",
        )
        after = len(od.get_field(fname).options)
        total_added += added
        total_fields += 1
        print(f"  {fname:30s} 标准={std:20s} +{added}/{len(opts)} 项 (字典 {before}→{after})")

    od.save()
    print(f"\n✅ 已合并 {total_fields} 个字段，新增 {total_added} 项 → {od.path}")

    # 显示最终状态
    print(f"\n=== 最终字典 ({len(od.fields)} 字段) ===")
    for fname, f in sorted(od.fields.items()):
        if fname.startswith("_fieldList_"):
            continue
        sample = ", ".join(o.name[:8] for o in f.options[:4])
        print(f"  {fname:30s} ×{len(f.options):3d}  {sample}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
