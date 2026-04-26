#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按 docs/case_广西容县李陈梦.json + config/rehearsal_assets_rongxian.json
跑 packet_chain 主链至「云提交」文案停点（不点云提交），并合并案例元数据到输出 JSON。

前置：本机 Chrome Dev 已开、已登录 9087（办件中心）；资料中的证件/合同路径须存在。

用法（政务平台根目录）:
  .\\.venv-portal\\Scripts\\python.exe system\\run_case_rongxian_to_yun_submit.py
  .\\.venv-portal\\Scripts\\python.exe system\\run_case_rongxian_to_yun_submit.py --human-fast
  .\\.venv-portal\\Scripts\\python.exe system\\run_case_rongxian_to_yun_submit.py --resume-current
  # 资料为「新设主体」示例：默认不要求「我的办件」里已出现该企业名（从头核名前列表里没有是常态）。
  # 仅当你要强制校验列表正文是否含全称时，再加：--enforce-listing-match
#
# 进程退出码（勿只看「脚本跑完」）:
#   0 — 第二阶段达成：phase_verdict.phase2_to_yun_submit_stop.status == pass（页面出现云提交文案停点）
#   3 — phase_verdict 第一阶段为 fail（含启用列表门禁且未命中时）
#   4 — 未达第二阶段停点，或第一阶段为 unknown（新设从头常见）
#   2 — 前置错误（缺 case 文件等）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

CASE_JSON_DEFAULT = ROOT / "docs" / "case_有为风.json"
ASSETS_JSON = ROOT / "config" / "rehearsal_assets_rongxian.json"
OUT_JSON = ROOT / "dashboard" / "data" / "records" / "case_run_rongxian_latest.json"


def _preflight(case: Dict[str, Any]) -> Dict[str, Any]:
    assets = case.get("assets") or {}
    out: Dict[str, Any] = {}
    for k, p in assets.items():
        fp = Path(str(p))
        out[k] = {"path": str(p), "exists": fp.is_file()}
    raw_a = json.loads(ASSETS_JSON.read_text(encoding="utf-8"))
    if raw_a.get("lease_contract"):
        lp = Path(str(raw_a["lease_contract"]))
        out["lease_contract"] = {"path": str(lp), "exists": lp.is_file(), "source": "rehearsal_assets_rongxian.json"}
    exists_vals = [v.get("exists") for v in out.values() if isinstance(v, dict) and "exists" in v]
    return {"asset_files": out, "all_exist": bool(exists_vals) and all(exists_vals)}


def _status_cn(status: Optional[str]) -> str:
    return {"pass": "通过", "fail": "未通过", "unknown": "未判定/需人工"}.get(str(status or ""), str(status))


def _print_business_verdict(
    data: Dict[str, Any], case: Dict[str, Any], *, enforce_listing_match: bool
) -> Tuple[int, Dict[str, Any]]:
    """根据 phase_verdict 打印终端结论并返回 (exit_code, runner_extra)。"""
    pv = data.get("phase_verdict")
    company = case.get("company_name_full") or ""
    if not isinstance(pv, dict):
        print("")
        print("=== 业务结论（必读）===")
        print("  WARN: 输出 JSON 中无 phase_verdict（可能为旧版 packet_chain）。无法自动判定两阶段成败，请人工看 steps 与截图。")
        print("=======================")
        return 4, {"business_exit_code": 4, "business_reason": "no_phase_verdict_in_output"}

    p1 = (pv.get("phase1_name_then_case_row") or {}).get("status")
    p2 = (pv.get("phase2_to_yun_submit_stop") or {}).get("status")

    if data.get("phase1_only") or pv.get("run_mode") == "phase1_only":
        print("")
        print("=== 业务结论（第一阶段专用模式）===")
        print(f"  案例拟设企业名称: {company}")
        print("  本脚本**只做到名称登记入口/当前页快照**，未执行「直至云提交」主循环。")
        print("  请在浏览器内**人工完成**名称申报/核名及系统提示的材料；完成后第二阶段执行：")
        print("    python system\\run_case_rongxian_to_yun_submit.py --resume-current")
        print("  详情: phase_verdict.run_mode、steps.phase1_only_stop")
        print("=======================")
        return 0, {"business_exit_code": 0, "business_reason": "phase1_only_mode_completed"}

    print("")
    print("=== 业务结论（必读）===")
    print(f"  案例拟设企业名称（资料）: {company}")
    print(f"  第一阶段 phase_verdict: {_status_cn(str(p1) if p1 else None)}")
    print(f"  第二阶段（至云提交文案停点）: {_status_cn(str(p2) if p2 else None)}")
    if enforce_listing_match:
        print("  说明: 已启用 --enforce-listing-match — 仅在「我的办件」列表页且正文含上述全称时，列表门禁记为通过。")
    else:
        print(
            "  说明: **默认不要求**列表里已出现该企业名。资料用于**新设主体从头跑**；核名前/未生成办件时列表里没有该行是**正常现象**，勿与「任务失败」划等号。"
        )
    if p1 == "fail":
        if enforce_listing_match:
            print("  【结论】列表门禁未通过（正文不含案例全称），本 run 已中止。")
        else:
            print("  【结论】phase_verdict 第一阶段为 fail：请读 JSON 内 phase_verdict.phase1…detail（含是否曾启用列表门禁等）。")
    elif p1 == "unknown":
        print("  【提示】第一阶段为「未判定」：请结合名称登记/核名页面与系统提示判断；新设时以**核名通过与系统生成办件**为准，不单看列表。")
    if p2 != "pass":
        print("  【结论】未到达云提交文案停点；自动化任务未完成。")
    else:
        print("  【结论】已探测到云提交相关停点（未自动点击提交）。")
    print("  详情: 见 JSON 字段 phase_verdict、acceptance")
    print("=======================")

    if p2 == "pass":
        return 0, {"business_exit_code": 0, "business_reason": "phase2_yun_submit_ok"}
    if p1 == "fail":
        return 3, {"business_exit_code": 3, "business_reason": "phase1_not_satisfied"}
    return 4, {"business_exit_code": 4, "business_reason": "phase2_incomplete_or_phase1_unknown"}


def _build_guide_seed(case: Dict[str, Any]) -> Dict[str, Any]:
    dist_codes_raw = case.get("phase1_dist_codes") or []
    dist_codes = [str(x).strip() for x in dist_codes_raw if str(x).strip()]
    dist_code = dist_codes[-1] if dist_codes else ""
    region_text = str(case.get("region_text") or "").strip()
    address_full = str(case.get("address_full") or "").strip()
    district_name = region_text.replace("广西壮族自治区", "").replace("广西", "").strip()
    detail = address_full
    for prefix in ("广西壮族自治区", "广西", "玉林市", district_name):
        if prefix and detail.startswith(prefix):
            detail = detail[len(prefix) :].strip()
    if district_name and detail.startswith(district_name):
        detail = detail[len(district_name) :].strip()
    if not detail:
        detail = address_full
    path_texts = []
    if dist_codes:
        path_texts.append("广西壮族自治区")
    if len(dist_codes) >= 2:
        path_texts.append("玉林市")
    if len(dist_codes) >= 3:
        path_texts.append(district_name or dist_code)
    while len(path_texts) < len(dist_codes):
        path_texts.append(dist_codes[len(path_texts)])
    address_value = district_name or region_text or address_full
    return {
        "distCode": dist_code,
        "streetCode": dist_code,
        "streetName": address_value,
        "address": address_value,
        "detAddress": detail,
        "nameCode": "0",
        "isnameType": "0",
        "formChoiceName": "0",
        "havaAdress": "0",
        "distCodePath": dist_codes,
        "distPathTexts": path_texts,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=Path, default=CASE_JSON_DEFAULT, help="案例 JSON 路径")
    ap.add_argument("--human-fast", action="store_true", help="关闭类人节奏（仅调试用）")
    ap.add_argument("--resume-current", action="store_true", help="不从门户重跑，从当前 9087 页续跑")
    ap.add_argument(
        "--enforce-listing-match",
        action="store_true",
        help="可选：在「我的办件」列表页强制校验页面正文是否含案例 company_name_full（缺则立即中止）；新设从头默认不要开",
    )
    ap.add_argument(
        "--phase1-only",
        action="store_true",
        help="仅第一阶段：门户导航至名称登记子应用并快照后停止，不跑直至云提交的主循环；核名须人工在浏览器完成，再跑本脚本第二阶段（不带本参数）",
    )
    ap.add_argument("-o", "--output", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    CASE_JSON = args.case
    if not CASE_JSON.is_file():
        print("ERROR: missing", CASE_JSON)
        return 2
    case = json.loads(CASE_JSON.read_text(encoding="utf-8"))
    pre = _preflight(case)
    print("=== 案例 ===", case.get("company_name_full"))
    print("=== 附件路径检查 ===", json.dumps(pre, ensure_ascii=False, indent=2))
    if not pre.get("all_exist"):
        print("WARN: 部分文件不存在，上传步骤可能失败；仍继续跑导航与提示收集。")

    from packet_chain_portal_from_start import run as packet_run

    gate_substr: Optional[str] = None
    if args.enforce_listing_match:
        gate_substr = (case.get("company_name_full") or "").strip() or None
    guide_seed = _build_guide_seed(case)

    t0 = time.time()
    packet_run(
        entry="namenotice",
        out_path=args.output,
        also_write_iter_latest=True,
        framework_md_path=ROOT / "dashboard" / "data" / "records" / "case_run_rongxian_rehearsal.md",
        resume_current=bool(args.resume_current),
        human_fast=bool(args.human_fast),
        assets_path=ASSETS_JSON if ASSETS_JSON.is_file() else None,
        require_listing_company_substr=gate_substr,
        phase1_only=bool(args.phase1_only),
        guide_seed=guide_seed,
    )

    exit_code = 4
    if args.output.is_file():
        data = json.loads(args.output.read_text(encoding="utf-8"))
        data["case_profile"] = case
        data["preflight"] = pre
        ec, extra = _print_business_verdict(data, case, enforce_listing_match=bool(args.enforce_listing_match))
        exit_code = ec
        data["runner"] = {
            "script": "system/run_case_rongxian_to_yun_submit.py",
            "elapsed_sec": round(time.time() - t0, 2),
            "note": "业务验收：见 phase_verdict；资料为拟设新设示例时默认不强制「列表已有该企业名」；云提交停点见 steps；未自动点击云提交",
            "enforce_listing_match": bool(args.enforce_listing_match),
            "phase1_only": bool(args.phase1_only),
            **extra,
        }
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Merged case_profile into {args.output}")
        print(f"进程退出码: {exit_code}（0=第二阶段停点达成，3=第一阶段明确未过，4=未完成或需人工）")
    else:
        print("ERROR: 未生成输出 JSON", args.output)
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
