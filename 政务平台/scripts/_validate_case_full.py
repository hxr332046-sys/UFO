"""用最新字典对现有 case 做深度质检。

对比：
- 启用前 28 字段检查
- 启用后 30 字段 / 777+ 项数据下能识别多少不一致 / 命中多少枚举字段
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'system')
from governance import CaseValidator, OptionDict, IndustryMatcher


def main():
    case_path = Path("docs/case_兴裕为.json")
    case = json.load(open(case_path, "r", encoding="utf-8"))

    od = OptionDict.load()
    im = IndustryMatcher.load()

    print(f"=== Case 质检（基于 30 字段 / 777+ 项字典） ===\n")
    print(f"Case: {case_path.name}")
    print(f"  公司: {case.get('phase1_check_name', '?')}")
    print(f"  字典: {len(od.fields)} 字段")
    print()

    v = CaseValidator(option_dict=od, industry_matcher=im)
    rep = v.validate(case)

    print(f"质检结果:")
    print(f"  字段检查总数: {rep.checked_fields}")
    print(f"  ✅ pass:      {rep.checked_fields - len(rep.issues)}")
    print(f"  ❌ fail:      {len(rep.fails)}")
    print(f"  ⚠ warn:      {len(rep.warns)}")
    print(f"  ❓ ambiguous: {len(rep.ambiguous)}")
    print()

    if rep.issues:
        print(f"问题清单：")
        for it in rep.issues:
            tag = {"fail": "❌", "ambiguous": "❓", "warn": "⚠"}.get(it.level.value, "·")
            print(f"  {tag} [{it.level.value}] {it.field_path} = {it.case_value!r}")
            print(f"      {it.message}")
            for c in (it.candidates or [])[:3]:
                score = c.get("score")
                print(f"        - {c.get('code','?')} {c.get('name','?')}"
                      + (f"  (score={score})" if score is not None else ""))

    # 主动对 case 中所有 *Code 字段做一次反查（即使 CaseValidator 没检查）
    print(f"\n=== 字典覆盖度自检（深度反查 case 字段） ===\n")

    def walk_case(node, prefix=""):
        if isinstance(node, dict):
            for k, val in node.items():
                p = f"{prefix}.{k}" if prefix else k
                yield p, k, val
                yield from walk_case(val, p)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from walk_case(item, f"{prefix}[{i}]")

    coverage_hit = []
    coverage_miss = []
    for path, key, val in walk_case(case):
        if not isinstance(val, (str, int)) or val == "" or val is None:
            continue
        # 只对 Code/Type/Status/Flag/Sex/Visage 类字段反查
        if not any(s in key for s in ["Code", "Type", "Status", "Flag", "Sex", "code", "Mark"]):
            continue
        if key in ("entType_default", "busiType_default"):
            continue
        # 在字典里查
        f = od.get_field(key)
        if f is None:
            # 试 lower 形式或去后缀
            for cand in (key.lower(), key.rstrip("Code") + "Code"):
                f = od.get_field(cand)
                if f:
                    break
        if f:
            opt = f.find_by_code(str(val))
            if opt:
                coverage_hit.append((path, key, val, opt.name))
            else:
                coverage_miss.append((path, key, val, f"字典 {key} 不含 code={val}"))

    print(f"  ✅ 命中字典: {len(coverage_hit)} 个字段")
    for path, key, val, name in coverage_hit[:15]:
        print(f"    {path:40s} = {val:8s}  → {name}")
    if len(coverage_hit) > 15:
        print(f"    ... ({len(coverage_hit) - 15} more)")

    if coverage_miss:
        print(f"\n  ❌ 字典里有该字段但 case 值非法: {len(coverage_miss)}")
        for path, key, val, msg in coverage_miss[:10]:
            print(f"    {path}: {msg}")


if __name__ == "__main__":
    main()
