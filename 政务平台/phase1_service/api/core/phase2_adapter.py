"""把 system/phase2_protocol_driver.run 封装成可复用函数，供 API 调用。

设计约束：
- 不改 system/phase2_protocol_driver.py（driver 保持纯协议、可独立跑）
- Step 列表**统一从 driver.get_steps_spec() 读**，这里不再维护第二份（SSOT）
- 默认 stop_after=14（BasicInfo load 成功），step 15 save 存在 A0002 问题，不纳入默认链路
- 返回结构化结果（busiId / nameId / establish_busiId / basicinfo_signInfo / steps），不是日志文本
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system"))


def _load_driver() -> Dict[str, Any]:
    """延迟导入 driver，保证 FastAPI 启动时不连远程。

    只 import 基础设施（Context / 错误码 / ICPSPClient / 元数据）；
    step 函数列表由 driver.get_steps_spec() 统一导出。
    """
    from phase2_protocol_driver import (  # type: ignore
        Phase2Context,
        extract_phase1_busi_id,
        get_steps_spec,
        SESSION_GATE_CODE,
        PRIVILEGE_CODE,
        RATE_LIMIT_CODE,
    )
    from icpsp_api_client import ICPSPClient  # type: ignore
    return locals()


def _get_steps_spec(drv: Dict[str, Any], ent_type: str | None = None) -> List[tuple]:
    """直接透传 driver 的 SSOT — 不再有重复定义。

    ent_type: "1151" 返回 28 步有限公司链；其他/None 返回 25 步个人独资链。
    """
    return drv["get_steps_spec"](ent_type=ent_type)


def _decode(res: Dict[str, Any]) -> Dict[str, Any]:
    code = str(res.get("code") or "")
    data = res.get("data") or {}
    rt = str(data.get("resultType") or "")
    msg = str(data.get("msg") or res.get("msg") or "")
    busi = data.get("busiData") or {}
    return {"code": code, "resultType": rt, "msg": msg, "busiData": busi}


async def drive_phase2(
    case_dict: Dict[str, Any],
    busi_id: str,
    *,
    stop_after: int = 14,
    start_from: int = 1,
    preset_name_id: Optional[str] = None,
    step_delay_sec: float = 1.8,
    write_delay_sec: float = 4.5,
) -> Dict[str, Any]:
    """异步入口：sync 逻辑包在 thread executor 里，不阻塞 event loop。"""
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _sync_drive,
        case_dict, busi_id, stop_after, start_from, preset_name_id, step_delay_sec, write_delay_sec,
    )


def _sync_drive(
    case_dict: Dict[str, Any],
    busi_id: str,
    stop_after: int,
    start_from: int,
    preset_name_id: Optional[str],
    step_delay_sec: float,
    write_delay_sec: float,
) -> Dict[str, Any]:
    started = time.time()
    drv = _load_driver()
    Phase2Context = drv["Phase2Context"]
    ICPSPClient = drv["ICPSPClient"]
    SESSION_GATE = drv["SESSION_GATE_CODE"]
    RATE_LIMIT = drv["RATE_LIMIT_CODE"]

    c = Phase2Context.from_case(case_dict, busi_id)
    if preset_name_id:
        c.name_id = preset_name_id
    client = ICPSPClient()

    steps_spec = _get_steps_spec(drv, ent_type=str(case_dict.get("entType_default") or "4540"))
    steps_out: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {
        "success": False,
        "busiId": busi_id,
        "nameId": preset_name_id,
        "establish_busiId": None,
        "basicinfo_signInfo": None,
        "stopped_at_step": 0,
        "steps": steps_out,
        "latency_ms": 0,
        "reason": None,
        "reason_detail": None,
    }

    # ★ establish 热身：断点续跑 establish 步骤（>=12）时，
    #   必须先跑 step12 (establish/loadCurrentLocationInfo) 建立会话绑定，
    #   否则服务端返回 D0018/D0019。
    if start_from > 12:
        warmup_step = next((s for s in steps_spec if s[0] == 12), None)
        if warmup_step:
            _, wn, wf, _ = warmup_step
            try:
                wres = wf(client, c)
                wdec = _decode(wres)
                print(f"    [warmup] step12 {wn}: code={wdec['code']}")
                time.sleep(step_delay_sec)
            except Exception as e:
                print(f"    [warmup] step12 failed: {e}")

    exit_reason = None
    for i, name, fn, optional in steps_spec:
        if i < start_from:
            continue
        if i > stop_after:
            break
        t0 = time.time()
        try:
            res = fn(client, c)
            dec = _decode(res)
            dt = int((time.time() - t0) * 1000)
            rec = {
                "i": i,
                "name": name,
                "ok": dec["code"] == "00000",
                "code": dec["code"],
                "resultType": dec["resultType"],
                "msg": dec["msg"],
                "duration_ms": dt,
                "busiData_preview": json.dumps(dec["busiData"], ensure_ascii=False)[:400],
            }
            steps_out.append(rec)
            # 致命错误处理
            if dec["code"] == SESSION_GATE:
                exit_reason = ("session_expired", "Authorization 已失效，请重新登录")
                break
            if dec["code"] == RATE_LIMIT:
                exit_reason = ("rate_limit", "D0029 操作频繁，请稍后重试")
                break
            if dec["code"] != "00000":
                if optional:
                    # optional step 失败不中断，继续下一步
                    pass
                else:
                    exit_reason = (f"step{i}_failed", f"{name}: code={dec['code']} msg={dec['msg']}")
                    break
            if dec["resultType"] == "-1":
                exit_reason = (f"step{i}_resultType_-1", f"{name}: resultType=-1 msg={dec['msg']}")
                break
            # 写操作后更长冷却
            if "operationBusinessDataInfo" in name or "submit" in name or "operate" in name:
                time.sleep(write_delay_sec)
            else:
                time.sleep(step_delay_sec)
        except Exception as e:
            dt = int((time.time() - t0) * 1000)
            steps_out.append({"i": i, "name": name, "ok": False, "err": str(e), "duration_ms": dt})
            exit_reason = (f"step{i}_exception", str(e))
            break

    # 捕获 driver 里 snapshot/context 的关键值
    try:
        if c.name_id:
            result["nameId"] = str(c.name_id)
        if c.snapshot.get("establish_busiId"):
            result["establish_busiId"] = str(c.snapshot["establish_busiId"])
        if c.snapshot.get("basicinfo_signInfo"):
            result["basicinfo_signInfo"] = str(c.snapshot["basicinfo_signInfo"])
    except Exception:
        pass

    result["stopped_at_step"] = steps_out[-1]["i"] if steps_out else 0
    if exit_reason:
        result["reason"] = exit_reason[0]
        result["reason_detail"] = exit_reason[1]
    else:
        # 默认判定：到达 stop_after 且最后一步 ok 就算成功
        last = steps_out[-1] if steps_out else None
        if last and last.get("ok") and last["i"] >= stop_after:
            result["success"] = True
    result["latency_ms"] = int((time.time() - started) * 1000)
    return result
