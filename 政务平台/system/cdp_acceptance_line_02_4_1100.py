#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验收线 L1：busiType=02_4 + entType=1100 —— name-register **#/guide/base** → **core.html** →
尽力用类人节奏点主按钮前进，直至判定「材料相关第一屏」（可见 file 控件或材料关键词 + 上传区）。

不点「云提交」；遇云提交/实人门控文案则停在本阶段并记入验收项。

输出：dashboard/data/records/acceptance_line_02_4_1100_latest.json
根字段：acceptance_line_schema=ufo.acceptance_line_02_4_1100.v1
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

from cdp_attachment_upload import PROBE_FILE_CONTEXT_JS  # noqa: E402
from gov_task_run_model import new_run_id  # noqa: E402
from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from icpsp_entry import ICPSP_HOST, ICPSP_PORT, ensure_icpsp_entry  # noqa: E402
from packet_chain_portal_from_start import (  # noqa: E402
    CDP,
    CLICK_FIRST_PRIMARY,
    GUIDE_BASE_AUTOFILL_V2,
    READ_BLOCKER_UI_JS,
    YUN_SUBMIT_PROBE,
)

OUT = ROOT / "dashboard" / "data" / "records" / "acceptance_line_02_4_1100_latest.json"
NAME_REG = f"https://{ICPSP_HOST}:{ICPSP_PORT}/icpsp-web-pc/name-register.html"
BUSI = "02_4"
ENT = "1100"

MATERIALS_FIRST_PROBE_JS = r"""(function(){
  var href = location.href || '';
  var h = location.hash || '';
  var t = (document.body && document.body.innerText) || '';
  var inputs = [...document.querySelectorAll('input[type=file]')];
  var visFiles = inputs.filter(function(inp){
    var r = inp.getBoundingClientRect();
    return inp.offsetParent !== null && r.width > 0 && r.height > 0;
  }).length;
  var kw = /材料|附件资料|扫描件|上传文件|要件|电子化材料|附件上传|设立登记提交材料/.test(t);
  var hashMat = /material|attach|doc|file|matter|upload|engagement/i.test(h);
  return {
    href: href.slice(0, 520),
    hash: h.slice(0, 300),
    visible_file_inputs: visFiles,
    total_file_inputs: inputs.length,
    body_keyword_materials: kw,
    hash_material_hint: hashMat,
    el_upload_count: document.querySelectorAll('.el-upload').length,
    snippet: t.replace(/\s+/g,' ').trim().slice(0, 700)
  };
})()"""


def guide_base_href() -> str:
    return f"{NAME_REG}#/guide/base?busiType={BUSI}&entType={ENT}&marPrId=&marUniscId="


def _cdp_port() -> int:
    with (ROOT / "config" / "browser.json").open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def materials_first_screen_ok(p: Any) -> bool:
    if not isinstance(p, dict):
        return False
    if int(p.get("visible_file_inputs") or 0) >= 1:
        return True
    if int(p.get("total_file_inputs") or 0) >= 1 and (
        bool(p.get("body_keyword_materials")) or bool(p.get("hash_material_hint"))
    ):
        return True
    if bool(p.get("body_keyword_materials")) and int(p.get("el_upload_count") or 0) >= 1:
        return True
    return False


def build_acceptance(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    ph = rec.get("phases") or {}
    a = ph.get("A_guide_to_core") or {}
    b = ph.get("B_core_to_materials_probe") or {}
    ac: List[Dict[str, Any]] = []
    ac.append(
        {
            "id": "AC-L1-SCOPE",
            "ok": rec.get("busi_type") == BUSI and rec.get("ent_type") == ENT,
            "note": f"固定验收范围 busiType={BUSI} entType={ENT}",
        }
    )
    ac.append(
        {
            "id": "AC-L1-GUIDE",
            "ok": bool(a.get("reached_guide_base")),
            "note": "曾进入或目标为 name-register #/guide/base",
            "detail": {"nav": a.get("nav")},
        }
    )
    ac.append(
        {
            "id": "AC-L1-CORE",
            "ok": bool(a.get("reached_core")),
            "note": "已进入 core.html（设立主流程 SPA）",
            "detail": {"last_href": a.get("last_href_after_A")},
        }
    )
    ac.append(
        {
            "id": "AC-L1-MATERIALS-FIRST",
            "ok": bool(b.get("materials_first_ok")),
            "note": "材料相关第一屏：可见 file 或（材料类文案/hash 提示 + file/upload 证据）",
            "detail": b.get("final_materials_probe"),
        }
    )
    ac.append(
        {
            "id": "AC-L1-NO-YUN-AUTO",
            "ok": not rec.get("yun_submit_clicked"),
            "note": "脚本未自动点击云提交（停点仅探测）",
        }
    )
    return ac


def _main() -> int:
    ap = argparse.ArgumentParser(description="验收线 L1：02_4+1100 guide→core→材料第一屏")
    ap.add_argument("--guide-rounds", type=int, default=18, help="guide/base 阶段最大轮次")
    ap.add_argument("--core-advance-rounds", type=int, default=16, help="进入 core 后点主按钮推进的最大轮次")
    ap.add_argument("--no-nav", action="store_true", help="不跳转到 guide/base（从当前页开始跑）")
    ap.add_argument("--human-fast", action="store_true")
    ap.add_argument("-o", "--output", type=Path, default=OUT)
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=args.human_fast)

    rec: Dict[str, Any] = {
        "acceptance_line_schema": "ufo.acceptance_line_02_4_1100.v1",
        "run_id": new_run_id(),
        "busi_type": BUSI,
        "ent_type": ENT,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "yun_submit_clicked": False,
        "phases": {
            "A_guide_to_core": {"rounds": [], "reached_guide_base": False, "reached_core": False},
            "B_core_to_materials_probe": {"rounds": [], "materials_first_ok": False},
        },
    }

    nav = ensure_icpsp_entry(_cdp_port(), busi_type=BUSI, navigate_policy="host_only", wait_after_nav_sec=2.5)
    rec["ensure_icpsp_entry"] = nav
    ws_url = nav.get("ws_url")
    if not ws_url:
        rec["error"] = "no_ws"
        rec["acceptance"] = build_acceptance(rec)
        rec["verdict"] = "failed_prereq"
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    cdp: Optional[CDP] = None
    try:
        cdp = CDP(ws_url)
        target = guide_base_href()
        href0 = str(cdp.ev(r"(function(){return location.href;})()") or "")
        rec["phases"]["A_guide_to_core"]["href_start"] = href0
        if not args.no_nav:
            cdp.ev(f"location.href = {json.dumps(target, ensure_ascii=False)}")
            sleep_human(3.8)
            rec["phases"]["A_guide_to_core"]["reached_guide_base"] = True
            rec["phases"]["A_guide_to_core"]["nav"] = {"target": target, "href_after": cdp.ev(r"(function(){return location.href;})()")}
        else:
            rec["phases"]["A_guide_to_core"]["reached_guide_base"] = bool("guide/base" in href0)

        # ----- Phase A -----
        for i in range(max(1, args.guide_rounds)):
            yun = cdp.ev(YUN_SUBMIT_PROBE)
            if isinstance(yun, dict) and yun.get("hasYunSubmit"):
                rec["phases"]["A_guide_to_core"]["yun_during_A"] = True
                rec["phases"]["A_guide_to_core"]["stopped_at_yun_boundary"] = True
                rec["phases"]["A_guide_to_core"]["rounds"].append({"i": i, "stop": "yun_submit_text_in_name_flow", "yun": yun})
                break
            href = str((yun or {}).get("href") or "") if isinstance(yun, dict) else ""
            if "core.html" in href:
                rec["phases"]["A_guide_to_core"]["reached_core"] = True
                rec["phases"]["A_guide_to_core"]["last_href_after_A"] = href
                rec["phases"]["A_guide_to_core"]["rounds"].append({"i": i, "note": "reached_core", "yun": yun})
                break
            ui = cdp.ev(READ_BLOCKER_UI_JS)
            gfill = cdp.ev(GUIDE_BASE_AUTOFILL_V2)
            sleep_human(1.0)
            clk = cdp.ev(CLICK_FIRST_PRIMARY)
            sleep_human(2.0)
            rec["phases"]["A_guide_to_core"]["rounds"].append(
                {"i": i, "yun": yun, "ui_errors": (ui or {}).get("errors") if isinstance(ui, dict) else None, "click": clk, "autofill": (gfill or {}).get("log") if isinstance(gfill, dict) else None}
            )
            sleep_human(0.85)

        # ----- Phase B -----
        if rec["phases"]["A_guide_to_core"].get("reached_core"):
            last_hash = ""
            same_hash = 0
            for j in range(max(1, args.core_advance_rounds)):
                yun = cdp.ev(YUN_SUBMIT_PROBE)
                mat = cdp.ev(MATERIALS_FIRST_PROBE_JS)
                files_ctx = cdp.ev(PROBE_FILE_CONTEXT_JS)
                if isinstance(yun, dict) and yun.get("hasYunSubmit"):
                    rec["phases"]["B_core_to_materials_probe"]["yun_during_B"] = True
                    rec["phases"]["B_core_to_materials_probe"]["stopped_at_yun_expected"] = True
                    rec["phases"]["B_core_to_materials_probe"]["rounds"].append({"j": j, "stop": "yun_submit_visible", "yun": yun, "materials": mat})
                    break
                ok = materials_first_screen_ok(mat)
                rec["phases"]["B_core_to_materials_probe"]["rounds"].append({"j": j, "materials": mat, "file_context": files_ctx, "materials_first_ok": ok})
                if ok:
                    rec["phases"]["B_core_to_materials_probe"]["materials_first_ok"] = True
                    rec["phases"]["B_core_to_materials_probe"]["final_materials_probe"] = mat
                    break
                hnow = str((mat or {}).get("hash") or "") if isinstance(mat, dict) else ""
                if hnow and hnow == last_hash:
                    same_hash += 1
                else:
                    same_hash = 0
                    last_hash = hnow
                if same_hash >= 4:
                    rec["phases"]["B_core_to_materials_probe"]["stop"] = "hash_stagnate"
                    break
                cdp.ev(GUIDE_BASE_AUTOFILL_V2)
                sleep_human(0.9)
                cdp.ev(CLICK_FIRST_PRIMARY)
                sleep_human(2.1)
        else:
            rec["phases"]["B_core_to_materials_probe"]["skipped"] = "core_not_reached"

        rec["acceptance"] = build_acceptance(rec)
        strict = all(
            x.get("ok")
            for x in rec["acceptance"]
            if x.get("id")
            in (
                "AC-L1-SCOPE",
                "AC-L1-GUIDE",
                "AC-L1-CORE",
                "AC-L1-MATERIALS-FIRST",
                "AC-L1-NO-YUN-AUTO",
            )
        )
        rec["verdict"] = "pass" if strict else ("partial" if rec["phases"]["A_guide_to_core"].get("reached_core") else "fail")
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {args.output} verdict={rec.get('verdict')}")
    return 0 if rec.get("verdict") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(_main())
