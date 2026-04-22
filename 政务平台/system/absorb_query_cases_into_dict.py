#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 query_cases 普查成果聚合后写入 dict_items（survey_* 分类），供面板检索。

只操作 category LIKE 'survey_%' 的旧行（可重复执行覆盖同前缀批次逻辑）。
不删除 region / industry / organize 等基础字典项。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from dict_v2_store import begin_run, connect, end_run, insert_dict_item

_SURVEY_PREFIX = "survey_"


def _strip_html(s: str) -> str:
    s = s or ""
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def _kw_parts(s: str) -> List[str]:
    out: List[str] = []
    for part in re.split(r"[、,，\s]+", s or ""):
        p = part.strip()
        if p:
            out.append(p)
    return out


def _short(s: str, n: int = 220) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _code_digest(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:20]


def absorb_from_query_cases(
    *,
    max_tip_rows: int = 400,
    max_remark_rows: int = 200,
    max_keyword_rows: int = 120,
    max_cohort_rows: int = 300,
    max_industry_rows: int = 150,
    min_tip_count: int = 2,
    min_cohort_total: int = 8,
) -> Dict[str, Any]:
    con = connect()
    run_tag = f"absorb_query_cases_{time.strftime('%Y%m%d_%H%M%S')}"
    run_id = begin_run(con, run_tag=run_tag, source="query_cases", note="survey digest -> dict_items")

    con.execute("DELETE FROM dict_items WHERE category LIKE ?", (_SURVEY_PREFIX + "%",))
    con.commit()

    banned_tips: Counter = Counter()
    repeat_remarks: Counter = Counter()
    keywords: Counter = Counter()
    cohort: Dict[Tuple[str, str, str], Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "stop": 0, "banned_fail": 0, "repeat_stop": 0}
    )
    industry_stop: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "stop": 0}
    )

    tip_examples: Dict[str, List[int]] = defaultdict(list)
    remark_examples: Dict[str, List[int]] = defaultdict(list)

    rows = con.execute(
        """
SELECT id, ent_type, dist_code, industry, ind_spec, stop_flag, overall_ok,
       banned_tip, repeat_top_remark, result_json
FROM query_cases
"""
    ).fetchall()

    for r in rows:
        rid = int(r["id"])
        ent_type = str(r["ent_type"] or "").strip()
        ind = str(r["industry"] or "").strip()
        stop = int(r["stop_flag"] or 0)
        res: Dict[str, Any] = {}
        try:
            res = json.loads(r["result_json"] or "{}")
        except Exception:
            res = {}
        meta = res.get("survey_meta") if isinstance(res.get("survey_meta"), dict) else {}
        mark = str(meta.get("nameMark") or "").strip()
        mode = str(meta.get("indspec_mode") or "").strip()

        bt = _strip_html(str(r["banned_tip"] or ""))
        if bt:
            banned_tips[bt] += 1
            if len(tip_examples[bt]) < 12:
                tip_examples[bt].append(rid)

        rr = _strip_html(str(r["repeat_top_remark"] or ""))
        if rr:
            repeat_remarks[rr] += 1
            if len(remark_examples[rr]) < 12:
                remark_examples[rr].append(rid)

        b = ((res.get("bannedLexiconCalibration") or {}).get("explain") or {}) if isinstance(
            res.get("bannedLexiconCalibration"), dict
        ) else {}
        kw = _strip_html(str(b.get("tipKeyWords") or ""))
        for p in _kw_parts(kw):
            keywords[p] += 1

        rep = ((res.get("nameCheckRepeat") or {}).get("explain") or {}) if isinstance(res.get("nameCheckRepeat"), dict) else {}
        if ent_type and mark and mode:
            c = cohort[(ent_type, mark, mode)]
            c["total"] += 1
            c["stop"] += stop
            if b.get("success") is False:
                c["banned_fail"] += 1
            if bool(rep.get("stop")):
                c["repeat_stop"] += 1

        if ent_type and ind:
            s = industry_stop[(ent_type, ind)]
            s["total"] += 1
            s["stop"] += stop

    inserted = {"banned_tip": 0, "repeat_remark": 0, "keyword": 0, "cohort": 0, "industry": 0}

    for tip, cnt in banned_tips.most_common():
        if cnt < min_tip_count:
            break
        if inserted["banned_tip"] >= max_tip_rows:
            break
        code = "tip_" + _code_digest(tip)
        insert_dict_item(
            con,
            category=_SURVEY_PREFIX + "banned_tip",
            code=code,
            name=_short(tip, 240),
            ent_type=None,
            tags=["普查吸收", "官方禁限用", "tipStr"],
            tip_ok=f"样本中出现 {cnt} 次（来自 query_cases）",
            tip_error=None,
            recommendation="查询面板名称核查或知识库检索时可对照此官方提示。",
            source_api="/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
            source_file="query_cases",
            raw_json={"count": cnt, "case_ids": tip_examples.get(tip, [])[:12], "text": tip},
            run_id=run_id,
        )
        inserted["banned_tip"] += 1

    for rm, cnt in repeat_remarks.most_common():
        if cnt < min_tip_count:
            break
        if inserted["repeat_remark"] >= max_remark_rows:
            break
        code = "rm_" + _code_digest(rm)
        insert_dict_item(
            con,
            category=_SURVEY_PREFIX + "repeat_remark",
            code=code,
            name=_short(rm, 240),
            ent_type=None,
            tags=["普查吸收", "官方查重", "remark"],
            tip_ok=f"样本中出现 {cnt} 次",
            recommendation="与 checkState / langStateCode 一起看；以 result_json 为准。",
            source_api="/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat",
            source_file="query_cases",
            raw_json={"count": cnt, "case_ids": remark_examples.get(rm, [])[:12], "text": rm},
            run_id=run_id,
        )
        inserted["repeat_remark"] += 1

    for kw, cnt in keywords.most_common():
        if inserted["keyword"] >= max_keyword_rows:
            break
        code = "kw_" + _code_digest(kw)
        insert_dict_item(
            con,
            category=_SURVEY_PREFIX + "keyword",
            code=code,
            name=kw,
            ent_type=None,
            tags=["普查吸收", "tipKeyWords"],
            tip_ok=f"出现 {cnt} 次",
            recommendation="高频关键词多来自禁限用接口；需结合完整 tipStr。",
            source_api="/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
            source_file="query_cases",
            raw_json={"keyword": kw, "count": cnt},
            run_id=run_id,
        )
        inserted["keyword"] += 1

    cohort_ranked = sorted(
        ((k, v) for k, v in cohort.items() if v["total"] >= min_cohort_total),
        key=lambda x: -x[1]["total"],
    )
    for (ent, mark, mode), st in cohort_ranked[:max_cohort_rows]:
        code = _code_digest(f"{ent}|{mark}|{mode}")[:24]
        name = f"{ent} | nameMark={mark} | indspec={mode}"
        insert_dict_item(
            con,
            category=_SURVEY_PREFIX + "cohort_mark_mode",
            code=code,
            name=name,
            ent_type=ent,
            tags=["普查吸收", "对照组", "nameMark", "indspec_mode"],
            tip_ok=f"total={st['total']} ok≈{st['total']-st['stop']}",
            tip_error=f"stop={st['stop']} banned_fail={st['banned_fail']} repeat_stop={st['repeat_stop']}",
            recommendation="分组为样本统计，非官方规则；用于定位哪类组合更易阻断。",
            source_file="query_cases",
            raw_json={"entType": ent, "nameMark": mark, "indspec_mode": mode, **st},
            run_id=run_id,
        )
        inserted["cohort"] += 1

    ind_ranked = sorted(
        ((k, v) for k, v in industry_stop.items() if v["total"] >= min_cohort_total),
        key=lambda x: (-x[1]["stop"], -x[1]["total"]),
    )
    for (ent, ind), st in ind_ranked[:max_industry_rows]:
        if st["total"] <= 0:
            continue
        rate = st["stop"] / st["total"]
        code = _code_digest(f"{ent}|{ind}")[:24]
        insert_dict_item(
            con,
            category=_SURVEY_PREFIX + "industry_stop",
            code=code,
            name=f"{ent} / industry={ind}",
            ent_type=ent,
            tags=["普查吸收", "行业码", "stop率"],
            tip_ok=f"样本 total={st['total']}",
            tip_error=f"stop={st['stop']} 占比={rate:.3f}",
            recommendation="高 stop 占比行业码可优先人工复核；仍以单条 case 的 result_json 为准。",
            source_file="query_cases",
            raw_json={"entType": ent, "industry": ind, **st, "stop_rate": round(rate, 5)},
            run_id=run_id,
        )
        inserted["industry"] += 1

    con.commit()
    end_run(con, run_id)

    return {
        "ok": True,
        "run_id": run_id,
        "run_tag": run_tag,
        "source_rows": len(rows),
        "inserted": inserted,
        "unique_banned_tip": len(banned_tips),
        "unique_repeat_remark": len(repeat_remarks),
        "unique_keyword": len(keywords),
        "cohort_keys": len(cohort),
    }


def main() -> None:
    out = absorb_from_query_cases()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
