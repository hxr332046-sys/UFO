"""把 system/phase1_protocol_driver.run 封装成可复用函数，供 API 调用。

关键点：
- driver 原本只能从 case.json 启动；这里支持传入 dict。
- 返回结构化结果（busiId / hit_count / steps），不是日志文本。
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system"))

# 延迟导入：避免 import 期就连远程
def _load_driver():
    from phase1_protocol_driver import (  # type: ignore
        DriverContext,
        step_check_establish_name,
        step_load_current_location,
        step_namecheck_load,
        step_banned_lexicon,
        step_nc_op_first_save,
        step_namecheck_repeat,
        step_nc_op_second_save,
    )
    from icpsp_api_client import ICPSPClient  # type: ignore
    return locals()


def _to_step_report(sr) -> Dict[str, Any]:
    return {
        "name": sr.name,
        "ok": sr.ok,
        "code": sr.code or "",
        "result_type": sr.result_type or "",
        "msg": sr.reason or "",
        "extracted": sr.extracted or {},
    }


async def drive_phase1(case_dict: Dict[str, Any]) -> Dict[str, Any]:
    """同步逻辑包在线程里，不阻塞 event loop。"""
    return await asyncio.get_event_loop().run_in_executor(None, _sync_drive, case_dict)


def _sync_drive(case_dict: Dict[str, Any]) -> Dict[str, Any]:
    started = time.time()
    driver = _load_driver()
    DriverContext = driver["DriverContext"]
    ICPSPClient = driver["ICPSPClient"]

    c = DriverContext.from_case(case_dict)
    client = ICPSPClient()

    steps_meta: list = []
    result = {
        "success": False,
        "busiId": None,
        "hit_count": None,
        "checkState": None,
        "similar_names": [],
        "steps": steps_meta,
        "latency_ms": 0,
        "reason": None,
    }

    try:
        # step 1
        sr, _ = driver["step_check_establish_name"](client, c)
        steps_meta.append(_to_step_report(sr))
        if not sr.ok:
            result["reason"] = f"step1_failed: {sr.reason}"
            return result
        time.sleep(0.9)

        # step 2
        sr, _ = driver["step_load_current_location"](client, c)
        steps_meta.append(_to_step_report(sr))
        if not sr.ok:
            result["reason"] = f"step2_failed: {sr.reason}"
            return result
        time.sleep(0.9)

        # step 3
        sr, _ = driver["step_namecheck_load"](client, c)
        steps_meta.append(_to_step_report(sr))
        if not sr.ok:
            result["reason"] = f"step3_failed: {sr.reason}"
            return result
        time.sleep(0.9)

        # step 4
        sr, _ = driver["step_banned_lexicon"](client, c)
        steps_meta.append(_to_step_report(sr))
        if not sr.ok:
            result["reason"] = f"step4_failed: {sr.reason}"
            return result
        time.sleep(0.9)

        # step 5
        sr, resp5 = driver["step_nc_op_first_save"](client, c)
        rpt5 = _to_step_report(sr)
        # 捕获服务端 msg（禁限用词警告等，即使 code=00000）
        if resp5:
            d5 = (resp5.get("data") or {})
            server_msg5 = d5.get("msg") or ""
            if server_msg5:
                rpt5["server_msg"] = server_msg5
        steps_meta.append(rpt5)
        if not sr.ok:
            result["reason"] = f"step5_failed: {sr.reason}"
            return result
        time.sleep(0.9)

        # step 6
        sr, resp6 = driver["step_namecheck_repeat"](client, c)
        steps_meta.append(_to_step_report(sr))
        if not sr.ok:
            result["reason"] = f"step6_failed: {sr.reason}"
            return result
        # 从 step 6 响应提取 similar_names
        if resp6:
            try:
                dto = (resp6.get("data") or {}).get("busiData") or {}
                sims = dto.get("checkResult") or []
                if isinstance(sims, list):
                    result["similar_names"] = [
                        {"name": s.get("entName") or s.get("name"), "regNo": s.get("regNo")} for s in sims[:20]
                    ]
            except Exception:
                pass
        result["hit_count"] = sr.extracted.get("hit_count")
        result["checkState"] = sr.extracted.get("checkState_reported")
        time.sleep(0.9)

        # step 7
        sr, resp7 = driver["step_nc_op_second_save"](client, c)
        rpt7 = _to_step_report(sr)
        if resp7:
            d7 = (resp7.get("data") or {})
            server_msg7 = d7.get("msg") or ""
            if server_msg7:
                rpt7["server_msg"] = server_msg7
        steps_meta.append(rpt7)
        if not sr.ok:
            result["reason"] = f"step7_failed: {sr.reason}"
            return result

        # 从 step5/step7 提取 resultType 和 msg
        step5_report = steps_meta[4] if len(steps_meta) > 4 else {}
        step7_report = steps_meta[6] if len(steps_meta) > 6 else {}
        rt5 = step5_report.get("result_type", "")
        rt7 = step7_report.get("result_type", "")
        result["step5_result_type"] = rt5
        result["step7_result_type"] = rt7

        if c.busi_id:
            result["busiId"] = c.busi_id
            result["success"] = True
        else:
            # 分析 no-busiId 的具体原因
            if rt5 == "1" or rt7 == "1":
                result["reason"] = "name_prohibited"
                result["reason_detail"] = "名称含有禁止使用的内容（resultType=1）"
            elif rt5 == "2" and rt7 != "0":
                result["reason"] = "name_restricted"
                result["reason_detail"] = "名称含有限制使用的内容（resultType=2）且未通过二次确认"
            else:
                result["reason"] = "step7_no_busi_id"
    finally:
        result["latency_ms"] = int((time.time() - started) * 1000)
    return result
