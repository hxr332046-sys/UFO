#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Automatic survey for name-check parameter combinations.

Purpose:
- Continue reverse-engineering survey after login is available.
- Batch call bannedLexiconCalibration + nameCheckRepeat.
- Persist outcomes into query_cases for later analysis.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from typing import Any, Dict, List

from dict_v2_store import connect as db_connect, insert_query_case
from icpsp_api_client import ICPSPClient
from namecheck_query_packet import _explain_banned, _explain_repeat


def _pick_organize(con, ent_type: str) -> str:
    row = con.execute(
        """
SELECT name FROM dict_items
WHERE category='organize' AND ent_type=? AND name IS NOT NULL AND name<>''
ORDER BY id LIMIT 1
""",
        [ent_type],
    ).fetchone()
    if row and row["name"]:
        return str(row["name"])
    return "有限公司"


def _leaf_industries(con, ent_type: str, limit: int) -> List[Dict[str, str]]:
    rows = con.execute(
        """
SELECT code, name, raw_json
FROM dict_items
WHERE category='industry' AND ent_type=? AND code IS NOT NULL AND code<>''
ORDER BY code
""",
        [ent_type],
    ).fetchall()
    out: List[Dict[str, str]] = []
    for r in rows:
        raw = {}
        try:
            raw = json.loads(r["raw_json"] or "{}")
        except Exception:
            raw = {}
        if bool(raw.get("minKindSign")):
            out.append({"code": str(r["code"]), "name": str(r["name"] or "")})
    random.seed(42)
    random.shuffle(out)
    return out[: max(1, limit)]


def _mk_name(idx: int, organize: str) -> str:
    # Use Chinese-only core to avoid banned tip for digits/non-standard chars.
    syllables = ["辰", "衡", "启", "远", "诺", "川", "禾", "景", "瑞", "拓", "诚", "泽"]
    a = syllables[(idx * 3) % len(syllables)]
    b = syllables[(idx * 5 + 1) % len(syllables)]
    c = syllables[(idx * 7 + 2) % len(syllables)]
    core = f"{a}{b}{c}企研"
    return "广西" + core + organize


def _mk_indspec(industry_name: str, mode: str) -> str:
    n = (industry_name or "").strip()
    if mode == "industry":
        # Keep a short phrase for sensitivity tests.
        return n[:8] if n else "软件"
    if mode == "software":
        return "软件"
    if mode == "farming":
        return "种植"
    return "科技"


def run_batch(ent_type: str, dist_code: str, limit: int, indspec_mode: str) -> Dict[str, Any]:
    con = db_connect()
    organize = _pick_organize(con, ent_type)
    leaves = _leaf_industries(con, ent_type, limit)
    c = ICPSPClient()

    stop_count = 0
    ok_count = 0
    samples: List[Dict[str, Any]] = []

    for i, ind in enumerate(leaves, start=1):
        name = _mk_name(i, organize)
        name_mark = name.replace("广西", "").replace(organize, "")[:6]
        ind_spec = _mk_indspec(ind.get("name", ""), indspec_mode)

        banned = c.get_json("/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration", {"nameMark": name_mark})
        repeat_body = {
            "condition": "1",
            "busiId": None,
            "busiType": "01",
            "entType": ent_type,
            "name": name,
            "namePre": "广西",
            "nameMark": name_mark,
            "distCode": dist_code,
            "areaCode": dist_code,
            "organize": organize,
            "industry": ind["code"],
            "indSpec": ind_spec,
            "hasParent": None,
            "jtParentEntName": "",
        }
        repeat = c.post_json("/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat", repeat_body)
        out = {
            "ok": True,
            "input": {
                "name": name,
                "distCode": dist_code,
                "entType": ent_type,
                "organize": organize,
                "industry": ind["code"],
                "indSpec": ind_spec,
                "namePre": "广西",
                "nameMark": name_mark,
            },
            "bannedLexiconCalibration": {
                "code": (banned.get("code") if isinstance(banned, dict) else None),
                "explain": _explain_banned(banned if isinstance(banned, dict) else {}),
            },
            "nameCheckRepeat": {
                "code": (repeat.get("code") if isinstance(repeat, dict) else None),
                "explain": _explain_repeat(repeat if isinstance(repeat, dict) else {}),
            },
        }
        stop = bool(out["nameCheckRepeat"]["explain"].get("stop")) or (out["bannedLexiconCalibration"]["explain"].get("success") is False)
        out["overall"] = {"ok": not stop, "stop": stop}
        if stop:
            stop_count += 1
        else:
            ok_count += 1

        insert_query_case(
            con,
            name=name,
            dist_code=dist_code,
            ent_type=ent_type,
            organize=organize,
            industry=ind["code"],
            ind_spec=ind_spec,
            input_obj=out["input"],
            result_obj=out,
        )
        if len(samples) < 8:
            samples.append(
                {
                    "name": name,
                    "industry": ind["code"],
                    "industry_name": ind["name"],
                    "indSpec": ind_spec,
                    "overall": out["overall"],
                    "banned_tip": out["bannedLexiconCalibration"]["explain"].get("tipStr"),
                    "repeat_top_remark": out["nameCheckRepeat"]["explain"].get("top_remark"),
                }
            )

    con.commit()
    return {
        "entType": ent_type,
        "distCode": dist_code,
        "organize": organize,
        "indspec_mode": indspec_mode,
        "total": len(leaves),
        "ok": ok_count,
        "stop": stop_count,
        "samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entType", default="1100")
    ap.add_argument("--distCode", default="450000")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--indSpecMode", default="industry", choices=["industry", "software", "farming", "tech"])
    args = ap.parse_args()
    result = run_batch(args.entType, args.distCode, args.limit, args.indSpecMode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
