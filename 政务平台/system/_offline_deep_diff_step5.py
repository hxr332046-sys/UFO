"""
深度 diff：driver 当前构造的 step5 body 与 mitm 备份里"加多名"样本（L354）做递归对比。
包含所有嵌套字段。
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
sample_body = None
with mitm.open("r", encoding="utf-8", errors="replace") as f:
    for ln, line in enumerate(f, 1):
        if ln != 354:
            continue
        rec = json.loads(line)
        req_body = rec.get("req_body")
        sample_body = json.loads(req_body)
        break

if sample_body is None:
    print("L354 not found")
    sys.exit(2)


def walk(path: str, d: Any, s: Any, out: List[Dict[str, Any]]) -> None:
    if isinstance(d, dict) and isinstance(s, dict):
        dk = set(d.keys())
        sk = set(s.keys())
        for k in sorted(dk - sk):
            out.append({"path": path + "." + k, "kind": "only_in_driver", "driver": d[k]})
        for k in sorted(sk - dk):
            out.append({"path": path + "." + k, "kind": "only_in_sample", "sample": s[k]})
        for k in sorted(dk & sk):
            walk(path + "." + k, d[k], s[k], out)
    elif isinstance(d, list) and isinstance(s, list):
        if len(d) != len(s):
            out.append({"path": path, "kind": "list_len_diff", "driver_len": len(d), "sample_len": len(s)})
        for i, (dv, sv) in enumerate(zip(d, s)):
            walk(f"{path}[{i}]", dv, sv, out)
    else:
        if d != s:
            out.append({"path": path, "kind": "value_diff", "driver": d, "sample": s})


diffs: List[Dict[str, Any]] = []
walk("", driver_body, sample_body, diffs)

print(f"=== driver vs sample(L354) 深度 diff：共 {len(diffs)} 处差异 ===\n")
for d in diffs:
    p = d["path"]
    if d["kind"] == "value_diff":
        dv = json.dumps(d["driver"], ensure_ascii=False)
        sv = json.dumps(d["sample"], ensure_ascii=False)
        print(f"  [{d['kind']}] {p}")
        print(f"     driver : {dv[:200]}")
        print(f"     sample : {sv[:200]}")
    else:
        print(f"  [{d['kind']}] {p}  detail={json.dumps({k: v for k, v in d.items() if k not in ('kind','path')}, ensure_ascii=False)[:200]}")
