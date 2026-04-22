#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从一次 packet_chain JSON 或 guide 普查 JSON 生成给规划层的紧凑摘要（固定结构、可截断 tail）。

schema: ufo.llm_run_digest.v1 — 与完整 rec 并存，便于 API/提示词拼装。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def digest_packet_chain_for_planning(
    rec: Dict[str, Any],
    *,
    obs_tail: int = 28,
    blocker_tail: int = 12,
) -> Dict[str, Any]:
    be = rec.get("blocker_evidence") or []
    tags: List[Optional[str]] = []
    for b in be[-blocker_tail:]:
        if isinstance(b, dict):
            tags.append(str(b.get("tag") or "") or None)
    obs = rec.get("llm_observations") or []
    if not isinstance(obs, list):
        obs = []
    return {
        "schema": "ufo.llm_run_digest.v1",
        "source": "packet_chain",
        "run_id": rec.get("run_id"),
        "started_at": rec.get("started_at"),
        "ended_at": rec.get("ended_at"),
        "task": rec.get("task"),
        "acceptance": rec.get("acceptance"),
        "framework_notes": rec.get("framework_notes"),
        "llm_observations_tail": obs[-obs_tail:],
        "blocker_evidence_tags_tail": [t for t in tags if t],
        "run_error": rec.get("run_error"),
    }


def digest_guide_census_for_planning(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "ufo.llm_run_digest.v1",
        "source": "guide_base_core_census",
        "run_id": rec.get("run_id"),
        "started_at": rec.get("started_at"),
        "ended_at": rec.get("ended_at"),
        "overall_outcome": rec.get("overall_outcome"),
        "segments": rec.get("segments"),
        "error": rec.get("error"),
    }


def digest_acceptance_line_for_planning(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "ufo.llm_run_digest.v1",
        "source": "acceptance_line_02_4_1100",
        "run_id": rec.get("run_id"),
        "started_at": rec.get("started_at"),
        "ended_at": rec.get("ended_at"),
        "verdict": rec.get("verdict"),
        "acceptance": rec.get("acceptance"),
        "phases": rec.get("phases"),
        "error": rec.get("error"),
    }


def _main() -> int:
    ap = argparse.ArgumentParser(description="从 JSON 文件生成 ufo.llm_run_digest.v1")
    ap.add_argument("json_path", type=Path, help="packet_chain 或 census 输出 JSON")
    ap.add_argument("--obs-tail", type=int, default=28)
    ap.add_argument("-o", "--output", type=Path, default=None, help="写入文件；省略则打印到 stdout")
    args = ap.parse_args()
    raw = json.loads(args.json_path.read_text(encoding="utf-8"))
    if raw.get("census_schema") == "ufo.guide_base_core_census.v1":
        out = digest_guide_census_for_planning(raw)
    elif raw.get("acceptance_line_schema") == "ufo.acceptance_line_02_4_1100.v1":
        out = digest_acceptance_line_for_planning(raw)
    else:
        out = digest_packet_chain_for_planning(raw, obs_tail=args.obs_tail)
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
