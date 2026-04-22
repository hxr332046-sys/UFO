"""多案件 E2E 测试：不同公司名/地区/企业类型，验证第一阶段通用性。"""
from __future__ import annotations

import json
import time
import sys
import requests

API = "http://127.0.0.1:8800/api/phase1/register"

PERSON = {
    "name": "黄永裕",
    "mobile": "18977514335",
    "id_no": "450921198812051251",
    "email": "344979990@qq.com",
}

CASES = [
    {
        "label": "A: 容县 · 4540 个独 · 换名",
        "case": {
            "case_id": "test_a_rongxian_4540",
            "entType_default": "4540",
            "busiType_default": "02_4",
            "name_mark": "永裕科技",
            "phase1_check_name": "永裕科技（广西容县）信息技术服务中心（个人独资）",
            "phase1_name_pre": "广西容县",
            "phase1_industry_special": "信息技术",
            "phase1_industry_code": "6540",
            "phase1_industry_name": "信息技术咨询服务",
            "phase1_main_business_desc": "信息技术咨询服务",
            "phase1_organize": "中心（个人独资）",
            "phase1_dist_codes": ["450000", "450900", "450921"],
            "phase1_protocol_busi_type": "01",
            "person": PERSON,
        },
    },
    {
        "label": "B: 南宁青秀区 · 1100 有限公司",
        "case": {
            "case_id": "test_b_nanning_1100",
            "entType_default": "1100",
            "busiType_default": "02_4",
            "name_mark": "永裕信息",
            "phase1_check_name": "广西永裕信息科技有限公司",
            "phase1_name_pre": "广西",
            "phase1_industry_special": "软件开发",
            "phase1_industry_code": "6513",
            "phase1_industry_name": "应用软件开发",
            "phase1_main_business_desc": "软件开发",
            "phase1_organize": "有限公司",
            "phase1_dist_codes": ["450000", "450100", "450103"],
            "phase1_protocol_busi_type": "01",
            "person": PERSON,
        },
    },
    {
        "label": "C: 桂林七星区 · 4540 个独 · 电商",
        "case": {
            "case_id": "test_c_guilin_4540",
            "entType_default": "4540",
            "busiType_default": "02_4",
            "name_mark": "裕鑫电商",
            "phase1_check_name": "裕鑫电商（桂林市七星区）电子商务经营部（个人独资）",
            "phase1_name_pre": "桂林市七星区",
            "phase1_industry_special": "销售",
            "phase1_industry_code": "5192",
            "phase1_industry_name": "互联网零售",
            "phase1_main_business_desc": "互联网零售",
            "phase1_organize": "经营部（个人独资）",
            "phase1_dist_codes": ["450000", "450300", "450305"],
            "phase1_protocol_busi_type": "01",
            "person": PERSON,
        },
    },
]


def run_one(label: str, case_data: dict) -> dict:
    print("\n" + "=" * 70)
    print(label)
    print("  name: " + case_data.get("phase1_check_name", "?"))
    print("  entType: " + case_data.get("entType_default", "?"))
    print("  dist: " + " > ".join(case_data.get("phase1_dist_codes", [])))
    print("=" * 70)

    t0 = time.time()
    try:
        r = requests.post(API, json={"case": case_data}, timeout=120)
    except Exception as e:
        print("  HTTP ERROR: " + repr(e))
        return {"label": label, "success": False, "error": repr(e)}

    d = r.json()
    dur = int((time.time() - t0) * 1000)

    print("  HTTP " + str(r.status_code))
    print("  success:    " + str(d.get("success")))
    print("  busiId:     " + str(d.get("busiId")))
    print("  checkState: " + str(d.get("checkState")))
    print("  hit_count:  " + str(d.get("hit_count")))
    print("  latency_ms: " + str(d.get("latency_ms")))
    print("  reason:     " + str(d.get("reason")))

    for s in d.get("steps") or []:
        ok = "OK" if s.get("ok") else "!!"
        sn = s.get("name") or "?"
        sc = s.get("code") or ""
        sm = (s.get("msg") or "")[:50]
        print("    [" + ok + "] " + sn + "  code=" + sc + "  " + sm)

    return {
        "label": label,
        "success": d.get("success"),
        "busiId": d.get("busiId"),
        "checkState": d.get("checkState"),
        "hit_count": d.get("hit_count"),
        "latency_ms": d.get("latency_ms") or dur,
        "reason": d.get("reason"),
        "steps_ok": all(s.get("ok") for s in (d.get("steps") or [])),
    }


def main():
    results = []
    for i, c in enumerate(CASES):
        if i > 0:
            wait = 15
            print("\n--- 冷却 " + str(wait) + " 秒（避免 D0029）---")
            time.sleep(wait)
        results.append(run_one(c["label"], c["case"]))

    print("\n\n" + "=" * 70)
    print("  汇总")
    print("=" * 70)
    for r in results:
        ok_str = "PASS" if r.get("success") and r.get("steps_ok") else "FAIL"
        bid = r.get("busiId") or "N/A"
        lt = r.get("latency_ms") or 0
        reason = r.get("reason") or ""
        print("  [" + ok_str + "]  " + r["label"])
        print("        busiId=" + str(bid) + "  latency=" + str(lt) + "ms  " + reason)
    print()

    all_pass = all(r.get("success") and r.get("steps_ok") for r in results)
    if all_pass:
        print("  >>> 全部通过！第一阶段 API 通用性验证成功 <<<")
    else:
        print("  >>> 有失败，需排查 <<<")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
