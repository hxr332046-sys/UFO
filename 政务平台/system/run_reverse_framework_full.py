#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键执行逆开发框架主流程：
1) 矩阵普查（nameMark 对照组 + indSpec 模式）
2) 生成统计报告（auto_survey_report）
3) 导出可查询知识快照（JSON）
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from auto_survey_namecheck_grid import run_grid
from auto_survey_report import generate_report
from dict_v2_store import connect

ROOT = Path("G:/UFO/政务平台")
OUT_JSON = ROOT / "dashboard" / "data" / "records" / "reverse_framework_latest.json"


def _top_tips(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    c = Counter()
    for r in rows:
        tip = str(r.get("banned_tip") or "").strip()
        if tip:
            c[tip] += 1
    return [{"tip": k, "count": v} for k, v in c.most_common(20)]


def _top_repeat_remarks(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    c = Counter()
    for r in rows:
        tip = str(r.get("repeat_top_remark") or "").strip()
        if tip:
            c[tip] += 1
    return [{"remark": k, "count": v} for k, v in c.most_common(20)]


def _api_reserved_fields(con) -> List[str]:
    rows = con.execute(
        "SELECT request_template FROM api_specs WHERE path='/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat' LIMIT 1"
    ).fetchall()
    if not rows:
        return []
    try:
        req = json.loads(rows[0]["request_template"] or "{}")
    except Exception:
        req = {}
    reserved = []
    for k, v in req.items():
        if v in ("", None):
            reserved.append(str(k))
    if reserved:
        return sorted(set(reserved))
    # Fallback: these fields are present in captured/replay request body and are usually placeholders.
    return ["busiId", "hasParent", "jtParentEntName"]


def _knowledge_snapshot(limit: int = 1200) -> Dict[str, Any]:
    con = connect()
    dict_stats = {
        "dict_items_total": int(con.execute("SELECT COUNT(*) c FROM dict_items").fetchone()["c"]),
        "api_specs_total": int(con.execute("SELECT COUNT(*) c FROM api_specs").fetchone()["c"]),
        "operation_methods_total": int(con.execute("SELECT COUNT(*) c FROM operation_methods").fetchone()["c"]),
        "query_cases_total": int(con.execute("SELECT COUNT(*) c FROM query_cases").fetchone()["c"]),
    }
    rows = [
        dict(r)
        for r in con.execute(
            """
SELECT id, queried_at, name, dist_code, ent_type, organize, industry, ind_spec,
       overall_ok, stop_flag, banned_tip, repeat_check_state, repeat_top_remark
FROM query_cases
ORDER BY id DESC
LIMIT ?
""",
            [int(limit)],
        )
    ]
    stop_rows = [r for r in rows if int(r.get("stop_flag") or 0) == 1]
    ok_rows = [r for r in rows if int(r.get("overall_ok") or 0) == 1]
    ent_counter = Counter(str(r.get("ent_type") or "") for r in rows if str(r.get("ent_type") or ""))
    reserved = _api_reserved_fields(con)
    return {
        "stats": dict_stats,
        "sample_window": len(rows),
        "official_signals": {
            "top_banned_tips": _top_tips(rows),
            "top_repeat_remarks": _top_repeat_remarks(rows),
            "stop_cases": len(stop_rows),
            "ok_cases": len(ok_rows),
            "entType_distribution": [{"entType": k, "count": v} for k, v in ent_counter.most_common(20)],
        },
        "protocol_fields": {
            "nameCheckRepeat_reserved_or_placeholder_fields": reserved,
            "note": "reserved/placeholder 指 request_template 中默认空值字段，用于协议重放时按需填充。",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entType", default="1100")
    ap.add_argument("--distLimit", type=int, default=2)
    ap.add_argument("--organizeLimit", type=int, default=2)
    ap.add_argument("--industryLimit", type=int, default=12)
    ap.add_argument("--indspecModes", default="industry,软件,种植,科技")
    ap.add_argument("--namePre", default="广西")
    ap.add_argument("--nameCore", default="禾泽诺企研")
    ap.add_argument("--nameMarkList", default="禾泽诺,启诺瑞,远川衡,有米米,驰科蓝,科技")
    ap.add_argument("--sleepMs", type=int, default=80)
    ap.add_argument("--snapshotLimit", type=int, default=1200)
    args = ap.parse_args()

    modes = [x.strip() for x in str(args.indspecModes).split(",") if x.strip()]
    marks = [x.strip() for x in str(args.nameMarkList).split(",") if x.strip()]
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")

    grid_result = run_grid(
        ent_type=str(args.entType),
        dist_limit=int(args.distLimit),
        organize_limit=int(args.organizeLimit),
        industry_limit=int(args.industryLimit),
        indspec_modes=modes,
        name_mark_list=marks,
        name_pre=str(args.namePre),
        name_core=str(args.nameCore),
        sleep_ms=int(args.sleepMs),
    )

    generate_report(50000)
    snapshot = _knowledge_snapshot(limit=int(args.snapshotLimit))
    payload = {
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_args": {
            "entType": args.entType,
            "distLimit": args.distLimit,
            "organizeLimit": args.organizeLimit,
            "industryLimit": args.industryLimit,
            "indspecModes": modes,
            "namePre": args.namePre,
            "nameCore": args.nameCore,
            "nameMarkList": marks,
            "sleepMs": args.sleepMs,
        },
        "grid_result": grid_result,
        "knowledge_snapshot": snapshot,
        "artifacts": {
            "reverse_framework_latest_json": str(OUT_JSON),
            "auto_survey_report_json": str(ROOT / "dashboard" / "data" / "records" / "auto_survey_report_latest.json"),
            "auto_survey_report_md": str(ROOT / "dashboard" / "data" / "records" / "auto_survey_report_latest.md"),
        },
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(OUT_JSON))
    print(json.dumps({"total": grid_result.get("total"), "ok": grid_result.get("ok"), "stop": grid_result.get("stop")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

