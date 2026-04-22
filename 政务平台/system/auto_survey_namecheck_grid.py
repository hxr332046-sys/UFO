#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Matrix-style survey for name-check logic (evidence-first).

Goal:
- Keep official behavior as-is (no extra blocking rules).
- Systematically vary inputs to learn relationships and conflicts:
  entType / distCode / organize / industry / indSpec / nameMark
- Persist full official responses into query_cases.result_json.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from typing import Any, Dict, List, Tuple

from dict_v2_store import connect as db_connect, insert_query_case
from icpsp_api_client import ICPSPClient
from namecheck_query_packet import _explain_banned, _explain_repeat


def _pick_regions(con, limit: int) -> List[str]:
    rows = con.execute(
        "SELECT code FROM dict_items WHERE category='region' AND code IS NOT NULL AND code<>'' ORDER BY code"
    ).fetchall()
    codes = [str(r["code"]) for r in rows if str(r["code"]).strip()]
    # keep province first; add a few cities if available
    out: List[str] = []
    if "450000" in codes:
        out.append("450000")
    for c in codes:
        if c != "450000":
            out.append(c)
        if len(out) >= limit:
            break
    return out[: max(1, limit)]


def _pick_organizes(con, ent_type: str, limit: int) -> List[str]:
    rows = con.execute(
        """
SELECT name FROM dict_items
WHERE category='organize' AND ent_type=? AND name IS NOT NULL AND name<>''
GROUP BY name
ORDER BY name
LIMIT ?
""",
        [ent_type, limit],
    ).fetchall()
    out = [str(r["name"]) for r in rows if str(r["name"]).strip()]
    return out or (["有限公司"] if ent_type == "1100" else ["院"])


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
    leaves: List[Dict[str, str]] = []
    for r in rows:
        raw = {}
        try:
            raw = json.loads(r["raw_json"] or "{}")
        except Exception:
            raw = {}
        if bool(raw.get("minKindSign")):
            leaves.append({"code": str(r["code"]), "name": str(r["name"] or "")})
    random.seed(123)
    random.shuffle(leaves)
    return leaves[: max(1, limit)]


def _mk_name(pre: str, core: str, organize: str) -> str:
    core = (core or "").strip()
    return (pre or "") + core + (organize or "")


def _run_one(
    c: ICPSPClient,
    *,
    ent_type: str,
    dist_code: str,
    organize: str,
    industry_code: str,
    industry_name: str,
    ind_spec: str,
    name_pre: str,
    name_core: str,
    name_mark: str,
    survey_meta: Dict[str, Any],
) -> Dict[str, Any]:
    name = _mk_name(name_pre, name_core, organize)

    banned = c.get_json("/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration", {"nameMark": name_mark})
    repeat_body = {
        "condition": "1",
        "busiId": None,
        "busiType": "01",
        "entType": ent_type,
        "name": name,
        "namePre": name_pre,
        "nameMark": name_mark,
        "distCode": dist_code,
        "areaCode": dist_code,
        "organize": organize,
        "industry": industry_code,
        "indSpec": ind_spec,
        "hasParent": None,
        "jtParentEntName": "",
    }
    repeat = c.post_json("/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat", repeat_body)

    out: Dict[str, Any] = {
        "ok": True,
        "survey_meta": survey_meta,
        "input": {
            "name": name,
            "distCode": dist_code,
            "entType": ent_type,
            "organize": organize,
            "industry": industry_code,
            "industry_name": industry_name,
            "indSpec": ind_spec,
            "namePre": name_pre,
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
    return out


def run_grid(
    *,
    ent_type: str,
    dist_limit: int,
    organize_limit: int,
    industry_limit: int,
    indspec_modes: List[str],
    name_mark_list: List[str],
    name_pre: str,
    name_core: str,
    sleep_ms: int,
) -> Dict[str, Any]:
    con = db_connect()
    regions = _pick_regions(con, dist_limit)
    organizes = _pick_organizes(con, ent_type, organize_limit)
    industries = _leaf_industries(con, ent_type, industry_limit)

    c = ICPSPClient()
    total = 0
    ok = 0
    stop = 0
    samples: List[Dict[str, Any]] = []

    for dist_code in regions:
        for organize in organizes:
            for ind in industries:
                for mode in indspec_modes:
                    for nm in name_mark_list:
                        if mode == "industry":
                            ind_spec = (ind.get("name") or "")[:8] or "软件"
                        else:
                            ind_spec = mode
                        survey_meta = {
                            "kind": "grid",
                            "entType": ent_type,
                            "distCode": dist_code,
                            "organize": organize,
                            "industry": ind.get("code"),
                            "indspec_mode": mode,
                            "nameMark": nm,
                        }
                        out = _run_one(
                            c,
                            ent_type=ent_type,
                            dist_code=dist_code,
                            organize=organize,
                            industry_code=str(ind.get("code") or ""),
                            industry_name=str(ind.get("name") or ""),
                            ind_spec=ind_spec,
                            name_pre=name_pre,
                            name_core=name_core,
                            name_mark=nm,
                            survey_meta=survey_meta,
                        )
                        total += 1
                        if out["overall"]["ok"]:
                            ok += 1
                        else:
                            stop += 1

                        insert_query_case(
                            con,
                            name=out["input"]["name"],
                            dist_code=dist_code,
                            ent_type=ent_type,
                            organize=organize,
                            industry=str(ind.get("code") or ""),
                            ind_spec=ind_spec,
                            input_obj=out["input"],
                            result_obj=out,
                        )
                        if len(samples) < 10:
                            samples.append(
                                {
                                    "overall": out["overall"],
                                    "banned_tip": out["bannedLexiconCalibration"]["explain"].get("tipStr"),
                                    "repeat_top_remark": out["nameCheckRepeat"]["explain"].get("top_remark"),
                                    "repeat_hit_count": out["nameCheckRepeat"]["explain"].get("hit_count"),
                                    "input": out["input"],
                                    "survey_meta": survey_meta,
                                }
                            )
                        if sleep_ms > 0:
                            time.sleep(sleep_ms / 1000.0)
                        if total % 100 == 0:
                            print(f"[progress] entType={ent_type} total={total} ok={ok} stop={stop}", flush=True)

    con.commit()
    return {
        "entType": ent_type,
        "namePre": name_pre,
        "nameCore": name_core,
        "nameMarkList": name_mark_list,
        "regions": regions,
        "organizes": organizes,
        "industry_count": len(industries),
        "indspec_modes": indspec_modes,
        "total": total,
        "ok": ok,
        "stop": stop,
        "samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entType", default="1100")
    ap.add_argument("--distLimit", type=int, default=2)
    ap.add_argument("--organizeLimit", type=int, default=2)
    ap.add_argument("--industryLimit", type=int, default=60)
    ap.add_argument("--indspecModes", default="industry,软件,种植,科技")
    ap.add_argument("--namePre", default="广西")
    ap.add_argument("--nameCore", default="禾泽诺企研")
    ap.add_argument("--nameMarkList", default="禾泽诺")
    ap.add_argument("--sleepMs", type=int, default=80)
    args = ap.parse_args()

    modes = [x.strip() for x in str(args.indspecModes).split(",") if x.strip()]
    marks = [x.strip() for x in str(args.nameMarkList).split(",") if x.strip()]
    result = run_grid(
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
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

