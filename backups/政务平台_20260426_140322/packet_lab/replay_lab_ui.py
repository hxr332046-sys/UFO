#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地浏览器界面：加载 mitm 片段（不写死），单步/整段重放 icpsp-api，验证「这一段」协议是否已被掌握。

启动（在 政务平台 目录）：
  .\\.venv-portal\\Scripts\\python.exe packet_lab\\replay_lab_ui.py
浏览器打开 http://127.0.0.1:8766/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

import requests
from flask import Flask, jsonify, request

from mitm_replay_core import load_icpsp_slice, replay_one_record
from icpsp_replay_assertions import apply_replay_assertions
from llm_run_digest import (
    digest_acceptance_line_for_planning,
    digest_guide_census_for_planning,
    digest_packet_chain_for_planning,
)
from namecheck_query_packet import _explain_banned, _explain_repeat
from icpsp_api_client import ICPSPClient
from dict_v2_store import (
    connect as dictv2_connect,
    stats as dictv2_stats,
    insert_query_case as dictv2_insert_query_case,
    insert_industry_analysis_run as dictv2_insert_industry_analysis_run,
)

app = Flask(__name__)

# in-memory slice: list of {line_no, preview, rec}
SLICE: list = []

RECORDS_ROOT = (ROOT / "dashboard" / "data" / "records").resolve()
_MAX_DIGEST_BYTES = 100 * 1024 * 1024


def _resolve_safe_records_json(rel: str):
    """仅允许 dashboard/data/records 下的 .json 文件（防路径穿越）。"""
    rel = (rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    p = (RECORDS_ROOT / rel).resolve()
    try:
        p.relative_to(RECORDS_ROOT)
    except ValueError:
        return None
    if p.suffix.lower() != ".json" or not p.is_file():
        return None
    try:
        if p.stat().st_size > _MAX_DIGEST_BYTES:
            return None
    except OSError:
        return None
    return p


def _default_skip() -> int:
    p = ROOT / "dashboard" / "data" / "records" / ".mitm_listen_baseline"
    if p.is_file():
        try:
            return max(0, int(p.read_text(encoding="utf-8").strip()))
        except ValueError:
            pass
    return 0


def _default_mitm() -> str:
    return str((ROOT / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl").resolve())


@app.route("/")
def index():
    return PAGE_HTML


@app.post("/api/load")
def api_load():
    global SLICE
    data = request.get_json(force=True, silent=True) or {}
    mitm = Path(data.get("mitm") or _default_mitm())
    skip = int(data.get("skip_lines", _default_skip()))
    max_n = int(data.get("max", 60))
    if not mitm.is_file():
        return jsonify({"ok": False, "error": f"file not found: {mitm}"}), 400
    rows = load_icpsp_slice(mitm, skip, max_n)
    SLICE = []
    for line_no, rec in rows:
        url = rec.get("url") or ""
        method = rec.get("method") or "?"
        SLICE.append(
            {
                "line_no": line_no,
                "method": method,
                "url_preview": (url[:180] + ("…" if len(url) > 180 else "")),
                "rec": rec,
            }
        )
    rows = [{"line_no": x["line_no"], "method": x["method"], "url_preview": x["url_preview"]} for x in SLICE]
    return jsonify(
        {
            "ok": True,
            "count": len(SLICE),
            "rows": rows,
            "mitm": str(mitm.resolve()),
            "skip_lines": skip,
            "max": max_n,
        }
    )


@app.post("/api/replay_one")
def api_replay_one():
    data = request.get_json(force=True, silent=True) or {}
    idx = int(data.get("index", -1))
    if idx < 0 or idx >= len(SLICE):
        return jsonify({"ok": False, "error": "bad index; load slice first"}), 400
    row = SLICE[idx]
    sess = requests.Session()
    r = replay_one_record(sess, row["rec"], row["line_no"])
    return jsonify({"ok": True, "result": r})


@app.post("/api/replay_all")
def api_replay_all():
    data = request.get_json(force=True, silent=True) or {}
    pause_ms = int(data.get("pause_ms", 0))
    sess = requests.Session()
    results = []
    for i, row in enumerate(SLICE):
        r = replay_one_record(sess, row["rec"], row["line_no"])
        results.append(r)
        if pause_ms > 0:
            __import__("time").sleep(pause_ms / 1000.0)
        if r.get("error"):
            break
    return jsonify({"ok": True, "count": len(results), "results": results})


@app.post("/api/replay_one_assert")
def api_replay_one_assert():
    """重放 SLICE 中一条并执行断言（用于回归模板）。"""
    data = request.get_json(force=True, silent=True) or {}
    idx = int(data.get("index", -1))
    assertions = data.get("assertions") or []
    if idx < 0 or idx >= len(SLICE):
        return jsonify({"ok": False, "error": "bad index; load slice first"}), 400
    row = SLICE[idx]
    sess = requests.Session()
    r = replay_one_record(sess, row["rec"], row["line_no"])
    ass = apply_replay_assertions(r, assertions if isinstance(assertions, list) else [])
    return jsonify({"ok": True, "replay": r, "assertion_result": ass})


@app.get("/api/llm_digest")
def api_llm_digest_get():
    rel = (request.args.get("rel_path") or request.args.get("file") or "").strip()
    obs_tail = int(request.args.get("obs_tail") or 28)
    p = _resolve_safe_records_json(rel)
    if not p:
        return jsonify({"ok": False, "error": "bad rel_path or not a .json under records/"}), 400
    raw = json.loads(p.read_text(encoding="utf-8"))
    if raw.get("census_schema") == "ufo.guide_base_core_census.v1":
        digest = digest_guide_census_for_planning(raw)
    elif raw.get("acceptance_line_schema") == "ufo.acceptance_line_02_4_1100.v1":
        digest = digest_acceptance_line_for_planning(raw)
    else:
        digest = digest_packet_chain_for_planning(raw, obs_tail=max(1, min(obs_tail, 200)))
    return jsonify({"ok": True, "rel_path": rel, "digest": digest})


@app.post("/api/llm_digest")
def api_llm_digest_post():
    data = request.get_json(force=True, silent=True) or {}
    rel = str(data.get("rel_path") or data.get("file") or "").strip()
    obs_tail = int(data.get("obs_tail") or 28)
    p = _resolve_safe_records_json(rel)
    if not p:
        return jsonify({"ok": False, "error": "bad rel_path or not a .json under records/"}), 400
    raw = json.loads(p.read_text(encoding="utf-8"))
    if raw.get("census_schema") == "ufo.guide_base_core_census.v1":
        digest = digest_guide_census_for_planning(raw)
    elif raw.get("acceptance_line_schema") == "ufo.acceptance_line_02_4_1100.v1":
        digest = digest_acceptance_line_for_planning(raw)
    else:
        digest = digest_packet_chain_for_planning(raw, obs_tail=max(1, min(obs_tail, 200)))
    return jsonify({"ok": True, "rel_path": rel, "digest": digest})


@app.post("/api/namecheck")
def api_namecheck():
    """
    直接按包查名称可用性（不依赖 UI）：
    - bannedLexiconCalibration(nameMark)
    - nameCheckRepeat(body)
    """
    data = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "missing name"}), 400
    dist = str(data.get("distCode") or "450000").strip()
    ent_type = str(data.get("entType") or "1100").strip()
    organize = str(data.get("organize") or "有限公司").strip()
    industry = str(data.get("industry") or "7519").strip()
    ind_spec = str(data.get("indSpec") or "科技").strip()
    name_pre = str(data.get("namePre") or "广西").strip()
    name_mark = str(data.get("nameMark") or "").strip() or (name.replace(name_pre, "").replace(organize, "")[:6])

    c = ICPSPClient()
    banned = c.get_json("/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration", {"nameMark": name_mark})
    repeat_body = {
        "condition": "1",
        "busiId": None,
        "busiType": "01",
        "entType": ent_type,
        "name": name,
        "namePre": name_pre,
        "nameMark": name_mark,
        "distCode": dist,
        "areaCode": dist,
        "organize": organize,
        "industry": industry,
        "indSpec": ind_spec,
        "hasParent": None,
        "jtParentEntName": "",
    }
    repeat = c.post_json("/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat", repeat_body)

    out = {
        "ok": True,
        "input": {"name": name, "distCode": dist, "entType": ent_type, "organize": organize, "industry": industry, "indSpec": ind_spec, "namePre": name_pre, "nameMark": name_mark},
        "bannedLexiconCalibration": {"code": (banned.get("code") if isinstance(banned, dict) else None), "explain": _explain_banned(banned if isinstance(banned, dict) else {})},
        "nameCheckRepeat": {"code": (repeat.get("code") if isinstance(repeat, dict) else None), "explain": _explain_repeat(repeat if isinstance(repeat, dict) else {})},
    }
    stop = bool(out["nameCheckRepeat"]["explain"].get("stop")) or (out["bannedLexiconCalibration"]["explain"].get("success") is False)
    out["overall"] = {"ok": not stop, "stop": stop}
    # V2.1: persist each query case for future explainability / replay knowledge
    try:
        con = dictv2_connect()
        case_id = dictv2_insert_query_case(
            con,
            name=name,
            dist_code=dist,
            ent_type=ent_type,
            organize=organize,
            industry=industry,
            ind_spec=ind_spec,
            input_obj=out["input"],
            result_obj=out,
        )
        out["case_id"] = case_id
    except Exception as e:
        out["case_log_error"] = repr(e)
    return jsonify(out)


@app.post("/api/v2/rebuild")
def api_v2_rebuild():
    """重建 V2 字典库（SQLite）"""
    from build_dict_v2 import main as build_main

    build_main()
    return jsonify({"ok": True})


@app.get("/api/v2/stats")
def api_v2_stats():
    con = dictv2_connect()
    return jsonify({"ok": True, "stats": dictv2_stats(con)})


@app.get("/api/v2/list")
def api_v2_list():
    category = (request.args.get("category") or "").strip()
    category_prefix = (request.args.get("categoryPrefix") or "").strip()
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or "120")
    offset = int(request.args.get("offset") or "0")
    con = dictv2_connect()
    sql = "SELECT id, category, code, name, parent_code, ent_type, busi_type, tip_ok, tip_error, recommendation, source_api FROM dict_items WHERE 1=1"
    params = []
    if category:
        sql += " AND category=?"
        params.append(category)
    elif category_prefix:
        sql += " AND category LIKE ?"
        params.append(category_prefix.rstrip("%") + "%")
    if q:
        sql += " AND (name LIKE ? OR code LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY category, code LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = [dict(r) for r in con.execute(sql, params)]
    return jsonify({"ok": True, "rows": rows, "count": len(rows)})


@app.post("/api/v2/absorb_survey")
def api_v2_absorb_survey():
    """将 query_cases 聚合吸收为 dict_items（survey_*），可重复执行。"""
    try:
        from absorb_query_cases_into_dict import absorb_from_query_cases

        out = absorb_from_query_cases()
        return jsonify({"ok": True, **out})
    except Exception as e:
        return jsonify({"ok": False, "error": repr(e)}), 500


@app.get("/api/v2/apis")
def api_v2_apis():
    con = dictv2_connect()
    rows = [dict(r) for r in con.execute("SELECT path, method, purpose, request_template, response_keys, error_patterns, recommendation FROM api_specs ORDER BY path")]
    return jsonify({"ok": True, "rows": rows})


@app.get("/api/v2/methods")
def api_v2_methods():
    con = dictv2_connect()
    rows = [dict(r) for r in con.execute("SELECT step_code, step_name, preconditions, action_desc, expected_desc, error_desc, recommendation, related_apis FROM operation_methods ORDER BY step_code")]
    return jsonify({"ok": True, "rows": rows})


@app.get("/api/v2/cases")
def api_v2_cases():
    limit = int(request.args.get("limit") or "20")
    q = (request.args.get("q") or "").strip()
    ent_type = (request.args.get("entType") or "").strip()
    stop_flag = (request.args.get("stop") or "").strip()  # "1" / "0" / ""
    name_mark = (request.args.get("nameMark") or "").strip()
    indspec_mode = (request.args.get("indspecMode") or "").strip()
    con = dictv2_connect()
    sql = """
SELECT id, queried_at, name, dist_code, ent_type, organize, industry, ind_spec,
       overall_ok, stop_flag, banned_success, banned_tip, repeat_check_state, repeat_lang_state_code, repeat_top_remark, repeat_hit_count
     , input_json, result_json
FROM query_cases
WHERE 1=1
"""
    params = []
    if q:
        sql += " AND (name LIKE ? OR banned_tip LIKE ? OR repeat_top_remark LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if ent_type:
        sql += " AND ent_type=?"
        params.append(ent_type)
    if stop_flag in ("0", "1"):
        sql += " AND stop_flag=?"
        params.append(int(stop_flag))
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    raw_rows = [dict(r) for r in con.execute(sql, params)]

    # optional cohort filters (from result_json.survey_meta)
    if name_mark or indspec_mode:
        filtered = []
        for r in raw_rows:
            try:
                res = json.loads(r.get("result_json") or "{}")
            except Exception:
                res = {}
            meta = res.get("survey_meta") if isinstance(res.get("survey_meta"), dict) else {}
            mk = str(meta.get("nameMark") or "").strip()
            md = str(meta.get("indspec_mode") or "").strip()
            if name_mark and mk != name_mark:
                continue
            if indspec_mode and md != indspec_mode:
                continue
            filtered.append(r)
        raw_rows = filtered

    # hide big json fields in response; keep in case needed later
    for r in raw_rows:
        r.pop("input_json", None)
        r.pop("result_json", None)
    return jsonify({"ok": True, "rows": raw_rows})


@app.get("/api/v2/knowledge/search")
def api_v2_knowledge_search():
    """
    知识库检索：按关键词聚合官方提示/阻断原因与样例。
    q 可命中：名称、禁限用提示、查重备注、字号(nameMark)。
    """
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or "80")
    con = dictv2_connect()
    sql = """
SELECT id, queried_at, name, ent_type, dist_code, organize, industry, ind_spec,
       overall_ok, stop_flag, banned_tip, repeat_check_state, repeat_top_remark, input_json, result_json
FROM query_cases
WHERE 1=1
"""
    params = []
    if q:
        sql += " AND (name LIKE ? OR banned_tip LIKE ? OR repeat_top_remark LIKE ? OR input_json LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in con.execute(sql, params)]

    banned_counter = {}
    repeat_counter = {}
    examples = []
    for r in rows:
        bt = str(r.get("banned_tip") or "").strip()
        rr = str(r.get("repeat_top_remark") or "").strip()
        if bt:
            banned_counter[bt] = int(banned_counter.get(bt, 0)) + 1
        if rr:
            repeat_counter[rr] = int(repeat_counter.get(rr, 0)) + 1
        if len(examples) < 20:
            item = dict(r)
            item.pop("result_json", None)
            item.pop("input_json", None)
            examples.append(item)

    top_banned = sorted(
        [{"tip": k, "count": v} for k, v in banned_counter.items()],
        key=lambda x: (-int(x["count"]), str(x["tip"])),
    )[:20]
    top_repeat = sorted(
        [{"remark": k, "count": v} for k, v in repeat_counter.items()],
        key=lambda x: (-int(x["count"]), str(x["remark"])),
    )[:20]
    return jsonify(
        {
            "ok": True,
            "query": q,
            "matched": len(rows),
            "summary": {
                "stop_count": sum(1 for r in rows if int(r.get("stop_flag") or 0) == 1),
                "ok_count": sum(1 for r in rows if int(r.get("overall_ok") or 0) == 1),
                "top_banned_tips": top_banned,
                "top_repeat_remarks": top_repeat,
            },
            "examples": examples,
        }
    )


@app.get("/api/v2/options")
def api_v2_options():
    """Provide dropdown options for name-check form from V2 dictionary."""
    ent_type = (request.args.get("entType") or "").strip()
    con = dictv2_connect()

    regions = [
        dict(r)
        for r in con.execute(
            """
SELECT code, name, parent_code
FROM dict_items
WHERE category='region' AND code IS NOT NULL AND code<>''
GROUP BY code, name, parent_code
ORDER BY code
LIMIT 5000
"""
        )
    ]
    ent_types = [
        dict(r)
        for r in con.execute(
            """
SELECT code, name
FROM dict_items
WHERE category IN ('ent_type_type1', 'ent_type_type2') AND code IS NOT NULL AND code<>''
GROUP BY code, name
ORDER BY code
"""
        )
    ]
    if ent_type:
        organizes = [
            dict(r)
            for r in con.execute(
                """
SELECT code, name, ent_type
FROM dict_items
WHERE category='organize' AND ent_type=? AND name IS NOT NULL AND name<>''
GROUP BY code, name, ent_type
ORDER BY code
LIMIT 1200
""",
                [ent_type],
            )
        ]
        industries = [
            dict(r)
            for r in con.execute(
                """
SELECT code, name, parent_code, ent_type
FROM dict_items
WHERE category='industry' AND ent_type=? AND code IS NOT NULL AND code<>''
GROUP BY code, name, parent_code, ent_type
ORDER BY code
LIMIT 6000
""",
                [ent_type],
            )
        ]
    else:
        organizes = [
            dict(r)
            for r in con.execute(
                """
SELECT code, name, ent_type
FROM dict_items
WHERE category='organize' AND name IS NOT NULL AND name<>''
GROUP BY code, name, ent_type
ORDER BY ent_type, code
LIMIT 2000
"""
            )
        ]
        industries = [
            dict(r)
            for r in con.execute(
                """
SELECT code, name, parent_code, ent_type
FROM dict_items
WHERE category='industry' AND code IS NOT NULL AND code<>''
GROUP BY code, name, parent_code, ent_type
ORDER BY ent_type, code
LIMIT 9000
"""
            )
        ]
    return jsonify(
        {
            "ok": True,
            "entType": ent_type,
            "counts": {
                "regions": len(regions),
                "ent_types": len(ent_types),
                "organizes": len(organizes),
                "industries": len(industries),
            },
            "regions": regions,
            "ent_types": ent_types,
            "organizes": organizes,
            "industries": industries,
        }
    )


def _build_industry_analysis(con, ent_type: str) -> dict:
    rows = [
        dict(r)
        for r in con.execute(
            """
SELECT code, name, parent_code, raw_json
FROM dict_items
WHERE category='industry' AND ent_type=? AND code IS NOT NULL AND code<>''
""",
            [ent_type],
        )
    ]
    by_code = {}
    for r in rows:
        by_code[str(r.get("code") or "")] = r
    kind_count = 0
    max_count = 0
    mid_count = 0
    min_count = 0
    missing_parent = []
    level_dist = {"len_1": 0, "len_2": 0, "len_3": 0, "len_4": 0}
    for r in rows:
        code = str(r.get("code") or "")
        parent = str(r.get("parent_code") or "")
        raw = {}
        try:
            raw = json.loads(r.get("raw_json") or "{}")
        except Exception:
            raw = {}
        if bool(raw.get("kindSign")):
            kind_count += 1
            level_dist["len_1"] += 1
        if bool(raw.get("maxKindSign")):
            max_count += 1
            level_dist["len_2"] += 1
        if bool(raw.get("midKindSign")):
            mid_count += 1
            level_dist["len_3"] += 1
        if bool(raw.get("minKindSign")):
            min_count += 1
            level_dist["len_4"] += 1
        if parent and parent not in by_code:
            missing_parent.append({"code": code, "parent": parent, "name": r.get("name")})

    def _chain(code: str) -> list:
        out = []
        curr = by_code.get(code)
        visited = set()
        while curr:
            c = str(curr.get("code") or "")
            if not c or c in visited:
                break
            visited.add(c)
            out.append({"code": c, "name": str(curr.get("name") or "")})
            p = str(curr.get("parent_code") or "")
            curr = by_code.get(p) if p else None
        out.reverse()
        return out

    sample_leaf_codes = ["7519", "6440"]
    sample_chain = []
    for c in sample_leaf_codes:
        if c in by_code:
            sample_chain.append({"leaf": c, "chain": _chain(c)})

    return {
        "entType": ent_type,
        "total_count": len(rows),
        "kind_count": kind_count,
        "max_count": max_count,
        "mid_count": mid_count,
        "min_count": min_count,
        "missing_parent_count": len(missing_parent),
        "missing_parent_samples": missing_parent[:20],
        "level_dist": level_dist,
        "sample_chain": sample_chain,
        "ok": len(missing_parent) == 0,
    }


@app.post("/api/v2/industry/analyze")
def api_v2_industry_analyze():
    data = request.get_json(force=True, silent=True) or {}
    ent_type = str(data.get("entType") or "1100").strip()
    con = dictv2_connect()
    payload = _build_industry_analysis(con, ent_type)
    run_id = dictv2_insert_industry_analysis_run(
        con,
        ent_type=ent_type,
        total_count=payload["total_count"],
        kind_count=payload["kind_count"],
        max_count=payload["max_count"],
        mid_count=payload["mid_count"],
        min_count=payload["min_count"],
        missing_parent_count=payload["missing_parent_count"],
        level_dist=payload["level_dist"],
        sample_chain=payload["sample_chain"],
        notes="auto analysis from dict_items(industry)",
    )
    return jsonify({"ok": True, "run_id": run_id, "analysis": payload})


@app.get("/api/v2/industry/latest")
def api_v2_industry_latest():
    ent_type = (request.args.get("entType") or "1100").strip()
    con = dictv2_connect()
    row = con.execute(
        """
SELECT id, analyzed_at, ent_type, total_count, kind_count, max_count, mid_count, min_count, missing_parent_count,
       level_dist_json, sample_chain_json, notes
FROM industry_analysis_runs
WHERE ent_type=?
ORDER BY id DESC
LIMIT 1
""",
        [ent_type],
    ).fetchone()
    if not row:
        return jsonify({"ok": True, "exists": False, "entType": ent_type})
    d = dict(row)
    d["level_dist"] = json.loads(d.pop("level_dist_json") or "{}")
    d["sample_chain"] = json.loads(d.pop("sample_chain_json") or "[]")
    d["ok"] = int(d.get("missing_parent_count") or 0) == 0
    return jsonify({"ok": True, "exists": True, "analysis": d})


PAGE_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>mitm 片段重放实验室</title>
  <link rel="stylesheet" href="https://unpkg.com/element-plus/dist/index.css"/>
  <style>
    body { margin: 0; background: #f5f7fa; }
    #app { padding: 14px; max-width: 1400px; margin: 0 auto; }
    .desc { color: #606266; margin: 0 0 10px; }
    .toolbar { margin-bottom: 10px; }
    .mono { font-family: Consolas, Monaco, monospace; }
    .log-pane {
      margin-top: 10px; background: #111; color: #d3ffd3;
      max-height: 280px; overflow: auto; border-radius: 6px; padding: 8px;
      font-family: Consolas, Monaco, monospace; font-size: 12px;
    }
    .log-bad { color: #ff9f9f; }
    .log-ok { color: #9bffa8; }
    .mb10 { margin-bottom: 10px; }
    .state-ok { color: #67c23a; font-weight: 600; }
    .state-stop { color: #f56c6c; font-weight: 600; }
  </style>
</head>
<body>
<div id="app">
  <el-card class="mb10">
    <template #header><span>mitm 片段重放（不写死路径 / 不写死行号）</span></template>
    <p class="desc">说明：登录态在每条 mitm 的 req_headers 里；仅在你点击「加载/重放」时读文件。若 401，换新抓包或改用 CDP 取 Token。</p>
    <el-form :inline="true" label-width="90px">
      <el-form-item label="mitm 文件">
        <el-input v-model="mitmForm.mitm" style="width: 680px;" placeholder="默认见服务端；也可粘贴绝对路径"/>
      </el-form-item>
      <el-form-item label="skip 行数">
        <el-input-number v-model="mitmForm.skip_lines" :min="0" :step="1"/>
      </el-form-item>
      <el-form-item label="最多条数">
        <el-input-number v-model="mitmForm.max" :min="1" :step="1"/>
      </el-form-item>
    </el-form>
    <div class="toolbar">
      <el-button type="primary" @click="loadSlice">加载片段</el-button>
      <el-button type="warning" @click="replayAll">按序全部重放</el-button>
    </div>
    <div class="desc mono">{{ sliceMeta }}</div>
    <el-table :data="sliceRows" border stripe height="260">
      <el-table-column type="index" label="#" width="60"/>
      <el-table-column prop="line_no" label="行号" width="100"/>
      <el-table-column prop="method" label="方法" width="100"/>
      <el-table-column prop="url_preview" label="URL"/>
      <el-table-column label="操作" width="110">
        <template #default="scope">
          <el-button size="small" @click="replayOne(scope.$index)">重放本条</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="mb10">
    <template #header><span>LLM 运行摘要（ufo.llm_run_digest.v1）</span></template>
    <p class="desc">仅允许读取 <span class="mono">dashboard/data/records/</span> 下已有 <span class="mono">.json</span>（如 packet_chain 演练、census 输出）。</p>
    <el-form :inline="true" label-width="88px">
      <el-form-item label="相对路径">
        <el-input v-model="digestForm.rel_path" style="width: 520px;" placeholder="packet_chain_portal_from_start.json"/>
      </el-form-item>
      <el-form-item label="obs_tail">
        <el-input-number v-model="digestForm.obs_tail" :min="1" :max="200"/>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="fetchDigest">生成 digest</el-button>
      </el-form-item>
    </el-form>
    <el-input v-model="digestJsonText" type="textarea" :rows="14" class="mono" placeholder="点击「生成 digest」后在此展示 JSON"/>
  </el-card>

  <el-card class="mb10">
    <template #header><span>名称可用性查询（按包）｜官方交互映射版</span></template>
    <el-steps :active="1" finish-status="success" simple class="mb10">
      <el-step title="主体与区划"/>
      <el-step title="名称要素"/>
      <el-step title="禁限用校验"/>
      <el-step title="重名比对"/>
    </el-steps>
    <el-row :gutter="12">
      <el-col :span="14">
        <el-form label-width="110px">
          <el-form-item label="名称">
            <el-input v-model="queryForm.name" placeholder="如：广西驰科蓝科技有限公司"/>
          </el-form-item>
          <el-form-item label="预览全称">
            <el-input :value="namePreview" readonly>
              <template #append>
                <el-button @click="applyNamePreview">使用预览全称</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="字号(nameMark)">
            <el-input v-model="queryForm.nameMark" placeholder="可手动覆盖；留空则后端自动推导">
              <template #append>
                <el-button @click="deriveNameMark">从名称提取</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="区域码">
            <el-select v-model="queryForm.distCode" filterable clearable style="width: 100%;">
              <el-option v-for="x in options.regions" :key="'r_'+x.code" :label="(x.code||'') + ' | ' + (x.name||'')" :value="x.code"/>
            </el-select>
          </el-form-item>
          <el-form-item label="主体类型">
            <el-select v-model="queryForm.entType" filterable clearable style="width: 100%;" @change="onEntTypeChange">
              <el-option v-for="x in options.ent_types" :key="'e_'+x.code" :label="(x.code||'') + ' | ' + (x.name||'')" :value="x.code"/>
            </el-select>
          </el-form-item>
          <el-form-item label="组织形式">
            <el-select v-model="queryForm.organize" filterable clearable style="width: 100%;">
              <el-option v-for="x in options.organizes" :key="'o_'+x.ent_type+'_'+x.code+'_'+x.name" :label="(x.name||'') + ' | code=' + (x.code||'')" :value="x.name"/>
            </el-select>
          </el-form-item>
          <el-form-item label="行业码">
            <el-select v-model="queryForm.industry" filterable clearable style="width: 100%;">
              <el-option v-for="x in options.industries" :key="'i_'+x.ent_type+'_'+x.code" :label="(x.code||'') + ' | ' + (x.name||'')" :value="x.code"/>
            </el-select>
          </el-form-item>
          <el-form-item label="行业特征">
            <el-select v-model="queryForm.indSpec" filterable allow-create default-first-option clearable style="width: 100%;">
              <el-option v-for="x in options.ind_specs" :key="'s_'+x" :label="x" :value="x"/>
            </el-select>
          </el-form-item>
        </el-form>
        <div class="toolbar">
          <el-button @click="refreshOptions">刷新可选项</el-button>
          <el-button type="success" @click="runNamecheck">查询</el-button>
        </div>
        <el-alert
          v-if="submitNameNeedsNormalize"
          title="当前“名称”与“预览全称”不一致；点击查询将按“预览全称”提交。"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 6px;"
        />
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>判定结果</template>
          <div v-if="namecheckResult">
            <p>
              总体：
              <span :class="namecheckResult.overall && namecheckResult.overall.ok ? 'state-ok' : 'state-stop'">
                {{ (namecheckResult.overall && namecheckResult.overall.ok) ? '可继续' : '阻断' }}
              </span>
            </p>
            <p>提交全称：<span class="mono">{{ lastSubmittedName || '-' }}</span></p>
            <p>服务端识别名称：<span class="mono">{{ (namecheckResult.input && namecheckResult.input.name) || '-' }}</span></p>
            <p>输入：<span class="mono">{{ JSON.stringify(namecheckResult.input || {}) }}</span></p>
            <p>禁限用：
              <span :class="namecheckResult.bannedLexiconCalibration && namecheckResult.bannedLexiconCalibration.explain && namecheckResult.bannedLexiconCalibration.explain.success ? 'state-ok' : 'state-stop'">
                {{ namecheckResult.bannedLexiconCalibration && namecheckResult.bannedLexiconCalibration.explain && namecheckResult.bannedLexiconCalibration.explain.success ? '通过' : '命中' }}
              </span>
            </p>
            <p class="mono">{{ (namecheckResult.bannedLexiconCalibration && namecheckResult.bannedLexiconCalibration.explain && namecheckResult.bannedLexiconCalibration.explain.tipStr) || '-' }}</p>
            <p>查重：命中 {{ (namecheckResult.nameCheckRepeat && namecheckResult.nameCheckRepeat.explain && namecheckResult.nameCheckRepeat.explain.hit_count) || 0 }} 条</p>
            <el-alert
              v-for="(x, idx) in diagnosisItems"
              :key="'diag_'+idx"
              :title="x"
              :type="(namecheckResult.overall && namecheckResult.overall.ok) ? 'success' : 'warning'"
              :closable="false"
              show-icon
              style="margin-top: 6px;"
            />
          </div>
          <div v-else class="desc">尚未查询</div>
        </el-card>
      </el-col>
    </el-row>
    <el-table v-if="namecheckHits.length" :data="namecheckHits" border stripe height="220" style="margin-top: 10px;">
      <el-table-column type="index" label="#" width="60"/>
      <el-table-column prop="entName" label="命中企业名"/>
      <el-table-column prop="regionName" label="地区" width="120"/>
      <el-table-column prop="nameMark" label="字号" width="110"/>
      <el-table-column prop="remark" label="备注" width="220"/>
    </el-table>
  </el-card>

  <el-card class="mb10">
    <template #header><span>逆开发字典数据库 V2（SQLite）</span></template>
    <el-form :inline="true" label-width="80px">
      <el-form-item label="分类">
        <el-input v-model="v2Form.category" style="width: 180px;" placeholder="精确分类，如 survey_banned_tip"/>
      </el-form-item>
      <el-form-item label="分类前缀">
        <el-input v-model="v2Form.categoryPrefix" style="width: 140px;" placeholder="survey_"/>
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="v2Form.q" style="width: 260px;"/>
      </el-form-item>
      <el-form-item label="entType">
        <el-input v-model="v2Form.entType" style="width: 120px;" placeholder="1100/4540"/>
      </el-form-item>
      <el-form-item label="stop">
        <el-select v-model="v2Form.stop" clearable style="width: 110px;">
          <el-option label="全部" value=""/>
          <el-option label="stop=1" value="1"/>
          <el-option label="stop=0" value="0"/>
        </el-select>
      </el-form-item>
      <el-form-item label="nameMark">
        <el-input v-model="v2Form.nameMark" style="width: 150px;" placeholder="对照组"/>
      </el-form-item>
      <el-form-item label="indspecMode">
        <el-input v-model="v2Form.indspecMode" style="width: 150px;" placeholder="industry/软件/种植/科技"/>
      </el-form-item>
    </el-form>
    <div class="toolbar">
      <el-button @click="v2Rebuild">重建V2字典库</el-button>
      <el-button type="success" plain @click="v2AbsorbSurvey">吸收普查入字典</el-button>
      <el-button plain @click="v2ListSurveyOnly">只看普查吸收(survey_)</el-button>
      <el-button @click="v2Stats">查看统计</el-button>
      <el-button @click="v2List">检索字典项</el-button>
      <el-button @click="v2Apis">查看协议规范</el-button>
      <el-button @click="v2Methods">查看操作方法</el-button>
      <el-button @click="v2Cases">查看最近查询样本</el-button>
      <el-button type="primary" plain @click="analyzeIndustryRules">行业规则复核并入库</el-button>
      <el-button plain @click="loadLatestIndustryRules">查看最新行业规则结论</el-button>
    </div>
  </el-card>

  <el-card class="mb10">
    <template #header><span>行业码/行业特征规则结论（入库）</span></template>
    <div v-if="industryAnalysis">
      <p>entType={{ industryAnalysis.ent_type || industryAnalysis.entType }} | analyzed_at={{ industryAnalysis.analyzed_at || '-' }}</p>
      <p>
        total={{ industryAnalysis.total_count }} |
        kind={{ industryAnalysis.kind_count }} |
        max={{ industryAnalysis.max_count }} |
        mid={{ industryAnalysis.mid_count }} |
        min={{ industryAnalysis.min_count }} |
        missing_parent={{ industryAnalysis.missing_parent_count }}
      </p>
      <p class="mono">level_dist={{ JSON.stringify(industryAnalysis.level_dist || {}) }}</p>
      <el-table :data="industrySampleRows" border stripe max-height="200">
        <el-table-column prop="leaf" label="叶子码" width="120"/>
        <el-table-column prop="chain_text" label="链路（门类->大类->中类->小类）"/>
      </el-table>
    </div>
    <div v-else class="desc">暂无分析记录，点击“行业规则复核并入库”。</div>
  </el-card>

  <el-card>
    <template #header><span>日志</span></template>
    <div class="log-pane">
      <div v-for="(x, idx) in logs" :key="'l_'+idx" :class="x.cls">{{ x.msg }}</div>
    </div>
  </el-card>
</div>

<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<script src="https://unpkg.com/element-plus/dist/index.full.min.js"></script>
<script>
const { createApp } = Vue;
createApp({
  data() {
    return {
      mitmForm: { mitm: '', skip_lines: 0, max: 60 },
      queryForm: {
        name: '广西星彤创科技有限公司',
        nameMark: '',
        distCode: '450000',
        entType: '1100',
        organize: '有限公司',
        industry: '7519',
        indSpec: '科技',
        namePre: '广西'
      },
      v2Form: { category: '', categoryPrefix: '', q: '', entType: '', stop: '', nameMark: '', indspecMode: '' },
      sliceRows: [],
      sliceMeta: '',
      options: { regions: [], ent_types: [], organizes: [], industries: [], ind_specs: [] },
      logs: [],
      namecheckResult: null,
      industryAnalysis: null,
      lastSubmittedName: '',
      digestForm: { rel_path: 'packet_chain_portal_from_start.json', obs_tail: 28 },
      digestJsonText: ''
    };
  },
  computed: {
    namecheckHits() {
      const ex = this.namecheckResult && this.namecheckResult.nameCheckRepeat && this.namecheckResult.nameCheckRepeat.explain;
      if (!ex || !Array.isArray(ex.hits_top3)) return [];
      return ex.hits_top3;
    },
    industrySampleRows() {
      if (!this.industryAnalysis || !Array.isArray(this.industryAnalysis.sample_chain)) return [];
      return this.industryAnalysis.sample_chain.map(x => ({
        leaf: x.leaf,
        chain_text: (x.chain || []).map(c => (c.code || '') + ':' + (c.name || '')).join(' -> ')
      }));
    },
    namePreview() {
      const raw = String(this.queryForm.name || '').trim();
      const pre = String(this.queryForm.namePre || '').trim();
      const org = String(this.queryForm.organize || '').trim();
      if (!raw) return '';
      const hasPre = pre && raw.startsWith(pre);
      const hasOrg = org && raw.endsWith(org);
      if (hasPre && hasOrg) return raw;
      const core = raw.replace(pre, '').replace(org, '').trim();
      return (pre || '') + core + (org || '');
    },
    submitNameNeedsNormalize() {
      const raw = String(this.queryForm.name || '').trim();
      const preview = String(this.namePreview || '').trim();
      return !!raw && !!preview && raw !== preview;
    },
    diagnosisItems() {
      const r = this.namecheckResult;
      if (!r) return [];
      const out = [];
      const overall = r.overall || {};
      const b = (r.bannedLexiconCalibration || {}).explain || {};
      const rep = (r.nameCheckRepeat || {}).explain || {};
      if (overall.ok) {
        out.push('总体可继续：当前组合未触发硬阻断。');
      } else {
        out.push('总体阻断：请按下列原因调整名称参数后重试。');
      }
      if (b.success === false) {
        out.push('禁限用命中：' + (b.tipStr || '存在禁限用词命中'));
      } else if (b.success === true) {
        out.push('禁限用通过：未发现禁限用词。');
      }
      if (rep.stop) {
        out.push('查重阻断：' + (rep.top_remark || rep.langStateCode || '名称重复/近似导致阻断'));
      } else {
        out.push('查重提示：命中 ' + String(rep.hit_count || 0) + ' 条，状态=' + String(rep.checkState || '-') + '，结论=' + String(rep.top_remark || '相似提示，可继续'));
      }
      return out;
    }
  },
  methods: {
    pushLog(msg, cls) {
      this.logs.push({ msg: String(msg), cls: cls || '' });
    },
    clearLog() {
      this.logs = [];
    },
    async fetchDigest() {
      const j = await this.postJson('/api/llm_digest', {
        rel_path: this.digestForm.rel_path,
        obs_tail: parseInt(this.digestForm.obs_tail, 10) || 28
      });
      if (!j.ok) {
        this.pushLog('digest 失败: ' + (j.error || JSON.stringify(j)), 'log-bad');
        this.digestJsonText = '';
        return;
      }
      this.digestJsonText = JSON.stringify(j.digest || {}, null, 2);
      this.pushLog('digest 已生成: ' + (j.rel_path || ''), 'log-ok');
    },
    async postJson(path, body) {
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      return r.json();
    },
    async loadDefaults() {
      const r = await fetch('/api/defaults');
      const j = await r.json();
      this.mitmForm.mitm = j.mitm || '';
      this.mitmForm.skip_lines = parseInt(j.skip_lines || 0, 10);
    },
    async loadSlice() {
      this.clearLog();
      const j = await this.postJson('/api/load', this.mitmForm);
      if (!j.ok) { this.pushLog('加载失败: ' + (j.error || JSON.stringify(j)), 'log-bad'); return; }
      this.sliceRows = j.rows || [];
      this.sliceMeta = '已加载 ' + j.count + ' 条 | ' + j.mitm + ' | skip=' + j.skip_lines;
      this.pushLog('加载成功', 'log-ok');
    },
    async replayOne(index) {
      const j = await this.postJson('/api/replay_one', { index });
      this.pushLog(JSON.stringify(j.result || j), (j.result && j.result.error) ? 'log-bad' : 'log-ok');
    },
    async replayAll() {
      this.clearLog();
      const j = await this.postJson('/api/replay_all', { pause_ms: 50 });
      if (!j.ok) { this.pushLog('重放失败', 'log-bad'); return; }
      this.pushLog('完成 ' + j.count + ' 条', 'log-ok');
      (j.results || []).forEach(x => this.pushLog(JSON.stringify(x), x.error ? 'log-bad' : 'log-ok'));
    },
    async loadOptions() {
      const r = await fetch('/api/v2/options?entType=' + encodeURIComponent(this.queryForm.entType || ''));
      const j = await r.json();
      if (!j.ok) {
        this.pushLog('加载可选项失败: ' + JSON.stringify(j), 'log-bad');
        return;
      }
      this.options.regions = j.regions || [];
      this.options.ent_types = j.ent_types || [];
      this.options.organizes = j.organizes || [];
      this.options.industries = j.industries || [];
      const specs = new Set();
      (this.options.industries || []).forEach(x => { if (x && x.name) specs.add(String(x.name)); });
      this.options.ind_specs = Array.from(specs).slice(0, 500);
      this.pushLog('可选项已加载: ' + JSON.stringify(j.counts || {}), 'log-ok');
    },
    async onEntTypeChange() {
      await this.loadOptions();
      this.queryForm.organize = '';
      this.queryForm.industry = '';
    },
    deriveNameMark() {
      const name = String(this.queryForm.name || '').trim();
      const pre = String(this.queryForm.namePre || '').trim();
      const org = String(this.queryForm.organize || '').trim();
      this.queryForm.nameMark = name.replace(pre, '').replace(org, '').slice(0, 6);
      this.pushLog('已按名称提取 nameMark=' + this.queryForm.nameMark, 'log-ok');
    },
    applyNamePreview() {
      if (!this.namePreview) {
        this.pushLog('名称为空，无法生成预览全称', 'log-bad');
        return;
      }
      this.queryForm.name = this.namePreview;
      this.pushLog('已使用预览全称：' + this.namePreview, 'log-ok');
    },
    async refreshOptions() {
      this.clearLog();
      await this.loadOptions();
    },
    async runNamecheck() {
      this.clearLog();
      if (this.submitNameNeedsNormalize) {
        const ok = window.confirm('当前“名称”与“预览全称”不一致。\n将按预览全称提交：' + this.namePreview + '\n是否继续？');
        if (!ok) {
          this.pushLog('已取消查询：请先确认名称全称。', 'log-bad');
          return;
        }
      }
      const payload = Object.assign({}, this.queryForm, { name: this.namePreview || this.queryForm.name });
      this.lastSubmittedName = payload.name || '';
      const j = await this.postJson('/api/namecheck', payload);
      if (!j.ok) { this.pushLog('查询失败: ' + (j.error || JSON.stringify(j)), 'log-bad'); return; }
      this.namecheckResult = j;
      this.pushLog('submitted_name=' + this.lastSubmittedName, 'log-ok');
      this.pushLog('input=' + JSON.stringify(j.input), 'log-ok');
      this.pushLog('overall=' + JSON.stringify(j.overall), (j.overall && j.overall.ok) ? 'log-ok' : 'log-bad');
      this.pushLog('banned=' + JSON.stringify(j.bannedLexiconCalibration.explain), (j.bannedLexiconCalibration.explain && j.bannedLexiconCalibration.explain.success) ? 'log-ok' : 'log-bad');
      this.pushLog('repeat=' + JSON.stringify(j.nameCheckRepeat.explain), (j.nameCheckRepeat.explain && j.nameCheckRepeat.explain.stop) ? 'log-bad' : 'log-ok');
    },
    async v2Rebuild() {
      this.clearLog();
      this.pushLog('注意：重建会清空 dict_items（含 survey_* 普查吸收项），完成后需重新点「吸收普查入字典」。', 'log-bad');
      const j = await this.postJson('/api/v2/rebuild', {});
      this.pushLog('v2 rebuild=' + JSON.stringify(j), j.ok ? 'log-ok' : 'log-bad');
    },
    async v2Stats() {
      this.clearLog();
      const r = await fetch('/api/v2/stats');
      const j = await r.json();
      this.pushLog(JSON.stringify(j.stats || j), 'log-ok');
    },
    async v2List() {
      this.clearLog();
      const cat = (this.v2Form.category || '').trim();
      const pfx = (this.v2Form.categoryPrefix || '').trim();
      let url = '/api/v2/list?q=' + encodeURIComponent(this.v2Form.q || '') + '&limit=120';
      if (cat) {
        url += '&category=' + encodeURIComponent(cat);
      } else if (pfx) {
        url += '&categoryPrefix=' + encodeURIComponent(pfx);
      }
      const r = await fetch(url);
      const j = await r.json();
      this.pushLog('count=' + (j.count || 0), 'log-ok');
      (j.rows || []).slice(0, 24).forEach(x => this.pushLog(JSON.stringify(x), 'log-ok'));
    },
    async v2AbsorbSurvey() {
      this.clearLog();
      const j = await this.postJson('/api/v2/absorb_survey', {});
      this.pushLog('吸收普查=' + JSON.stringify(j), j.ok ? 'log-ok' : 'log-bad');
    },
    async v2ListSurveyOnly() {
      this.v2Form.category = '';
      this.v2Form.categoryPrefix = 'survey_';
      await this.v2List();
    },
    async v2Apis() {
      this.clearLog();
      const r = await fetch('/api/v2/apis');
      const j = await r.json();
      this.pushLog('api_specs=' + ((j.rows || []).length), 'log-ok');
      (j.rows || []).forEach(x => this.pushLog((x.method || '') + ' ' + (x.path || '') + ' | ' + (x.purpose || ''), 'log-ok'));
    },
    async v2Methods() {
      this.clearLog();
      const r = await fetch('/api/v2/methods');
      const j = await r.json();
      this.pushLog('operation_methods=' + ((j.rows || []).length), 'log-ok');
      (j.rows || []).forEach(x => this.pushLog((x.step_code || '') + ' ' + (x.step_name || ''), 'log-ok'));
    },
    async v2Cases() {
      this.clearLog();
      const qs = [
        'limit=50',
        'q=' + encodeURIComponent(this.v2Form.q || ''),
        'entType=' + encodeURIComponent(this.v2Form.entType || ''),
        'stop=' + encodeURIComponent(this.v2Form.stop || ''),
        'nameMark=' + encodeURIComponent(this.v2Form.nameMark || ''),
        'indspecMode=' + encodeURIComponent(this.v2Form.indspecMode || ''),
      ].join('&');
      const r = await fetch('/api/v2/cases?' + qs);
      const j = await r.json();
      this.pushLog('query_cases=' + ((j.rows || []).length), 'log-ok');
      (j.rows || []).forEach(x => this.pushLog(JSON.stringify(x), x.stop_flag ? 'log-bad' : 'log-ok'));
    },
    async analyzeIndustryRules() {
      this.clearLog();
      const entType = this.queryForm.entType || '1100';
      const j = await this.postJson('/api/v2/industry/analyze', { entType });
      if (!j.ok) { this.pushLog('行业规则复核失败: ' + JSON.stringify(j), 'log-bad'); return; }
      this.industryAnalysis = j.analysis || null;
      this.pushLog('行业规则已入库 run_id=' + j.run_id, 'log-ok');
      this.pushLog('analysis=' + JSON.stringify(j.analysis || {}), (j.analysis && j.analysis.ok) ? 'log-ok' : 'log-bad');
    },
    async loadLatestIndustryRules() {
      this.clearLog();
      const entType = this.queryForm.entType || '1100';
      const r = await fetch('/api/v2/industry/latest?entType=' + encodeURIComponent(entType));
      const j = await r.json();
      if (!j.ok || !j.exists) {
        this.pushLog('暂无行业规则分析记录', 'log-bad');
        this.industryAnalysis = null;
        return;
      }
      this.industryAnalysis = j.analysis || null;
      this.pushLog('已加载最新行业规则结论', (j.analysis && j.analysis.ok) ? 'log-ok' : 'log-bad');
    }
  },
  async mounted() {
    await this.loadDefaults();
    await this.loadOptions();
    await this.loadLatestIndustryRules();
  }
}).use(ElementPlus).mount('#app');
</script>
</body>
</html>
"""


@app.get("/api/defaults")
def api_defaults():
    return jsonify({"mitm": _default_mitm(), "skip_lines": _default_skip()})


def main() -> None:
    print("open http://127.0.0.1:8766/  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=8766, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
