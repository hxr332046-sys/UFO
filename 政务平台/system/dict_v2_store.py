#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2 dictionary SQLite store for reverse-engineering framework."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DB_PATH = Path("G:/UFO/政务平台/dashboard/data/records/dict_v2.sqlite")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    init_schema(con)
    return con


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
CREATE TABLE IF NOT EXISTS survey_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_tag TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  source TEXT,
  note TEXT
);

CREATE TABLE IF NOT EXISTS dict_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL,        -- ent_type / region / organize / industry / rule / etc.
  code TEXT,
  name TEXT,
  parent_code TEXT,
  ent_type TEXT,
  busi_type TEXT,
  tags TEXT,                     -- JSON array string
  tip_ok TEXT,
  tip_error TEXT,
  recommendation TEXT,
  source_api TEXT,
  source_file TEXT,
  raw_json TEXT,
  run_id INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dict_items_cat ON dict_items(category);
CREATE INDEX IF NOT EXISTS idx_dict_items_code ON dict_items(code);
CREATE INDEX IF NOT EXISTS idx_dict_items_name ON dict_items(name);
CREATE INDEX IF NOT EXISTS idx_dict_items_ent ON dict_items(ent_type);

CREATE TABLE IF NOT EXISTS api_specs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  method TEXT NOT NULL,
  purpose TEXT,
  request_template TEXT,
  response_keys TEXT,
  error_patterns TEXT,
  recommendation TEXT,
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_specs_unique ON api_specs(path, method);

CREATE TABLE IF NOT EXISTS operation_methods (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  step_code TEXT NOT NULL,
  step_name TEXT NOT NULL,
  preconditions TEXT,
  action_desc TEXT,
  expected_desc TEXT,
  error_desc TEXT,
  recommendation TEXT,
  related_apis TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operation_methods_step ON operation_methods(step_code);

CREATE TABLE IF NOT EXISTS query_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queried_at TEXT NOT NULL,
  name TEXT NOT NULL,
  dist_code TEXT,
  ent_type TEXT,
  organize TEXT,
  industry TEXT,
  ind_spec TEXT,
  overall_ok INTEGER,
  stop_flag INTEGER,
  banned_success INTEGER,
  banned_tip TEXT,
  repeat_check_state TEXT,
  repeat_lang_state_code TEXT,
  repeat_top_remark TEXT,
  repeat_hit_count INTEGER,
  input_json TEXT,
  result_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_query_cases_time ON query_cases(queried_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_cases_name ON query_cases(name);

CREATE TABLE IF NOT EXISTS industry_analysis_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analyzed_at TEXT NOT NULL,
  ent_type TEXT NOT NULL,
  total_count INTEGER,
  kind_count INTEGER,
  max_count INTEGER,
  mid_count INTEGER,
  min_count INTEGER,
  missing_parent_count INTEGER,
  level_dist_json TEXT,
  sample_chain_json TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_industry_analysis_runs_time ON industry_analysis_runs(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_industry_analysis_runs_ent ON industry_analysis_runs(ent_type, analyzed_at DESC);
"""
    )
    con.commit()


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def clear_v2_data(con: sqlite3.Connection) -> None:
    con.execute("DELETE FROM dict_items")
    con.execute("DELETE FROM api_specs")
    con.execute("DELETE FROM operation_methods")
    con.commit()


def begin_run(con: sqlite3.Connection, run_tag: str, source: str, note: str = "") -> int:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    cur = con.execute(
        "INSERT INTO survey_runs(run_tag, started_at, source, note) VALUES(?,?,?,?)",
        (run_tag, now, source, note),
    )
    con.commit()
    return int(cur.lastrowid)


def end_run(con: sqlite3.Connection, run_id: int) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    con.execute("UPDATE survey_runs SET ended_at=? WHERE id=?", (now, run_id))
    con.commit()


def insert_dict_item(
    con: sqlite3.Connection,
    *,
    category: str,
    code: Optional[str],
    name: Optional[str],
    parent_code: Optional[str] = None,
    ent_type: Optional[str] = None,
    busi_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    tip_ok: Optional[str] = None,
    tip_error: Optional[str] = None,
    recommendation: Optional[str] = None,
    source_api: Optional[str] = None,
    source_file: Optional[str] = None,
    raw_json: Optional[Dict[str, Any]] = None,
    run_id: Optional[int] = None,
) -> None:
    con.execute(
        """
INSERT INTO dict_items(
  category, code, name, parent_code, ent_type, busi_type, tags,
  tip_ok, tip_error, recommendation, source_api, source_file, raw_json, run_id, created_at
) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""",
        (
            category,
            code,
            name,
            parent_code,
            ent_type,
            busi_type,
            _j(tags or []),
            tip_ok,
            tip_error,
            recommendation,
            source_api,
            source_file,
            _j(raw_json) if raw_json is not None else None,
            run_id,
            time.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def upsert_api_spec(
    con: sqlite3.Connection,
    *,
    path: str,
    method: str,
    purpose: str,
    request_template: Dict[str, Any],
    response_keys: List[str],
    error_patterns: List[str],
    recommendation: str,
) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        """
INSERT OR REPLACE INTO api_specs(
  id, path, method, purpose, request_template, response_keys, error_patterns, recommendation, created_at
)
VALUES(
  (SELECT id FROM api_specs WHERE path=? AND method=?),
  ?,?,?,?,?,?,?,?
)
""",
        (
            path,
            method,
            path,
            method,
            purpose,
            _j(request_template),
            _j(response_keys),
            _j(error_patterns),
            recommendation,
            now,
        ),
    )


def insert_operation_method(
    con: sqlite3.Connection,
    *,
    step_code: str,
    step_name: str,
    preconditions: List[str],
    action_desc: str,
    expected_desc: str,
    error_desc: str,
    recommendation: str,
    related_apis: List[str],
) -> None:
    con.execute(
        """
INSERT INTO operation_methods(
  step_code, step_name, preconditions, action_desc, expected_desc, error_desc, recommendation, related_apis, created_at
) VALUES(?,?,?,?,?,?,?,?,?)
""",
        (
            step_code,
            step_name,
            _j(preconditions),
            action_desc,
            expected_desc,
            error_desc,
            recommendation,
            _j(related_apis),
            time.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def stats(con: sqlite3.Connection) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["dict_items_total"] = int(con.execute("SELECT COUNT(*) c FROM dict_items").fetchone()["c"])
    out["api_specs_total"] = int(con.execute("SELECT COUNT(*) c FROM api_specs").fetchone()["c"])
    out["operation_methods_total"] = int(con.execute("SELECT COUNT(*) c FROM operation_methods").fetchone()["c"])
    out["query_cases_total"] = int(con.execute("SELECT COUNT(*) c FROM query_cases").fetchone()["c"])
    out["by_category"] = [
        {"category": r["category"], "count": r["c"]}
        for r in con.execute("SELECT category, COUNT(*) c FROM dict_items GROUP BY category ORDER BY c DESC")
    ]
    return out


def insert_query_case(
    con: sqlite3.Connection,
    *,
    name: str,
    dist_code: str,
    ent_type: str,
    organize: str,
    industry: str,
    ind_spec: str,
    input_obj: Dict[str, Any],
    result_obj: Dict[str, Any],
) -> int:
    overall = result_obj.get("overall") if isinstance(result_obj.get("overall"), dict) else {}
    banned = result_obj.get("bannedLexiconCalibration") if isinstance(result_obj.get("bannedLexiconCalibration"), dict) else {}
    banned_ex = banned.get("explain") if isinstance(banned.get("explain"), dict) else {}
    repeat = result_obj.get("nameCheckRepeat") if isinstance(result_obj.get("nameCheckRepeat"), dict) else {}
    repeat_ex = repeat.get("explain") if isinstance(repeat.get("explain"), dict) else {}

    cur = con.execute(
        """
INSERT INTO query_cases(
  queried_at, name, dist_code, ent_type, organize, industry, ind_spec,
  overall_ok, stop_flag, banned_success, banned_tip,
  repeat_check_state, repeat_lang_state_code, repeat_top_remark, repeat_hit_count,
  input_json, result_json
) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""",
        (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            name,
            dist_code,
            ent_type,
            organize,
            industry,
            ind_spec,
            1 if bool(overall.get("ok")) else 0,
            1 if bool(overall.get("stop")) else 0,
            None if banned_ex.get("success") is None else (1 if bool(banned_ex.get("success")) else 0),
            str(banned_ex.get("tipStr") or "")[:1000],
            str(repeat_ex.get("checkState") or ""),
            str(repeat_ex.get("langStateCode") or ""),
            str(repeat_ex.get("top_remark") or "")[:1000],
            int(repeat_ex.get("hit_count") or 0),
            _j(input_obj),
            _j(result_obj),
        ),
    )
    con.commit()
    return int(cur.lastrowid)


def insert_industry_analysis_run(
    con: sqlite3.Connection,
    *,
    ent_type: str,
    total_count: int,
    kind_count: int,
    max_count: int,
    mid_count: int,
    min_count: int,
    missing_parent_count: int,
    level_dist: Dict[str, int],
    sample_chain: List[Dict[str, Any]],
    notes: str = "",
) -> int:
    cur = con.execute(
        """
INSERT INTO industry_analysis_runs(
  analyzed_at, ent_type, total_count, kind_count, max_count, mid_count, min_count, missing_parent_count,
  level_dist_json, sample_chain_json, notes
) VALUES(?,?,?,?,?,?,?,?,?,?,?)
""",
        (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ent_type,
            int(total_count),
            int(kind_count),
            int(max_count),
            int(mid_count),
            int(min_count),
            int(missing_parent_count),
            _j(level_dist),
            _j(sample_chain),
            notes,
        ),
    )
    con.commit()
    return int(cur.lastrowid)

