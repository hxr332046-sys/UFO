"""验证 CaseValidator 在故意写错的 case 上的拒绝能力。"""
import sys
import json
import copy
from pathlib import Path

sys.path.insert(0, 'system')
from governance import CaseValidator, OptionDict, IndustryMatcher


SCENARIOS = [
    # (description, mutator)
    ("场景 A: entType 写错为 9999",
     lambda c: c.update(entType_default="9999") or c),
    ("场景 B: 证件类型写为不存在的 99",
     lambda c: (c.setdefault("person", {}).update(cerType="99"), c)[-1]),
    ("场景 C: 政治面貌写为 '99'",
     lambda c: (c.setdefault("person", {}).update(politicsVisage="99"), c)[-1]),
    ("场景 D: 性别写为 '3'",
     lambda c: (c.setdefault("person", {}).update(sex="3"), c)[-1]),
    ("场景 E: 行政区域写为不存在的 999999",
     lambda c: c.update(domDistCode="999999") or c),
    ("场景 F: 行业代码写为不存在的 9999",
     lambda c: c.update(phase1_industry_code="9999") or c),
    ("场景 G: 货币写为不存在的 ZZZ",
     lambda c: c.update(currencyCode="ZZZ") or c),
    ("场景 H: 营业执照领取方式写为 5（合法只有 1/2）",
     lambda c: c.update(businessLicenceWay="5") or c),
    ("场景 I: 政治面貌中文 '中共党员' 应反向命中 code=01",
     lambda c: (c.setdefault("person", {}).update(politicsVisage="中共党员"), c)[-1]),
    ("场景 J: 国籍写中文 '美国' 应反向命中 code=840",
     lambda c: (c.setdefault("person", {}).update(country="美国"), c)[-1]),
]


def main():
    base_case = json.load(open("docs/case_兴裕为.json", "r", encoding="utf-8"))
    od = OptionDict.load()
    im = IndustryMatcher.load()
    v = CaseValidator(option_dict=od, industry_matcher=im)

    print("=" * 70)
    for desc, mutator in SCENARIOS:
        case = copy.deepcopy(base_case)
        case = mutator(case)
        rep = v.validate(case)

        print(f"\n{desc}")
        print(f"  fail={len(rep.fails)} ambiguous={len(rep.ambiguous)} warn={len(rep.warns)}")
        for it in rep.issues:
            tag = {"fail": "❌", "ambiguous": "❓", "warn": "⚠"}[it.level.value]
            print(f"  {tag} {it.field_path}={it.case_value!r}: {it.message[:80]}")
            for c in (it.candidates or [])[:2]:
                print(f"      → {c.get('code','?')} {c.get('name','?')}")


if __name__ == "__main__":
    main()
