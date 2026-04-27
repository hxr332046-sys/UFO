"""End-to-end test of governance subsystem against current case + a real load response.

不联网；用本地 records 中已有的 phase2 establish 响应作为 scout 数据源。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, 'system')
from governance import (
    CaseValidator, IndustryMatcher, OptionDict, OptionsScout
)


def main():
    # 1. 加载现有 case
    case_path = Path("docs/case_兴裕为.json")
    with open(case_path, "r", encoding="utf-8") as f:
        case = json.load(f)
    print(f"=== Loaded case: {case.get('case_id')} ===")
    print(f"  company: {case.get('company_name_full')}")
    print(f"  ent_type: {case.get('entType_default')}")
    print(f"  industry_code: {case.get('phase1_industry_code')}")
    print(f"  industry_text: {case.get('phase1_industry_special')}")
    print()

    # 2. Scout 扫一个真实 load response（用现成 records）
    records_path = Path("dashboard/data/records/phase2_establish_latest.json")
    od = OptionDict.load()
    if records_path.exists():
        with open(records_path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        print(f"=== Scout: scanning {records_path.name} ===")
        scout = OptionsScout(od, log=True)
        # 提取每步 raw_response 用 scout
        history = rec.get("steps") or rec.get("history") or []
        for s in history:
            comp = s.get("name", "")
            resp = s.get("raw_response") or s.get("response") or {}
            if not isinstance(resp, dict):
                continue
            # 从 step name 抽组件名（如 "[14] establish/BasicInfo/loadBusinessDataInfo"）
            comp_name = "Unknown"
            if "BasicInfo" in comp: comp_name = "BasicInfo"
            elif "MemberPost" in comp: comp_name = "MemberPost"
            elif "MemberInfo" in comp: comp_name = "MemberInfo"
            elif "MemberPool" in comp: comp_name = "MemberPool"
            elif "ComplementInfo" in comp: comp_name = "ComplementInfo"
            elif "TaxInvoice" in comp: comp_name = "TaxInvoice"
            elif "SlUploadMaterial" in comp: comp_name = "SlUploadMaterial"
            elif "BusinessLicenceWay" in comp: comp_name = "BusinessLicenceWay"
            elif "YbbSelect" in comp: comp_name = "YbbSelect"
            else: continue
            scout.ingest_load_response(component=comp_name, load_resp=resp)
        print(f"\n=== Scout report ===")
        rep = scout.report()
        print(f"  total findings: {rep['total_findings']}")
        print(f"  components: {rep['components_seen']}")
        # 持久化
        out = scout.persist()
        print(f"  persisted to: {out}")
    else:
        print("(no records file, skip scout step)")
    print()

    # 3. CaseValidator 跑质检
    print("=== CaseValidator ===")
    od2 = OptionDict.load()  # 重新加载（含 scout 结果）
    matcher = IndustryMatcher.load()
    v = CaseValidator(option_dict=od2, industry_matcher=matcher)
    report = v.validate(case)
    print(f"  case_id: {report.case_id}")
    print(f"  checked_fields: {report.checked_fields}")
    print(f"  fail count: {len(report.fails)}")
    print(f"  ambiguous count: {len(report.ambiguous)}")
    print(f"  warn count: {len(report.warns)}")
    print(f"  is_pass: {report.is_pass()}")
    print()
    for it in report.issues:
        print(f"  [{it.level.value:9s}] {it.field_path:35s} = {it.case_value!r}")
        print(f"             {it.message}")
        if it.candidates:
            print(f"             候选: {it.candidates[:3]}")
    # 写报告
    rep_path = Path("dashboard/data/records/_validation_report_latest.json")
    v.write_report(report, rep_path)
    print(f"\n  report written: {rep_path}")


if __name__ == "__main__":
    main()
