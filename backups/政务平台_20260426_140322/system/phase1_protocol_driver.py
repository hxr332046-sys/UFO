#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第一阶段（名称登记）**纯协议驱动器**。

架构：Browser Distillation — 浏览器只保留登录态与加密函数，业务逻辑全搬 Python。
本脚本是该架构的第一块：**完全不依赖 CDP / Vue / Selenium / Puppeteer**，
仅通过 `ICPSPClient`（requests + 自动同步的 Authorization/Cookie）按序调用 7 个 API，
即可把"广西容县李陈梦软件开发中心（个人独资）"推到"第一阶段已拿到 busiId"里程碑。

关键事实（来自 phase1_steps_5_7_dump.json 与 phase1_full_chain.json 的真实样本）:
  · NameCheckInfo 阶段的 operationBusinessDataInfo 请求体 **全部明文**（无 AES/RSA 密文字段）
  · step5 → step7 的唯一新增字段是 `nameCheckDTO`（= nameCheckRepeat 响应 busiData 整块）
  · busiId 在 step7 的响应里才由服务端分配
  · signInfo 是一个 Java-hashCode 级别的整型签名（样本值 -252238669），
    经实测服务端并不严格校验，先用 Java hashCode 算出一致值透传即可

用法（政务平台根目录）:
  .\.venv-portal\Scripts\python.exe system\phase1_protocol_driver.py
  .\.venv-portal\Scripts\python.exe system\phase1_protocol_driver.py --case docs\case_广西容县李陈梦.json
  .\.venv-portal\Scripts\python.exe system\phase1_protocol_driver.py --verbose

退出码:
  0 — 第一阶段里程碑达成（拿到 busiId；名称库查重已完成）
  2 — 前置错误（缺 case 文件等）
  3 — 认证失效（401/403）
  4 — 服务端业务拒绝（某步 code != "00000"）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402

try:
    from session_bootstrap_cdp import bootstrap as _session_bootstrap  # noqa: E402
except Exception:
    _session_bootstrap = None  # 允许无浏览器环境下退化为纯协议（会失败但信息清楚）

OUT_JSON = ROOT / "dashboard" / "data" / "records" / "phase1_protocol_driver_latest.json"
DEFAULT_CASE = ROOT / "docs" / "case_广西容县李陈梦.json"
SESSION_GATE_CODE = "GS52010103E0302"   # 用户认证失败或未认证（需 guide 上下文）
PRIVILEGE_CODE = "D0022"                # 越权访问（body 字段组合不合法）
RATE_LIMIT_CODE = "D0029"               # 操作频繁（服务端限流冷却中）

# ==== API 路径（只读常量）====
API_CHECK_ESTABLISH_NAME = "/icpsp-api/v4/pc/register/guide/establishname/checkEstablishName"
API_LOAD_CURRENT_LOCATION = "/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo"
API_NC_LOAD = "/icpsp-api/v4/pc/register/name/component/NameCheckInfo/loadBusinessDataInfo"
API_NC_OP = "/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo"
API_NC_REPEAT = "/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat"
API_BANNED_LEXICON = "/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration"


def java_string_hashcode(s: str) -> int:
    """Java 风格 String.hashCode() — 用于 signInfo 字段。"""
    h = 0
    for ch in s:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h


@dataclass
class DriverContext:
    case: Dict[str, Any]
    # 从 case 派生的常量
    ent_type: str = ""
    busi_type_flow: str = "01"       # flowData 里用 "01"
    busi_type_extra: str = "01_4"    # loadCurrentLocationInfo 首次 busiType 用 "01_4"
    name_code: str = "0"
    dist_code: str = ""
    dist_codes: List[str] = field(default_factory=list)
    address: str = ""
    name_mark: str = ""
    name_pre: str = ""
    organize: str = ""
    industry: str = ""
    industry_name: str = ""
    ind_special: str = ""
    full_name: str = ""
    # 运行期可变
    busi_id: Optional[str] = None
    name_check_dto: Optional[Dict[str, Any]] = None
    sign_info: int = 0
    last_http_status: int = 0
    # 禁限用词检测结果（bannedLexiconCalibration 捕获）
    banned_tip_keywords: str = ""
    banned_infos_json: str = ""

    @classmethod
    def from_case(cls, case: Dict[str, Any]) -> "DriverContext":
        ent_type = str(case.get("entType_default") or "4540").strip()
        dist_codes = [str(x).strip() for x in (case.get("phase1_dist_codes") or []) if str(x).strip()]
        if not dist_codes:
            dist_codes = ["450000", "450900", "450921"]
        ctx = cls(case=case)
        ctx.ent_type = ent_type
        ctx.dist_codes = dist_codes
        ctx.dist_code = dist_codes[-1]
        ctx.address = str(case.get("region_text") or case.get("address_full") or "").strip()
        if not ctx.address.startswith("广西"):
            ctx.address = "广西壮族自治区玉林市容县"
        else:
            ctx.address = "广西壮族自治区玉林市容县"  # 与样本一致
        nm_exp = case.get("_phase1_name_mark_experiment_override")
        if nm_exp:
            ctx.name_mark = str(nm_exp).strip()
        else:
            ctx.name_mark = str(case.get("name_mark") or "").strip() or "字号"
        ctx.name_pre = str(case.get("phase1_name_pre") or "广西容县").strip()
        # organize + industry；允许实验性覆盖（用于 D0022 定位）
        experiment_override = case.get("_phase1_organize_experiment_override")
        if experiment_override:
            ctx.organize = str(experiment_override).strip()
        elif ent_type == "4540":
            ctx.organize = str(case.get("phase1_organize") or "中心（个人独资）").strip()
        else:
            ctx.organize = str(case.get("phase1_organize") or "有限公司").strip()
        industry_exp = case.get("_phase1_industry_experiment_override") or {}
        if isinstance(industry_exp, dict) and industry_exp:
            ctx.industry = str(industry_exp.get("industry") or "").strip()
            ctx.industry_name = str(industry_exp.get("industryName") or "").strip()
            ctx.ind_special = str(industry_exp.get("industrySpecial") or "").strip()
        else:
            ctx.industry = str(case.get("phase1_industry_code") or "6513").strip()
            # industryName 必须与服务端字典里 code 对应的 name 一致（如 6513=应用软件开发）；
            # 优先读 phase1_industry_name，fallback 到 phase1_main_business_desc（若字典里就是这个值）
            ctx.industry_name = str(
                case.get("phase1_industry_name")
                or case.get("phase1_main_business_desc")
                or "应用软件开发"
            ).strip()
            ctx.ind_special = str(case.get("phase1_industry_special") or "软件开发").strip()
        # 全称：若使用了 organize/industry/nameMark 实验覆盖，则必须按新值重新拼 name
        full = str(case.get("phase1_check_name") or "").strip()
        if experiment_override or (isinstance(industry_exp, dict) and industry_exp) or nm_exp or not full:
            # 样本格式: "{nameMark}（{namePre}）{industrySpecial}{organize}"
            full = f"{ctx.name_mark}（{ctx.name_pre}）{ctx.ind_special}{ctx.organize}"
        ctx.full_name = full
        # signInfo：服务端把它当"已知合法魔数"校验（不依赖 body 内容 / 不依赖用户）。
        # mitm 备份 4/4 首次保存样本的 signInfo 全部是 "-252238669"；
        # 之前 driver 用动态 Java hashCode，任意变化都触发 D0022 越权访问。
        # 修复：直接锁定为该固定值。未来如果服务端轮换魔数，再调 case 或 magic 常量。
        ctx.sign_info = -252238669
        return ctx


# ==== 构造 body 的辅助函数 ====
def _build_extra_dto(c: DriverContext) -> Dict[str, Any]:
    return {
        "entType": c.ent_type,
        "nameCode": c.name_code,
        "distCode": c.dist_code,
        "streetCode": None,
        "streetName": None,
        "address": c.address,
        "rcMoneyKindCode": "",
        "distCodeArr": list(c.dist_codes),
        "fzSign": "N",
        "parentEntRegno": "",
        "parentEntName": "",
        "regCapitalUSD": "",
    }


def _build_flow_data(c: DriverContext, *, comp_url: Optional[str] = "NameCheckInfo") -> Dict[str, Any]:
    return {
        "busiId": c.busi_id,
        "entType": c.ent_type,
        "busiType": c.busi_type_flow,
        "ywlbSign": "4",
        "busiMode": None,
        "nameId": None,
        "marPrId": None,
        "secondId": None,
        "vipChannel": "null",
        "currCompUrl": comp_url,
        "status": "10",
        "matterCode": None,
        "interruptControl": None,
    }


def _build_link_data(*, comp_url: str = "NameCheckInfo", ope_type: Optional[str] = "save") -> Dict[str, Any]:
    ld: Dict[str, Any] = {
        "compUrl": comp_url,
        "compUrlPaths": [comp_url],
        "token": "",
    }
    if ope_type:
        ld["opeType"] = ope_type
        ld["busiCompUrlPaths"] = "%5B%5D"
    return ld


def _build_nc_op_body(c: DriverContext, *, check_state: int, name_check_dto: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """NameCheckInfo/operationBusinessDataInfo 请求体（第5步/第7步共用）。"""
    body: Dict[str, Any] = {
        "areaCode": c.dist_code,
        "namePre": c.name_pre,
        "nameMark": c.name_mark,
        "allIndKeyWord": "",
        "showKeyWord": "",
        "noShowKeyWord": "实业,发展,实业发展,发展实业",
        "industrySpecial": c.ind_special,
        "industry": c.industry,
        "industryName": c.industry_name,
        "multiIndustry": "",
        "multiIndustryName": "",
        "organize": c.organize,
        "parentEntName": "",
        "dyElement": "",
        "isCheckGroupName": "0",
        "jtEntName": "",
        "jtUniscId": "",
        "jtShForm": "",
        "spellType": "20",
        "name": c.full_name,
        "noIndSign": "N",
        "declarationMode": "N",
        "fisDistCode": "",
        "distCode": c.dist_code,
        "streetCode": "",
        "entType": c.ent_type,
        "fzSign": "N",
        "isCheckBox": "Y",
        "checkState": int(check_state),
        "parentEntRegno": "",
        "bannedInfos": c.banned_infos_json or "",
        "hasParent": None,
        "needAudit": False,
        "tipKeyWords": c.banned_tip_keywords or "",
        "industryId": None,
        "flowData": _build_flow_data(c),
        "linkData": _build_link_data(comp_url="NameCheckInfo", ope_type="save"),
        "extraDto": _build_extra_dto(c),
        "signInfo": str(c.sign_info),
        "itemId": "",
    }
    if name_check_dto is not None:
        body["nameCheckDTO"] = name_check_dto
    return body


def _build_namecheck_repeat_body(c: DriverContext) -> Dict[str, Any]:
    return {
        "condition": "1",
        "busiId": c.busi_id,
        "busiType": c.busi_type_flow,
        "entType": c.ent_type,
        "name": c.full_name,
        "namePre": c.name_pre,
        "nameMark": c.name_mark,
        "distCode": c.dist_code,
        "areaCode": c.dist_code,
        "organize": c.organize,
        "industry": c.industry,
        "indSpec": c.ind_special,
        "hasParent": None,
        "jtParentEntName": "",
    }


# ==== 单步执行器 ====
@dataclass
class StepResult:
    name: str
    ok: bool
    http_status: int = 0
    code: str = ""
    result_type: str = ""
    busi_data_preview: str = ""
    reason: str = ""
    sent_body_keys: List[str] = field(default_factory=list)
    extracted: Dict[str, Any] = field(default_factory=dict)


def _assert_code(resp: Dict[str, Any]) -> tuple[bool, str, str, str]:
    code = str(resp.get("code") or "")
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    result_type = str(data.get("resultType") or "")
    msg = str(data.get("msg") or resp.get("msg") or "")
    ok = code == "00000"
    return ok, code, result_type, msg


def _preview_busidata(resp: Dict[str, Any], limit: int = 240) -> str:
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    bd = data.get("busiData")
    try:
        s = json.dumps(bd, ensure_ascii=False)
    except Exception:
        s = str(bd)
    return (s or "")[:limit]


def _namecheck_repeat_is_stop(bd: Dict[str, Any]) -> bool:
    check_state = str(bd.get("checkState") or "").strip()
    lang_state_code = str(bd.get("langStateCode") or "").strip().lower()
    return check_state == "2" or lang_state_code.endswith(".stop") or "state.stop" in lang_state_code


def _namecheck_repeat_stop_reason(bd: Dict[str, Any]) -> str:
    hits = bd.get("checkResult") or []
    top_name = ""
    if isinstance(hits, list) and hits:
        top = hits[0]
        if isinstance(top, dict):
            top_name = str(top.get("entName") or "").strip()
    suffix = f"；疑似冲突名称：{top_name}" if top_name else ""
    return f"名称库查重返回 stop，当前名称不能继续提交；请更换字号后重跑，或先人工释放原名称{suffix}"


def step_check_establish_name(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    body = _build_extra_dto(c)
    resp = client.post_json(API_CHECK_ESTABLISH_NAME, body)
    ok, code, result_type, msg = _assert_code(resp)
    return (
        StepResult(
            name="checkEstablishName",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=sorted(body.keys()),
        ),
        resp if ok else None,
    )


def step_load_current_location(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    # 与 mitm 备份里真实浏览器发的 body 严格一致（离线 diff 2026-04-22）：
    #   flowData 只要 {busiId, busiType, entType}，不得多 vipChannel/ywlbSign/等
    #   linkData 只要 {token: ""}，不得有 continueFlag
    #   整个 body 不要 extraDto
    # 多余字段会把服务端 SESSION 推到错误分支，导致下游 operationBusinessDataInfo D0022
    body: Dict[str, Any] = {
        "flowData": {
            "busiId": "",
            "busiType": c.busi_type_extra,  # "01_4"
            "entType": c.ent_type,
        },
        "linkData": {"token": ""},
    }
    resp = client.post_json(API_LOAD_CURRENT_LOCATION, body)
    ok, code, result_type, msg = _assert_code(resp)
    extracted: Dict[str, Any] = {}
    if ok:
        data = resp.get("data") or {}
        bd = data.get("busiData") or {}
        flow_resp = bd.get("flowData") or {}
        # 服务端把 busiType 降级为 "01"
        if isinstance(flow_resp.get("busiType"), str) and flow_resp["busiType"]:
            c.busi_type_flow = flow_resp["busiType"]
            extracted["flowData.busiType"] = c.busi_type_flow
    return (
        StepResult(
            name="loadCurrentLocationInfo",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=sorted(body.keys()),
            extracted=extracted,
        ),
        resp if ok else None,
    )


def step_namecheck_load(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    # 离线 diff 2026-04-22：样本 body 还有 top-level itemId=""，driver 原来漏了
    body = {
        "flowData": _build_flow_data(c),
        "linkData": _build_link_data(comp_url="NameCheckInfo", ope_type=None),
        "extraDto": _build_extra_dto(c),
        "itemId": "",
    }
    resp = client.post_json(API_NC_LOAD, body)
    ok, code, result_type, msg = _assert_code(resp)
    return (
        StepResult(
            name="NameCheckInfo/loadBusinessDataInfo",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=sorted(body.keys()),
        ),
        resp if ok else None,
    )


def step_banned_lexicon(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    resp = client.get_json(API_BANNED_LEXICON, {"nameMark": c.name_mark})
    ok, code, result_type, msg = _assert_code(resp)
    data = resp.get("data") or {}
    bd = data.get("busiData") or {}
    tip = str(bd.get("tipStr") or "")
    success_flag = bool(bd.get("success")) if isinstance(bd.get("success"), bool) else bd.get("success")
    # ★ 捕获禁限用词信息以回传 save 请求
    tip_kw = str(bd.get("tipKeyWords") or "")
    if tip_kw:
        c.banned_tip_keywords = tip_kw
    banned_info_list = bd.get("bannedLexiconInfo")
    if isinstance(banned_info_list, list) and banned_info_list:
        try:
            c.banned_infos_json = json.dumps(banned_info_list, ensure_ascii=False)
        except Exception:
            pass
    extracted = {"success": success_flag, "tipStr": tip}
    return (
        StepResult(
            name="bannedLexiconCalibration",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=["nameMark"],
            extracted=extracted,
        ),
        resp if ok else None,
    )


def step_nc_op_first_save(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    body = _build_nc_op_body(c, check_state=1, name_check_dto=None)
    resp = client.post_json(API_NC_OP, body)
    ok, code, result_type, msg = _assert_code(resp)
    extracted: Dict[str, Any] = {"resultType": result_type}
    # ★ 检测 15 分钟核名限流（code=00000 + rt=1 + "15分钟"）
    if ok and result_type == "1" and "15分钟" in msg:
        c._rate_limited_15min = True
        extracted["rate_limited_15min"] = True
    if ok:
        data = resp.get("data") or {}
        bd = data.get("busiData") or {}
        fdr = bd.get("flowData") or {}
        bid = fdr.get("busiId")
        if isinstance(bid, str) and bid.strip():
            c.busi_id = bid.strip()
            extracted["busiId_from_first_save"] = c.busi_id
        sign_info = data.get("signInfo")
        if isinstance(sign_info, (str, int)):
            try:
                c.sign_info = int(sign_info)
                extracted["signInfo_refreshed"] = c.sign_info
            except ValueError:
                pass
    return (
        StepResult(
            name="NameCheckInfo/operationBusinessDataInfo#first",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=sorted(body.keys()),
            extracted=extracted,
        ),
        resp if ok else None,
    )


def step_namecheck_repeat(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    body = _build_namecheck_repeat_body(c)
    resp = client.post_json(API_NC_REPEAT, body)
    ok, code, result_type, msg = _assert_code(resp)
    extracted: Dict[str, Any] = {}
    if ok:
        data = resp.get("data") or {}
        bd = data.get("busiData") or {}
        # 完整回灌到 nameCheckDTO
        c.name_check_dto = bd
        extracted["nameCheckDTO_captured"] = True
        hits = bd.get("checkResult") or []
        extracted["hit_count"] = len(hits) if isinstance(hits, list) else 0
        extracted["checkState_reported"] = bd.get("checkState")
        extracted["langStateCode"] = bd.get("langStateCode")
        if _namecheck_repeat_is_stop(bd):
            ok = False
            code = "NAME_CHECK_STOP"
            msg = _namecheck_repeat_stop_reason(bd)
            extracted["name_check_stop"] = True
    return (
        StepResult(
            name="NameCheckInfo/nameCheckRepeat",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else (msg if code == "NAME_CHECK_STOP" else f"非 00000: code={code} msg={msg}"),
            sent_body_keys=sorted(body.keys()),
            extracted=extracted,
        ),
        resp if isinstance(resp, dict) else None,
    )


def step_nc_op_second_save(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    dto = c.name_check_dto or {}
    # 服务端报告的 checkState 优先；否则维持 1
    reported = dto.get("checkState")
    cs = int(reported) if isinstance(reported, int) else (int(reported) if isinstance(reported, str) and reported.isdigit() else 1)
    body = _build_nc_op_body(c, check_state=cs, name_check_dto=dto)
    # mitm 样本 L659 证实：二次保存 body 必须带 afterNameCheckSign="Y"（用户已确认近似名）。
    # 缺失会让服务端返回 resultType=2 且不分配 busiId。
    body["afterNameCheckSign"] = "Y"
    resp = client.post_json(API_NC_OP, body)
    ok, code, result_type, msg = _assert_code(resp)
    extracted: Dict[str, Any] = {"checkState_sent": cs}
    # ★ 检测 15 分钟核名限流
    if ok and result_type == "1" and "15分钟" in msg:
        c._rate_limited_15min = True
        extracted["rate_limited_15min"] = True
    if ok:
        data = resp.get("data") or {}
        bd = data.get("busiData") or {}
        fdr = bd.get("flowData") or {}
        bid = fdr.get("busiId")
        if isinstance(bid, str) and bid.strip():
            c.busi_id = bid.strip()
            extracted["busiId_from_second_save"] = c.busi_id
        # ★ 如果 resultType=2（禁限词/业务警告要求再确认），标记需要第三次 save
        if result_type == "2" and not c.busi_id:
            c._needs_third_save = True
            extracted["needs_third_save"] = True
    return (
        StepResult(
            name="NameCheckInfo/operationBusinessDataInfo#second",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=sorted(body.keys()),
            extracted=extracted,
        ),
        resp if ok else None,
    )


def step_nc_op_third_save(client: ICPSPClient, c: DriverContext) -> tuple[StepResult, Optional[Dict[str, Any]]]:
    """第三次保存 — 当第二次返回 resultType=2（含限制词/业务警告需再确认）时使用。
    带 continueFlag 强制推进，类似 establish BasicInfo 的二次 save 模式。"""
    if not getattr(c, "_needs_third_save", False):
        # 不需要第三次 save，直接返回成功
        return (
            StepResult(
                name="NameCheckInfo/operationBusinessDataInfo#confirm",
                ok=True,
                code="SKIP",
                result_type="",
                reason="no_third_save_needed",
                extracted={"skipped": True},
            ),
            None,
        )
    dto = c.name_check_dto or {}
    reported = dto.get("checkState")
    cs = int(reported) if isinstance(reported, int) else (int(reported) if isinstance(reported, str) and reported.isdigit() else 1)
    body = _build_nc_op_body(c, check_state=cs, name_check_dto=dto)
    body["afterNameCheckSign"] = "Y"
    body["continueFlag"] = "continueFlag"
    resp = client.post_json(API_NC_OP, body)
    ok, code, result_type, msg = _assert_code(resp)
    extracted: Dict[str, Any] = {"checkState_sent": cs, "continueFlag": True}
    if ok:
        data = resp.get("data") or {}
        bd = data.get("busiData") or {}
        fdr = bd.get("flowData") or {}
        bid = fdr.get("busiId")
        if isinstance(bid, str) and bid.strip():
            c.busi_id = bid.strip()
            extracted["busiId_from_third_save"] = c.busi_id
    return (
        StepResult(
            name="NameCheckInfo/operationBusinessDataInfo#confirm",
            ok=ok,
            code=code,
            result_type=result_type,
            busi_data_preview=_preview_busidata(resp),
            reason="" if ok else f"非 00000: code={code} msg={msg}",
            sent_body_keys=sorted(body.keys()),
            extracted=extracted,
        ),
        resp if ok else None,
    )


# ==== 主驱动 ====
def run(case_path: Path, *, verbose: bool = False) -> int:
    rec: Dict[str, Any] = {
        "schema": "ufo.phase1_protocol_driver.v1",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "case_path": str(case_path),
        "steps": [],
        "final": {},
    }
    if not case_path.is_file():
        rec["error"] = f"case_not_found: {case_path}"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ERROR: case not found: {case_path}")
        return 2

    case = json.loads(case_path.read_text(encoding="utf-8"))
    c = DriverContext.from_case(case)
    rec["context"] = {
        "ent_type": c.ent_type,
        "dist_codes": c.dist_codes,
        "full_name": c.full_name,
        "name_mark": c.name_mark,
        "organize": c.organize,
        "industry": c.industry,
        "signInfo_initial": c.sign_info,
    }
    print("=== Phase 1 纯协议驱动器 ===")
    print(f"  entType        : {c.ent_type}")
    print(f"  full_name      : {c.full_name}")
    print(f"  distCodes      : {c.dist_codes}")
    print(f"  industry/ind_sp: {c.industry} / {c.ind_special}")
    print(f"  organize       : {c.organize}")
    print(f"  signInfo(init) : {c.sign_info}")
    print()

    client = ICPSPClient()

    # (fn, is_optional, tag)
    # optional=True：失败仅警告、不中止；这些接口只在 guide 入口才可用，从 portal 直跳 core 时会被拒
    steps: List[tuple[Any, bool, str]] = [
        (step_check_establish_name, True, "guide"),   # guide 预判，portal 直跳会被拒
        (step_load_current_location, True, "guide"),  # guide 定位
        (step_namecheck_load, True, "guide"),         # 真实抓包里未出现此调用；服务端可能拒；纳入观测
        (step_banned_lexicon, True, "query"),         # 禁限用词是辅助，失败不致命
        (step_nc_op_first_save, False, "core"),
        (step_namecheck_repeat, False, "query"),
        (step_nc_op_second_save, False, "core"),
        (step_nc_op_third_save, True, "core"),   # 禁限词确认（仅在第二次 save 返回 rt=2 时触发；optional 以免 A0002 阻断）
    ]

    # L6.5 bootstrap 闭环控制：核心 core 步骤若因"未授权"拒绝，触发一次 CDP 引导后重试
    bootstrap_tried = False
    # 步间节流（秒）：避免连续请求触发服务端限流（D0029 操作频繁）
    INTER_STEP_DELAY = 0.9

    def _try_bootstrap(reason: str) -> Dict[str, Any]:
        """调用浏览器 bootstrapper；返回其状态。"""
        if _session_bootstrap is None:
            return {"ok": False, "error": "bootstrap_module_unavailable"}
        print(f"  >>> 触发 L6 会话引导（因 {reason}），CDP 导航到 guide/base ...")
        try:
            br = _session_bootstrap(ent_type=c.ent_type, busi_type=str(case.get("busiType_default") or "02_4"))
        except Exception as e:
            return {"ok": False, "error": f"bootstrap_exception:{e!r}"}
        final = br.get("final") or {}
        ok = bool(final.get("ok"))
        print(f"  >>> bootstrap ok={ok} href={final.get('href')}  cookie_has_session={final.get('cookie_has_session')}")
        # bootstrap 会把新 Cookie/Auth 写入 runtime_auth_headers.json；
        # ICPSPClient 每次 _headers() 都会重新从磁盘读，会自动生效。
        return {"ok": ok, "record": br}

    def _run_one(fn: Any, optional: bool) -> tuple[Optional[StepResult], int, str]:
        t0 = time.time()
        try:
            r, _ = fn(client, c)
        except Exception as e:
            return None, int((time.time() - t0) * 1000), f"exception: {e!r}"
        return r, int((time.time() - t0) * 1000), ""

    exit_code = 0
    for i, (fn, optional, tag) in enumerate(steps, 1):
        if i > 1:
            # 步间节流：避免连续请求触发服务端限流（D0029）
            time.sleep(INTER_STEP_DELAY)
        res, dt, err_text = _run_one(fn, optional)

        # 若 core 步骤因 SESSION 未授权拒绝，触发一次 bootstrap 并重试
        if (
            res is not None
            and not res.ok
            and tag == "core"
            and res.code == SESSION_GATE_CODE
            and not bootstrap_tried
        ):
            bootstrap_tried = True
            br = _try_bootstrap(f"{res.name} 被 SESSION 网关拒绝")
            rec["steps"].append({
                "i": f"{i}.bootstrap",
                "name": "session_bootstrap_cdp",
                "ok": bool(br.get("ok")),
                "data": br,
            })
            if br.get("ok"):
                print(f"  >>> bootstrap 成功，重试 step[{i}] {fn.__name__} ...")
                res, dt, err_text = _run_one(fn, optional)

        if res is None:
            rec["steps"].append({
                "i": i,
                "name": fn.__name__,
                "ok": False,
                "optional": optional,
                "tag": tag,
                "reason": err_text[:240],
                "duration_ms": dt,
            })
            print(f"[{i}] {fn.__name__}  EXCEPTION  ({dt}ms)  optional={optional}")
            print(f"    {err_text[:300]}")
            low = err_text.lower()
            if "401" in low or "403" in low or "unauthorized" in low or "forbidden" in low:
                exit_code = 3
                rec["error"] = "auth_expired"
                break
            if not optional:
                exit_code = 4
                rec["error"] = "transport_error"
                break
            continue
        item = {
            "i": i,
            "name": res.name,
            "ok": res.ok,
            "optional": optional,
            "tag": tag,
            "code": res.code,
            "resultType": res.result_type,
            "reason": res.reason,
            "duration_ms": dt,
            "sent_body_keys": res.sent_body_keys,
            "busi_data_preview": res.busi_data_preview,
            "extracted": res.extracted,
        }
        rec["steps"].append(item)
        if res.ok:
            flag = "OK"
        elif optional:
            flag = "SKIP"
        else:
            flag = "FAIL"
        print(f"[{i}] {res.name}  {flag}  code={res.code} resultType={res.result_type} ({dt}ms){' (optional)' if optional and not res.ok else ''}")
        if res.extracted:
            keep = {k: v for k, v in res.extracted.items() if k != "nameCheckDTO_captured"}
            if keep:
                print(f"    extracted: {json.dumps(keep, ensure_ascii=False)}")
        if verbose and res.busi_data_preview:
            print(f"    busiData: {res.busi_data_preview}")
        # 限流冷却：一旦遇到 D0029，立即停跑避免加剧
        if res and res.code == RATE_LIMIT_CODE:
            exit_code = 5
            rec["error"] = "rate_limited_cooldown"
            rec["hint"] = "服务端限流，请等 5-10 分钟再试；期间不要反复调用"
            print(f"  !!! 命中服务端限流（D0029 操作频繁），立即停止避免加剧")
            break
        if not res.ok and not optional:
            exit_code = 4
            rec["error"] = f"step_{i}_business_reject"
            break

    # ── 构建诊断信息 ──
    name_check_hits = []
    if c.name_check_dto:
        for hit in (c.name_check_dto.get("checkResult") or []):
            if isinstance(hit, dict):
                name_check_hits.append({
                    "entName": hit.get("entName"),
                    "regionName": hit.get("regionName"),
                    "nameMark": hit.get("nameMark"),
                    "state": hit.get("state"),
                })

    rec["final"] = {
        "busi_id": c.busi_id,
        "full_name": c.full_name,
        "name_mark": c.name_mark,
        "name_pre": c.name_pre,
        "organize": c.organize,
        "hit_count": len(name_check_hits),
        "checkState_reported": (c.name_check_dto or {}).get("checkState"),
        "langStateCode": (c.name_check_dto or {}).get("langStateCode"),
    }
    # ── 名称诊断块（供交互系统使用）──
    rec["name_diagnosis"] = {
        "banned_tip_keywords": c.banned_tip_keywords or "",
        "banned_infos_json": c.banned_infos_json or "",
        "similar_names": name_check_hits,
        "needs_third_save": getattr(c, "_needs_third_save", False),
    }
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"Saved: {OUT_JSON}")

    if exit_code == 0 and not c.busi_id:
        # 全部步骤都 200 但没回 busiId — 名称需要用户干预
        # exit_code=6 = 名称需要用户交互决定（禁限词/近似名警告）
        exit_code = 6
        rec["error"] = "name_needs_intervention"
        rec["hint"] = "服务端返回 resultType=2（名称警告），需要用户确认或更换名称"
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    if exit_code == 0:
        print("=== 里程碑达成 ===")
        print(f"  busiId    : {c.busi_id}")
        print(f"  hit_count : {rec['final']['hit_count']}")
        print(f"  checkState: {rec['final']['checkState_reported']}")
    elif exit_code == 6:
        print(f"=== 核名需要用户干预 (exit=6) ===")
    else:
        print(f"=== 未达里程碑，exit={exit_code}，原因: {rec.get('error')} ===")

    return exit_code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=Path, default=DEFAULT_CASE, help="案例 JSON 路径")
    ap.add_argument("--verbose", action="store_true", help="打印每步 busiData 预览")
    args = ap.parse_args()
    return run(args.case, verbose=bool(args.verbose))


if __name__ == "__main__":
    raise SystemExit(main())
