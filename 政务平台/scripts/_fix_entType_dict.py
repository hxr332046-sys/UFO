"""修正 entType 字典：从 phase1_service/ent_types_type1.json 的 enttypes 树展平。

之前用 ent_type_codes.json 体系不一致（缺 4540 个人独资）。这里改用服务端实际接受的体系。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'system')
from governance import OptionDict


def main():
    od = OptionDict.load()
    # 先清掉旧的 entType（采用错误的体系）
    if "entType" in od.fields:
        old = od.fields["entType"]
        print(f"清除旧 entType ({len(old.options)} 项, 来源 {old.source})")
        del od.fields["entType"]

    # 从 ent_types_type1.json 重建
    options = []
    seen = set()
    for fname in ["ent_types_type1.json", "ent_types_type2.json"]:
        fp = Path(f"phase1_service/data/dictionaries/{fname}")
        if not fp.exists():
            continue
        d = json.load(open(fp, "r", encoding="utf-8"))
        busi = d.get("data", {}).get("data", {}).get("busiData", {})
        if not isinstance(busi, dict):
            continue

        def walk(node, depth=0):
            if not isinstance(node, dict):
                return
            code = str(node.get("code") or "")
            name = node.get("name") or ""
            parcode = node.get("parcode")
            if code and code not in seen:
                seen.add(code)
                options.append({
                    "code": code,
                    "name": name,
                    "parent": str(parcode) if parcode else None,
                    "depth": depth,
                    "show_type": node.get("showType"),
                    "use_type": node.get("usetype"),
                })
            for ch in node.get("child", []) or []:
                walk(ch, depth + 1)

        # 处理 pagetypes 和 enttypes 两个分支
        for branch in ("enttypes", "pagetypes"):
            for root in busi.get(branch, []):
                walk(root, 0)

    if not options:
        print("❌ 没找到任何 entType 数据")
        return 1

    added = od.upsert_options(
        field_name="entType",
        options=options,
        label="企业类型代码（服务端实际体系，含个人独资 4540 等）",
        source="phase1_service:ent_types_type1.json:enttypes",
    )
    od.save()

    print(f"✅ entType 重建：共 {len(options)} 项（新增 {added}）")
    f = od.get_field("entType")
    print(f"  4540 (个人独资): {f.find_by_code('4540').name if f.find_by_code('4540') else '❌ 仍缺失'}")
    print(f"  4530 (个体工商户): {f.find_by_code('4530').name if f.find_by_code('4530') else '❌ 仍缺失'}")
    print(f"  1100 (有限责任公司): {f.find_by_code('1100').name if f.find_by_code('1100') else '❌ 仍缺失'}")
    print(f"  9100 (农民专业合作社): {f.find_by_code('9100').name if f.find_by_code('9100') else '❌ 仍缺失'}")

    print(f"\n  全部 codes: {sorted([o.code for o in f.options])[:50]}")


if __name__ == "__main__":
    sys.exit(main())
