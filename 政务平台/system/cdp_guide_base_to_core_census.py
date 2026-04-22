#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
guide/base（S08）→ core 专用普查：按 entType 分段导航、每轮结构化诊断 + 可选类人自动填/主按钮，
用于矩阵化记录「卡在哪」而非替代 packet_chain 主链。

输出：dashboard/data/records/cdp_guide_base_to_core_census_latest.json
schema 根字段：census_schema=ufo.guide_base_core_census.v1

用法（政务平台根目录，需已登录 9087 CDP）:
  .\\.venv-portal\\Scripts\\python.exe system\\cdp_guide_base_to_core_census.py
  .\\.venv-portal\\Scripts\\python.exe system\\cdp_guide_base_to_core_census.py --ent-types 1100,4540 --probe-rounds 6
  .\\.venv-portal\\Scripts\\python.exe system\\cdp_guide_base_to_core_census.py --no-nav --no-autoclick
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from gov_task_run_model import new_run_id  # noqa: E402
from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from icpsp_entry import ICPSP_HOST, ICPSP_PORT, ensure_icpsp_entry  # noqa: E402

# 复用与 packet_chain 一致的页内探测/动作（避免分叉两套 JS）
from packet_chain_portal_from_start import (  # noqa: E402
    CDP,
    CLICK_FIRST_PRIMARY,
    GUIDE_BASE_AUTOFILL_V2,
    READ_BLOCKER_UI_JS,
    S08_EXIT_DIAGNOSTIC_JS,
    YUN_SUBMIT_PROBE,
)

OUT = ROOT / "dashboard" / "data" / "records" / "cdp_guide_base_to_core_census_latest.json"
NAME_REG = f"https://{ICPSP_HOST}:{ICPSP_PORT}/icpsp-web-pc/name-register.html"


def guide_base_href(busi_type: str, ent_type: str) -> str:
    return f"{NAME_REG}#/guide/base?busiType={busi_type}&entType={ent_type}&marPrId=&marUniscId="


def _cdp_port() -> int:
    with (ROOT / "config" / "browser.json").open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _summarize_round(
    yun: Any,
    s08: Any,
    ui: Any,
    gfill: Any,
    click: Any,
) -> Dict[str, Any]:
    href = ""
    if isinstance(yun, dict):
        href = str(yun.get("href") or "")
    return {
        "href": href,
        "has_core": "core.html" in href,
        "has_yun_submit": bool(isinstance(yun, dict) and yun.get("hasYunSubmit")),
        "has_face_sms_gate": bool(isinstance(yun, dict) and yun.get("hasFaceSmsGate")),
        "s08_menu_count": (s08 or {}).get("cascaderVisibleMenus") if isinstance(s08, dict) else None,
        "s08_form_errors": (s08 or {}).get("formErrors") if isinstance(s08, dict) else None,
        "s08_message_boxes": (s08 or {}).get("messageBoxes") if isinstance(s08, dict) else None,
        "ui_errors": (ui or {}).get("errors") if isinstance(ui, dict) else None,
        "ui_message_box": (str((ui or {}).get("messageBox") or "")[:220]) if isinstance(ui, dict) else None,
        "autofill_log": (gfill or {}).get("log") if isinstance(gfill, dict) else None,
        "primary_click": click,
    }


def _segment_outcome(rounds: List[Dict[str, Any]]) -> str:
    for r in rounds:
        if r.get("has_core"):
            return "reached_core"
        if r.get("has_yun_submit"):
            return "reached_yun_submit_text"
    return "no_transition"


def main() -> int:
    ap = argparse.ArgumentParser(description="guide/base → core 普查（结构化诊断 + 可选类人点击）")
    ap.add_argument("--busi-type", default="02_4", help="busiType 查询参数")
    ap.add_argument(
        "--ent-types",
        default="1100",
        help="逗号分隔 entType，将按顺序各跑一段（每段重新导航 guide/base）",
    )
    ap.add_argument("--probe-rounds", type=int, default=8, help="每段最大轮数（每轮：探测→可选 autofill→可选主按钮）")
    ap.add_argument("--no-nav", action="store_true", help="不整页跳 guide/base（仅在当前页普查）")
    ap.add_argument(
        "--force-nav",
        action="store_true",
        help="即使已在 guide/base 也强制 location 到目标 URL（刷新参数矩阵）",
    )
    ap.add_argument("--no-autoclick", action="store_true", help="不执行 GUIDE_BASE_AUTOFILL_V2 与主按钮点击，仅记录诊断")
    ap.add_argument(
        "--stop-on-core",
        action="store_true",
        help="任一段出现 core.html 后不再跑后续 entType（默认跑满列表以做矩阵）",
    )
    ap.add_argument("--human-fast", action="store_true", help="关闭类人节奏")
    ap.add_argument("-o", "--output", type=Path, default=OUT)
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=args.human_fast)
    ent_list = [x.strip() for x in (args.ent_types or "").split(",") if x.strip()]
    if not ent_list:
        ent_list = ["1100"]

    rec: Dict[str, Any] = {
        "census_schema": "ufo.guide_base_core_census.v1",
        "run_id": new_run_id(),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "busi_type": str(args.busi_type),
        "ent_types": ent_list,
        "probe_rounds_cap": int(args.probe_rounds),
        "flags": {
            "no_nav": bool(args.no_nav),
            "force_nav": bool(args.force_nav),
            "no_autoclick": bool(args.no_autoclick),
            "human_fast": bool(args.human_fast),
        },
        "segments": [],
    }

    nav = ensure_icpsp_entry(_cdp_port(), busi_type=str(args.busi_type), navigate_policy="host_only", wait_after_nav_sec=2.5)
    rec["ensure_icpsp_entry"] = nav
    ws_url = nav.get("ws_url")
    if not ws_url:
        rec["error"] = "no_ws"
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ERROR", rec.get("error"))
        return 2

    cdp: Optional[CDP] = None
    try:
        cdp = CDP(ws_url)
        for ent in ent_list:
            seg: Dict[str, Any] = {"ent_type": ent, "busi_type": str(args.busi_type), "rounds": []}
            href_now = str(cdp.ev(r"(function(){return location.href;})()") or "")
            target = guide_base_href(str(args.busi_type), ent)
            do_nav = not args.no_nav and (args.force_nav or ("guide/base" not in href_now))
            if args.no_nav:
                seg["nav"] = {"skipped": True, "href_before": href_now}
            elif do_nav:
                cdp.ev(f"location.href = {json.dumps(target, ensure_ascii=False)}")
                sleep_human(3.6)
                seg["nav"] = {"assigned": True, "target": target, "href_after": cdp.ev(r"(function(){return location.href;})()")}
            else:
                seg["nav"] = {"skipped": True, "reason": "already_guide_base_or_no_force", "href": href_now}

            stopped = False
            for ri in range(max(1, int(args.probe_rounds))):
                yun = cdp.ev(YUN_SUBMIT_PROBE)
                s08 = cdp.ev(S08_EXIT_DIAGNOSTIC_JS)
                ui = cdp.ev(READ_BLOCKER_UI_JS)
                gfill: Any = None
                clk: Any = None
                if not args.no_autoclick:
                    gfill = cdp.ev(GUIDE_BASE_AUTOFILL_V2)
                    sleep_human(1.15)
                    clk = cdp.ev(CLICK_FIRST_PRIMARY)
                    sleep_human(2.0)
                row = _summarize_round(yun, s08, ui, gfill, clk)
                row["i"] = ri
                seg["rounds"].append(row)
                if row.get("has_core") or row.get("has_yun_submit"):
                    stopped = True
                    break
                if row.get("has_face_sms_gate"):
                    seg["early_stop"] = "face_or_sms_gate_detected"
                    stopped = True
                    break
                sleep_human(1.0)
            seg["outcome"] = _segment_outcome(seg["rounds"])
            seg["stopped_early"] = stopped
            rec["segments"].append(seg)
            if args.stop_on_core and seg["outcome"] == "reached_core":
                break
        reached = [s.get("outcome") for s in rec["segments"] if s.get("outcome") == "reached_core"]
        if reached:
            rec["overall_outcome"] = "reached_core"
        elif rec["segments"]:
            rec["overall_outcome"] = rec["segments"][-1].get("outcome") or "unknown"
        else:
            rec["overall_outcome"] = "empty"
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {args.output} overall_outcome={rec.get('overall_outcome')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
