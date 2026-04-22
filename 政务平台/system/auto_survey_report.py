#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build a human-readable report from query_cases (V2.1 samples).

Outputs:
- dashboard/data/records/auto_survey_report_latest.json
- dashboard/data/records/auto_survey_report_latest.md

This is evidence-first:
- Official signals: banned tipStr, restType/restLevel, repeat checkState/langState/top_remark.
- Non-official suggestions are clearly labeled as heuristics.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dict_v2_store import connect


ROOT = Path("G:/UFO/政务平台")
OUT_JSON = ROOT / "dashboard" / "data" / "records" / "auto_survey_report_latest.json"
OUT_MD = ROOT / "dashboard" / "data" / "records" / "auto_survey_report_latest.md"


def _jload(s: str) -> Any:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def _strip_html(s: str) -> str:
    s = s or ""
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def generate_report(limit: int = 50000) -> None:
    con = connect()
    limit = max(1, int(limit))
    rows = con.execute(
        """
SELECT id, queried_at, name, dist_code, ent_type, organize, industry, ind_spec,
       overall_ok, stop_flag, banned_success, banned_tip,
       repeat_check_state, repeat_lang_state_code, repeat_top_remark, repeat_hit_count,
       input_json, result_json
FROM query_cases
ORDER BY id DESC
LIMIT ?
""",
        (limit,),
    ).fetchall()

    by_ent: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        d = dict(r)
        d["input"] = _jload(d.get("input_json") or "")
        d["result"] = _jload(d.get("result_json") or "")
        by_ent[str(d.get("ent_type") or "")].append(d)

    report: Dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cases_scanned": len(rows),
        "by_entType": {},
        "notes": [
            "All 'official' reasons are from API responses (banned tipStr / repeat fields).",
            "Any recommendation is labeled as heuristic, not an official block.",
        ],
    }

    md: List[str] = []
    md.append(f"# 自动普查报告（latest）\n\n生成时间：{report['generated_at']}\n\n样本数：{len(rows)}\n")

    for ent_type, arr in sorted(by_ent.items()):
        if not ent_type:
            continue
        total = len(arr)
        ok = sum(1 for x in arr if int(x.get("overall_ok") or 0) == 1)
        stop = sum(1 for x in arr if int(x.get("stop_flag") or 0) == 1)

        banned_tips = Counter()
        banned_keywords = Counter()
        rest_types = Counter()
        check_states = Counter()
        lang_states = Counter()
        top_remarks = Counter()
        by_mark = defaultdict(lambda: Counter())
        by_mode = defaultdict(lambda: Counter())
        by_mark_mode = defaultdict(lambda: Counter())

        examples_stop: List[Dict[str, Any]] = []
        examples_ok: List[Dict[str, Any]] = []

        for x in arr:
            res = x.get("result") if isinstance(x.get("result"), dict) else {}
            meta = res.get("survey_meta") if isinstance(res.get("survey_meta"), dict) else {}
            b = ((res.get("bannedLexiconCalibration") or {}).get("explain") or {}) if isinstance(res.get("bannedLexiconCalibration"), dict) else {}
            rep = ((res.get("nameCheckRepeat") or {}).get("explain") or {}) if isinstance(res.get("nameCheckRepeat"), dict) else {}

            tip = _strip_html(str(b.get("tipStr") or ""))
            if tip:
                banned_tips[tip] += 1
            kw = _strip_html(str(b.get("tipKeyWords") or ""))
            if kw:
                for part in re.split(r"[、,，\\s]+", kw):
                    part = part.strip()
                    if part:
                        banned_keywords[part] += 1
            rt = str(b.get("restTypeName") or "")
            if rt:
                rest_types[rt] += 1

            cs = str(rep.get("checkState") or "")
            if cs:
                check_states[cs] += 1
            ls = str(rep.get("langStateCode") or "")
            if ls:
                lang_states[ls] += 1
            tr = _strip_html(str(rep.get("top_remark") or ""))
            if tr:
                top_remarks[tr] += 1

            # cohort stats (non-official grouping): nameMark / indspec_mode
            mark = str(meta.get("nameMark") or (x.get("input") or {}).get("nameMark") or "").strip()
            mode = str(meta.get("indspec_mode") or "").strip()
            stop_flag = int(x.get("stop_flag") or 0)
            if mark:
                by_mark[mark]["total"] += 1
                by_mark[mark]["stop"] += stop_flag
                if b.get("success") is False:
                    by_mark[mark]["banned_stop"] += 1
                if bool(rep.get("stop")):
                    by_mark[mark]["repeat_stop"] += 1
            if mode:
                by_mode[mode]["total"] += 1
                by_mode[mode]["stop"] += stop_flag
            if mark and mode:
                key = f"{mark} | {mode}"
                by_mark_mode[key]["total"] += 1
                by_mark_mode[key]["stop"] += stop_flag

            ex = {
                "id": x.get("id"),
                "name": x.get("name"),
                "industry": x.get("industry"),
                "indSpec": x.get("ind_spec"),
                "organize": x.get("organize"),
                "banned_tip": tip,
                "repeat_checkState": cs,
                "repeat_langStateCode": ls,
                "repeat_top_remark": tr,
                "repeat_hit_count": int(rep.get("hit_count") or 0),
                "overall_ok": bool(int(x.get("overall_ok") or 0)),
                "stop": bool(int(x.get("stop_flag") or 0)),
            }
            if ex["stop"] and len(examples_stop) < 8:
                examples_stop.append(ex)
            if (not ex["stop"]) and len(examples_ok) < 8:
                examples_ok.append(ex)

        heuristics: List[str] = []
        if banned_keywords:
            heuristics.append(
                "Heuristic: prioritize replacing/avoiding high-frequency banned keywords in nameMark/name. "
                + "Top keywords: "
                + ", ".join([f"{k}({v})" for k, v in banned_keywords.most_common(6)])
            )
        if check_states:
            heuristics.append(
                "Heuristic: checkState distribution suggests where stop tends to happen; see counts below."
            )

        report["by_entType"][ent_type] = {
            "total": total,
            "ok": ok,
            "stop": stop,
            "banned_top_tips": banned_tips.most_common(8),
            "banned_top_keywords": banned_keywords.most_common(12),
            "banned_rest_types": rest_types.most_common(12),
            "repeat_checkState": check_states.most_common(),
            "repeat_langStateCode": lang_states.most_common(12),
            "repeat_top_remark": top_remarks.most_common(12),
            "cohorts": {
                "by_nameMark": sorted(
                    [{"nameMark": k, **dict(v)} for k, v in by_mark.items()],
                    key=lambda x: (-int(x.get("total") or 0), str(x.get("nameMark") or "")),
                ),
                "by_indspec_mode": sorted(
                    [{"indspec_mode": k, **dict(v)} for k, v in by_mode.items()],
                    key=lambda x: (-int(x.get("total") or 0), str(x.get("indspec_mode") or "")),
                ),
                "by_nameMark_indspec_mode": sorted(
                    [{"key": k, **dict(v)} for k, v in by_mark_mode.items()],
                    key=lambda x: (-int(x.get("total") or 0), str(x.get("key") or "")),
                )[:40],
            },
            "examples_stop": examples_stop,
            "examples_ok": examples_ok,
            "heuristics": heuristics,
        }

        md.append(f"## entType={ent_type}\n\n- total: **{total}**\n- ok: **{ok}**\n- stop: **{stop}**\n")
        if banned_keywords:
            md.append("### 禁限用高频关键词（官方返回 tipKeyWords）\n")
            for k, v in banned_keywords.most_common(12):
                md.append(f"- {k}: {v}")
            md.append("")
        if banned_tips:
            md.append("### 禁限用高频提示（官方返回 tipStr）\n")
            for k, v in banned_tips.most_common(8):
                md.append(f"- ({v}) {k}")
            md.append("")
        md.append("### 查重状态分布（官方返回）\n")
        for k, v in check_states.most_common():
            md.append(f"- checkState={k}: {v}")
        md.append("")
        if by_mark:
            md.append("### 分组统计：nameMark（对照组，非官方规则）\n")
            for it in report["by_entType"][ent_type]["cohorts"]["by_nameMark"][:20]:
                md.append(
                    f"- {it['nameMark']}: total={it.get('total',0)} stop={it.get('stop',0)} banned_stop={it.get('banned_stop',0)} repeat_stop={it.get('repeat_stop',0)}"
                )
            md.append("")
        if by_mode:
            md.append("### 分组统计：indSpec 模式（对照组，非官方规则）\n")
            for it in report["by_entType"][ent_type]["cohorts"]["by_indspec_mode"][:20]:
                md.append(f"- {it['indspec_mode']}: total={it.get('total',0)} stop={it.get('stop',0)}")
            md.append("")
        if by_mark_mode:
            md.append("### 分组统计：nameMark × indSpec 模式（Top40，非官方规则）\n")
            for it in report["by_entType"][ent_type]["cohorts"]["by_nameMark_indspec_mode"][:40]:
                md.append(f"- {it['key']}: total={it.get('total',0)} stop={it.get('stop',0)}")
            md.append("")
        md.append("### 样例（stop）\n")
        for ex in examples_stop:
            md.append(f"- #{ex['id']} {ex['name']} | industry={ex['industry']} | indSpec={ex['indSpec']} | banned={ex['banned_tip'] or '-'} | remark={ex['repeat_top_remark'] or '-'}")
        md.append("")
        md.append("### 样例（ok）\n")
        for ex in examples_ok:
            md.append(f"- #{ex['id']} {ex['name']} | industry={ex['industry']} | indSpec={ex['indSpec']} | hit={ex['repeat_hit_count']}")
        md.append("")
        if heuristics:
            md.append("### 推荐（非官方规则，仅基于样本统计）\n")
            for h in heuristics:
                md.append(f"- {h}")
            md.append("")

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print("wrote", OUT_JSON)
    print("wrote", OUT_MD)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Report from query_cases (V2)")
    ap.add_argument(
        "--limit",
        type=int,
        default=50000,
        help="Max rows to scan (newest first). Default large enough for full census runs.",
    )
    args = ap.parse_args()
    generate_report(args.limit)


if __name__ == "__main__":
    main()

