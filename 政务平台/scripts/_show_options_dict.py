"""Show options_dict.json content cleanly."""
import sys
sys.path.insert(0, 'system')
from governance import OptionDict

od = OptionDict.load()
print(f"=== options_dict.json 最终状态 ===")
print(f"字段总数: {len(od.fields)}\n")
must_total = 0
meta_count = 0
enum_count = 0
for fname, f in sorted(od.fields.items()):
    if fname.startswith("_fieldList_"):
        must = sum(1 for o in f.options if o.extra.get("must_flag") == "1")
        must_total += must
        meta_count += 1
        print(f"  [meta] {fname:42s} ×{len(f.options):3d}  必填 {must}")
    else:
        enum_count += 1
        sample = ", ".join([f"{o.code}={o.name[:10]}" for o in f.options[:5]])
        print(f"  [enum] {fname:42s} ×{len(f.options):3d}  {sample}")

print(f"\n汇总：")
print(f"  字段元数据组: {meta_count}（含 {must_total} 个必填字段）")
print(f"  真实枚举字段: {enum_count}")
