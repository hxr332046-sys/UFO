"""
对比 driver step 5 body 与 mitm 备份里**所有** operationBusinessDataInfo 的请求体，
重点观察结构字段（非数据值）是否有差异；并筛选出可能的 "首次保存" 样本（checkState==1）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

from phase1_protocol_driver import DriverContext, _build_nc_op_body, API_NC_OP  # noqa: E402

case = json.loads((ROOT / "docs/case_广西容县李陈梦.json").read_text(encoding="utf-8"))
c = DriverContext.from_case(case)
driver_body = _build_nc_op_body(c, check_state=1, name_check_dto=None)

mitm = ROOT / "dashboard/data/records/mitm_ufo_flows_backup_20260421_231343.jsonl"
samples: List[Dict[str, Any]] = []
with mitm.open("r", encoding="utf-8", errors="replace") as f:
    for ln, line in enumerate(f, 1):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        url = str(rec.get("url") or "")
        if API_NC_OP not in url:
            continue
        if rec.get("method") != "POST":
            continue
        req_body = rec.get("req_body") or ""
        if not req_body:
            continue
        try:
            body = json.loads(req_body)
        except Exception:
            continue
        status = rec.get("status_code")
        samples.append({"line": ln, "status": status, "body": body})

print(f"找到 {len(samples)} 条 operationBusinessDataInfo 样本")
print()

# 只看"首次保存"候选：body 里没有 nameCheckDTO 或 nameCheckDTO 为空
first_saves = [s for s in samples if not s["body"].get("nameCheckDTO")]
second_saves = [s for s in samples if s["body"].get("nameCheckDTO")]
print(f"  首次保存（无 nameCheckDTO）: {len(first_saves)}")
print(f"  二次保存（含 nameCheckDTO）: {len(second_saves)}")
print()

d_keys = set(driver_body.keys())
print(f"driver body keys: {len(d_keys)} 个")
print()

# 扫描首次保存样本，看是否有字段结构差异
any_struct_diff = False
for i, s in enumerate(first_saves[:6], 1):
    sk = set(s["body"].keys())
    only_d = d_keys - sk
    only_s = sk - d_keys
    if only_d or only_s:
        any_struct_diff = True
        print(f"[{i}] L{s['line']} status={s['status']}  结构差异!")
        print(f"     only_in_driver : {sorted(only_d)}")
        print(f"     only_in_sample : {sorted(only_s)}")
    else:
        # 结构一致，列出值差异的 top 字段（取 5 个）
        diff_vals = {k: (driver_body[k], s["body"][k]) for k in d_keys if driver_body.get(k) != s["body"].get(k)}
        diff_keys_only = [k for k in diff_vals if k not in ("signInfo", "name", "nameMark", "industry",
                                                             "industryName", "industrySpecial", "organize")]
        print(f"[{i}] L{s['line']} status={s['status']}  结构一致"
              f"  value_diff_count={len(diff_vals)}  非预期差异字段={diff_keys_only}")

if not any_struct_diff:
    print("\n>>> 所有首次保存样本与 driver 结构完全一致 <<<")

# 拿第 1 条首次保存样本，导出完整 body 作参照
if first_saves:
    out = ROOT / "dashboard/data/records/_offline_sample_nc_op_first_save.json"
    out.write_text(json.dumps({
        "line": first_saves[0]["line"],
        "status": first_saves[0]["status"],
        "body": first_saves[0]["body"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved first_save sample: {out}")

# 对 second_saves 同样做一次
print()
for i, s in enumerate(second_saves[:3], 1):
    sk = set(s["body"].keys())
    only_s = sk - d_keys
    print(f"[second {i}] L{s['line']} status={s['status']}  仅样本含: {sorted(only_s)}")
