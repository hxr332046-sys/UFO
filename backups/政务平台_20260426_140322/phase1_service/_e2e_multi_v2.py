"""多案件 E2E 测试 v2：使用已验证安全的名字，测试不同地区/企业类型。"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system"))

from phase1_protocol_driver import (
    DriverContext,
    step_check_establish_name,
    step_load_current_location,
    step_namecheck_load,
    step_banned_lexicon,
    step_nc_op_first_save,
    step_namecheck_repeat,
    step_nc_op_second_save,
)
from icpsp_api_client import ICPSPClient

CASES = [
    {
        "label": "G: 李陈梦-南宁青秀-4540 (换地区)",
        "case": {
            "entType_default": "4540",
            "name_mark": "李陈梦",
            "phase1_check_name": "李陈梦（南宁市青秀区）软件开发中心（个人独资）",
            "phase1_name_pre": "南宁市青秀区",
            "phase1_industry_special": "软件开发",
            "phase1_industry_code": "6513",
            "phase1_industry_name": "应用软件开发",
            "phase1_main_business_desc": "软件开发",
            "phase1_organize": "中心（个人独资）",
            "phase1_dist_codes": ["450000", "450100", "450103"],
            "phase1_protocol_busi_type": "01",
        },
    },
    {
        "label": "H: 裕鑫-梧州万秀-1100 (换地区+有限)",
        "case": {
            "entType_default": "1100",
            "name_mark": "裕鑫",
            "phase1_check_name": "广西裕鑫信息技术有限公司",
            "phase1_name_pre": "广西",
            "phase1_industry_special": "信息技术",
            "phase1_industry_code": "6540",
            "phase1_industry_name": "信息技术咨询服务",
            "phase1_main_business_desc": "信息技术咨询服务",
            "phase1_organize": "有限公司",
            "phase1_dist_codes": ["450000", "450400", "450403"],
            "phase1_protocol_busi_type": "01",
        },
    },
    {
        "label": "I: 李陈梦-桂林七星-1100 (换地区+类型)",
        "case": {
            "entType_default": "1100",
            "name_mark": "李陈梦",
            "phase1_check_name": "桂林李陈梦软件开发有限公司",
            "phase1_name_pre": "桂林",
            "phase1_industry_special": "软件开发",
            "phase1_industry_code": "6513",
            "phase1_industry_name": "应用软件开发",
            "phase1_main_business_desc": "软件开发",
            "phase1_organize": "有限公司",
            "phase1_dist_codes": ["450000", "450300", "450305"],
            "phase1_protocol_busi_type": "01",
        },
    },
]


ALL_STEPS = [
    ("step1", step_check_establish_name),
    ("step2", step_load_current_location),
    ("step3", step_namecheck_load),
    ("step4", step_banned_lexicon),
]


def run_case(label, case_data):
    print("\n" + "=" * 70)
    print(label)
    c = DriverContext.from_case(case_data)
    client = ICPSPClient()
    print(f"  full_name: {c.full_name}")
    print(f"  ent_type:  {c.ent_type}  dist_code: {c.dist_code}")

    for lb, fn in ALL_STEPS:
        sr, _ = fn(client, c)
        if not sr.ok:
            print(f"  {lb} FAIL: {sr.reason}")
            return None, None
        time.sleep(0.9)
    print("  steps 1-4: all OK")

    # step 5
    sr5, resp5 = step_nc_op_first_save(client, c)
    d5 = (resp5 or {}).get("data") or {}
    m5 = d5.get("msg") or ""
    print(f"  step5: resultType={sr5.result_type}  msg={m5[:80]}")
    if not sr5.ok:
        return None, None
    time.sleep(0.9)

    # step 6
    sr6, _ = step_namecheck_repeat(client, c)
    print(f"  step6: hit_count={sr6.extracted.get('hit_count')}  checkState={sr6.extracted.get('checkState_reported')}")
    if not sr6.ok:
        return None, None
    time.sleep(0.9)

    # step 7
    sr7, resp7 = step_nc_op_second_save(client, c)
    d7 = (resp7 or {}).get("data") or {}
    m7 = d7.get("msg") or ""
    print(f"  step7: resultType={sr7.result_type}  msg={m7[:80]}")
    print(f"  busiId: {c.busi_id!r}")

    return c.busi_id, sr7.extracted


results = []
for i, item in enumerate(CASES):
    if i > 0:
        print("\n--- 冷却 15s ---")
        time.sleep(15)
    bid, ext = run_case(item["label"], item["case"])
    results.append((item["label"], bid))

print("\n\n" + "=" * 70)
print("  汇总")
print("=" * 70)
for label, bid in results:
    tag = "PASS" if bid else "FAIL"
    print(f"  [{tag}] {label}")
    print(f"         busiId={bid or 'N/A'}")

all_pass = all(b for _, b in results)
if all_pass:
    print("\n  >>> 全部通过！第一阶段通用性验证成功 <<<")
else:
    fails = [(l, b) for l, b in results if not b]
    print(f"\n  >>> {len(fails)}/{len(results)} 失败 <<<")
