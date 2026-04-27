#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第二阶段（信息补充 → 投资人信息 → 提交 → 设立 YbbSelect）**纯协议驱动器**。

流程（来自 mitm 样本 phase2_samples.json）:
  1. name/loadCurrentLocationInfo       （定位 NameSupplement 页）
  2. NameSupplement/loadBusinessDataInfo（读补充信息表单）
  3. NameShareholder/loadBusinessInfoList（读股东列表）
  4. NameShareholder/loadBusinessDataInfo（读股东表单模板）
  5. NameShareholder/operationBusinessDataInfo（保存股东，需加密）
  6. NameShareholder/loadBusinessInfoList（重读股东）
  7. NameSupplement/operationBusinessDataInfo（保存补充，需加密）
  8. register/name/submit               （提交名称登记）
  9. NameSuccess/loadBusinessDataInfo   （读成功页）
 10. manager/mattermanager/matters/operate x2（进 establish）
 11. register/establish/loadCurrentLocationInfo
 12. establish/YbbSelect/loadBusinessDataInfo（云帮办选择，STOP！）

加密字段（进入 5/7 需先破解）:
  · 身份证号: RSA 1024 Base64
  · 经营范围 (businessArea / busiAreaData / busiAreaName): AES hex

前置: Phase 1 已完成拿到 busiId（读 phase1_protocol_driver_latest.json）
      或通过 case 的 busi_id_from_phase1 字段传入

退出码:
  0 — 里程碑达成（YbbSelect 页加载成功，或当前阶段全部成功）
  2 — 前置错误（缺 case / busiId）
  3 — 认证失效
  4 — 服务端业务拒绝
  5 — 加密未破解，暂停在写步骤前
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402
from icpsp_crypto import rsa_encrypt, aes_encrypt  # noqa: E402
from phase2_constants import *  # noqa: E402
try:
    from cdp_ybb_select import run_ybb_select_general_flow
except Exception:  # pragma: no cover
    run_ybb_select_general_flow = None
from phase2_constants import (  # noqa: E402
    SIGN_INFO_NAME,
    SIGN_INFO_ESTABLISH,
    BASICINFO_META_STRIP,
    BUSI_COMP_URL_PATHS_EMPTY,
    CODE_SESSION_GATE,
    CODE_PRIVILEGE_D0021,
    CODE_RATE_LIMIT,
    REFERER_CORE,
    API_BENEFIT_CALLBACK,
    establish_comp_load,
    establish_comp_op,
    establish_comp_list,
)
import phase2_bodies as pb  # noqa: E402

# CDP 辅助（BenefitUsers 受益所有人）— 可选依赖
try:
    from cdp_benefit_users import run_benefit_users_commit as _cdp_benefit_commit
except ImportError:
    _cdp_benefit_commit = None  # type: ignore[assignment]

OUT_JSON = ROOT / "dashboard" / "data" / "records" / "phase2_protocol_driver_latest.json"
DEFAULT_CASE = ROOT / "docs" / "case_有为风.json"
PHASE1_LATEST = ROOT / "dashboard" / "data" / "records" / "phase1_protocol_driver_latest.json"

# 向后兼容别名 — 新代码统一从 phase2_constants 导入
SESSION_GATE_CODE = CODE_SESSION_GATE
PRIVILEGE_CODE = "D0022"  # phase2_constants.CODE_PRIVILEGE_D0022
RATE_LIMIT_CODE = CODE_RATE_LIMIT

# API 常量
API_NAME_LOAD_LOC = "/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo"
API_NSUPP_LOAD = "/icpsp-api/v4/pc/register/name/component/NameSupplement/loadBusinessDataInfo"
API_NSUPP_OP = "/icpsp-api/v4/pc/register/name/component/NameSupplement/operationBusinessDataInfo"
API_NSH_LIST = "/icpsp-api/v4/pc/register/name/component/NameShareholder/loadBusinessInfoList"
API_NSH_LOAD = "/icpsp-api/v4/pc/register/name/component/NameShareholder/loadBusinessDataInfo"
API_NSH_OP = "/icpsp-api/v4/pc/register/name/component/NameShareholder/operationBusinessDataInfo"
API_NAME_SUBMIT = "/icpsp-api/v4/pc/register/name/submit"
API_NSUCC_LOAD = "/icpsp-api/v4/pc/register/name/component/NameSuccess/loadBusinessDataInfo"
API_MATTERS_OP = "/icpsp-api/v4/pc/manager/mattermanager/matters/operate"
API_EST_LOAD_LOC = "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo"
API_YBB_LOAD = "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo"
API_EST_BASICINFO_LOAD = "/icpsp-api/v4/pc/register/establish/component/BasicInfo/loadBusinessDataInfo"
API_EST_BASICINFO_OP = "/icpsp-api/v4/pc/register/establish/component/BasicInfo/operationBusinessDataInfo"


# 向后兼容别名（新代码统一从 phase2_constants import）
SIGN_INFO_MAGIC = SIGN_INFO_NAME


@dataclass
class Phase2Context:
    case: Dict[str, Any]
    busi_id: str = ""
    phase1_busi_id: str = ""
    ent_type: str = "4540"
    busi_type: str = "01"
    dist_code: str = "450921"
    dist_codes: List[str] = field(default_factory=list)
    address: str = "广西壮族自治区玉林市容县"
    name_code: str = "0"
    full_name: str = ""
    # 投资人/承办人（都是同一人）
    person_name: str = ""
    person_id_no: str = ""
    person_mobile: str = ""
    person_email: str = ""
    # name/submit 成功后服务端分配的 nameId（step 12/13 进 establish 时需要）
    name_id: Optional[str] = None
    # 当前登录用户ID（linkData.token 需要，producePdf 等接口校验）
    user_id: str = ""
    # 运行时
    last_http_status: int = 0
    snapshot: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_case(cls, case: Dict[str, Any], busi_id: str) -> "Phase2Context":
        ctx = cls(case=case, busi_id=busi_id)
        ctx.phase1_busi_id = busi_id
        ctx.ent_type = str(case.get("entType_default") or "4540")
        ctx.dist_codes = [str(x) for x in (case.get("phase1_dist_codes") or ["450000", "450900", "450921"])]
        ctx.dist_code = ctx.dist_codes[-1]
        ctx.full_name = str(case.get("phase1_check_name") or case.get("company_name_phase1_normalized") or "").strip()
        person = case.get("person") or {}
        ctx.person_name = str(person.get("name") or "").strip()
        ctx.person_id_no = str(person.get("id_no") or "").strip()
        ctx.person_mobile = str(person.get("mobile") or "").strip()
        ctx.person_email = str(person.get("email") or "").strip()
        return ctx


# ─── body 构造 ───
def _flow_data(c: Phase2Context, comp_url: Optional[str] = None) -> Dict[str, Any]:
    return {
        "busiId": c.busi_id,
        "entType": c.ent_type,
        "busiType": c.busi_type,
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


def _extra_dto(c: Phase2Context) -> Dict[str, Any]:
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


# ─── 步骤实现（阶段 A: 读操作 1-4） ───
def step1_load_current_location(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """用已有 busiId 定位——服务端会回 currentComp / currentStep 告诉我们下一步去哪。"""
    body = {
        "flowData": {
            "busiId": c.busi_id,
            "busiType": "01_4",    # 首次入口用 01_4
            "entType": c.ent_type,
        },
        "linkData": {"token": c.user_id},
    }
    return client.post_json(API_NAME_LOAD_LOC, body)


def step2_load_name_supplement(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    body = {
        "flowData": _flow_data(c, "NameSupplement"),
        "linkData": {
            "compUrl": "NameSupplement",
            "compUrlPaths": ["NameSupplement"],
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
        "itemId": "",
    }
    return client.post_json(API_NSUPP_LOAD, body)


def step3_load_shareholder_list(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    body = {
        "flowData": _flow_data(c, "NameShareholder"),
        "linkData": {
            "compUrl": "NameShareholder",
            "compUrlPaths": ["NameSupplement", "NameShareholder"],
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
        "itemId": "",
        "query": "",
        "page": {"pageNum": 1, "pageSize": 6},
    }
    return client.post_json(API_NSH_LIST, body)


def step4_load_shareholder_form(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    body = {
        "flowData": _flow_data(c, "NameShareholder"),
        "linkData": {
            "compUrl": "NameShareholder",
            "compUrlPaths": ["NameSupplement", "NameShareholder"],
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
        "itemId": "",
    }
    return client.post_json(API_NSH_LOAD, body)


# ─── 步骤 5-7 写操作（含加密） ───

def step5_save_shareholder(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """保存投资人信息。身份证号 RSA 加密。"""
    body = {
        "id": None,
        "name": c.person_name,
        "type": "20",               # 自然人投资人
        "certificateType": "10",    # 身份证
        "certificateNo": rsa_encrypt(c.person_id_no),  # RSA 加密
        "encryptedCertificateNo": None,
        "blicTypes": "",
        "blicNO": "",
        "encryptedBLicNO": None,
        "memberType": "",
        "nationalityCode": "156",   # 中国
        "realInvestMoney": None,
        "realInvestMoneyType": "156",
        "realInvestMoneyName": "人民币",
        "moneyRatio": None,
        "tel": None,
        "encryptedTel": None,
        "entRepName": None,
        "entRepType": None,
        "entRepCerNo": None,
        "encryptedEntRepCerNo": None,
        "cardType": None,
        "apprType": None,
        "apprReason": None,
        "rcMoneyKindCode": "156",
        "registerCapital": None,
        "mcInvestNeedSign": "N",
        "idCardZmUuid": "uploadPluginValue",    # 占位符（前端逻辑：未上传也能过）
        "idCardFmUuid": "uploadPluginValue",
        "fileSize": "5120",
        "cutImgSize": "5120",
        "flowData": _flow_data(c, "NameShareholder"),
        "linkData": {
            "compUrl": "NameShareholder",
            "opeType": "save",
            "compUrlPaths": ["NameSupplement", "NameShareholder"],
            "busiCompUrlPaths": '%5B%7B%22compUrl%22%3A%22NameSupplement%22%2C%22id%22%3A%22%22%7D%5D',
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
        "signInfo": "-252238669",
        "itemId": "",
    }
    return client.post_json(API_NSH_OP, body)


def step6_reload_shareholder_list(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """保存后刷新股东列表（验证写入成功）。"""
    return step3_load_shareholder_list(client, c)


def _build_business_area_plaintext(case: Dict[str, Any]) -> str:
    """构造经营范围明文 JSON（case-aware）。

    优先从 case["busiAreaData_items"] 读完整列表；
    否则用 case 的行业字段构造单项；
    最终 fallback 到默认软件开发。
    """
    items = case.get("busiAreaData_items")
    if items and isinstance(items, list):
        return json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    # 从 case 散字段构造
    biz_code = case.get("busiAreaCode") or "I3006"
    biz_name = case.get("busiAreaName") or "软件开发"
    category = case.get("areaCategory") or biz_code[0] if biz_code else "I"
    indus_codes = case.get("indusTypeCode") or "6511;6512;6513"
    mid_codes = case.get("midIndusTypeCode") or "651;651;651"
    items = [
        {
            "id": biz_code,
            "stateCo": "1",
            "name": biz_name,
            "pid": "65",
            "minIndusTypeCode": indus_codes,
            "midIndusTypeCode": mid_codes,
            "isMainIndustry": "1",
            "category": category,
            "indusTypeCode": indus_codes,
            "indusTypeName": biz_name,
            "additionalValue": "",
        }
    ]
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def _build_agent_block(c: Phase2Context) -> Dict[str, Any]:
    """承办人对象（与投资人同一人）。对齐 mitm 样本的 24 个字段。"""
    now_ms = int(time.time() * 1000)
    keep_end_ms = now_ms + 91 * 24 * 3600 * 1000  # 承诺书有效期 91 天
    return {
        "isOrgan": None,
        "organName": None,
        "organUnsid": None,
        "organTel": None,
        "encryptedOrganTel": None,
        "agentName": c.person_name,
        "certificateType": "10",
        "certificateTypeName": None,
        "certificateNo": rsa_encrypt(c.person_id_no),
        "idCardZmUuid": "uploadPluginValue",
        "idCardFmUuid": "uploadPluginValue",
        "encryptedCertificateNo": None,
        "phone": None,
        "encryptedPhone": None,
        "mobile": rsa_encrypt(c.person_mobile) if c.person_mobile else None,
        "encryptedMobile": None,
        "keepStartDate": now_ms,
        "keepEndDate": keep_end_ms,
        "modifyMaterial": "1",
        "modifyWord": "1",
        "modifyForm": "1",
        "otherModifyItem": "1",
        "license": "1",
        "isLegalPerson": None,
    }


def step8_name_submit(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """提交名称登记（关键：告别 Phase 1，正式进入待审核）。
    注意：body 必须带 continueFlag="" + compUrl/compUrlPaths，否则 D0018。"""
    flow = _flow_data(c, "NameShareholder")    # 对齐 mitm 样本，current 停在 Shareholder
    body = {
        "flowData": flow,
        "linkData": {
            "compUrl": "NameSupplement",
            "compUrlPaths": ["NameSupplement"],
            "continueFlag": "",
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
    }
    return client.post_json(API_NAME_SUBMIT, body)


def step9_load_name_success(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """读 NameSuccess 页面（状态 status=51 表示已提交）。
    从响应中提取 nameId 并保存到 context（步骤 12/13 需要）。"""
    body = {
        "flowData": {**_flow_data(c, "NameSuccess"), "status": "51"},
        "linkData": {
            "compUrl": "NameSuccess",
            "compUrlPaths": ["NameSuccess"],
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
        "itemId": "",
    }
    resp = client.post_json(API_NSUCC_LOAD, body)
    # 从响应 flowData 里提取 nameId
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        fd = bd.get("flowData") or {}
        nid = fd.get("nameId")
        if nid:
            c.name_id = str(nid)
            print(f"    [captured nameId] {c.name_id}")
    except Exception:
        pass
    return resp


def step10_matters_before(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """matters/operate btnCode=108 dealFlag=before（设立登记前置检查）。
    注意：btnCode=108 才是设立登记入口（mitm 实录验证）。"""
    body = {"busiId": c.busi_id, "btnCode": "108", "dealFlag": "before"}
    return client.post_json(API_MATTERS_OP, body)


def step11_matters_operate(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """matters/operate btnCode=108 dealFlag=operate（真正进入设立登记）。
    执行后服务端把会话状态切到 busiType=02，才能访问 establish 下的 YbbSelect/BasicInfo 组件。"""
    body = {"busiId": c.busi_id, "btnCode": "108", "dealFlag": "operate"}
    return client.post_json(API_MATTERS_OP, body)


def _establish_busi_type(ent_type: str) -> str:
    """根据 entType 返回 establish 入口 busiType。"""
    mapping = {"4540": "02_4", "1151": "02_4", "1150": "02_1"}
    return mapping.get(ent_type, "02_1")


def step12_establish_location(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """进入 establish 流程定位（业务从 01 切 02）。
    初次进入：不传 busiId——名称登记的 busiId 在设立登记里无效。
    断点续跑：只传明确拿到的 establish busiId，服务端据此绑定设立上下文。
    """
    est_bid = c.snapshot.get("establish_busiId") or None
    if not est_bid and c.busi_id and c.busi_id != c.phase1_busi_id:
        est_bid = c.busi_id
    body = {
        "flowData": {
            "busiId": est_bid,
            "busiType": _establish_busi_type(c.ent_type),
            "entType": c.ent_type,
            "nameId": c.name_id or "",
        },
        "linkData": {"continueFlag": "continueFlag", "token": c.user_id},
    }
    resp = client.post_json(API_EST_LOAD_LOC, body, extra_headers={
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
    })
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        fd = bd.get("flowData") or {}
        est_busi_id = fd.get("busiId")
        if est_busi_id:
            c.snapshot["establish_busiId"] = str(est_busi_id)
            print(f"    [captured establish busiId] {est_busi_id}")
        else:
            c.snapshot["establish_busiId"] = None
            print(f"    [establish busiId] null (正常——BasicInfo save 时服务端分配)")
    except Exception:
        pass
    return resp


def step14_basicinfo_load(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """Establish 流程 BasicInfo 组件 load。
    关键（mitm 实录 [109] 验证）：
    - flowData.busiId = null（设立上下文，Phase 1 名称登记 busiId 不用）
    - flowData.busiType = "02"（不是 02_4）
    - 响应 busiData 含 flowData/linkData/signInfo/encryptData + 所有 178 个业务字段
    """
    bt_short = "02"  # establish
    ywlb = "4"       # 4540 → ywlbSign=4
    body = {
        "flowData": {
            "busiId": None,  # 关键：设立上下文 busiId 为 null
            "entType": c.ent_type,
            "busiType": bt_short,
            "ywlbSign": ywlb,
            "busiMode": None,
            "nameId": c.name_id,
            "marPrId": None,
            "secondId": None,
            "vipChannel": None,
            "currCompUrl": "BasicInfo",
            "status": "10",
            "matterCode": None,
            "interruptControl": None,
        },
        "linkData": {
            "compUrl": "BasicInfo",
            "compUrlPaths": ["BasicInfo"],
            "token": c.user_id,
        },
        "itemId": "",
    }
    resp = client.post_json(API_EST_BASICINFO_LOAD, body, extra_headers={
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
    })
    # 从响应里提取 signInfo 供后续 save 使用
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        si = bd.get("signInfo")
        if si is not None:
            c.snapshot["basicinfo_signInfo"] = str(si)
            c.snapshot["last_sign_info"] = str(si)  # ★ 初始化动态 signInfo 链
            print(f"    [captured basicinfo signInfo] {si}")
        # 保存完整 busiData 供 step 15 save 复用
        c.snapshot["basicinfo_busiData"] = bd
    except Exception:
        pass
    return resp


# 元数据字段过滤表：统一从 phase2_constants 导入（新代码用 BASICINFO_META_STRIP）
_BASICINFO_METADATA_STRIP = BASICINFO_META_STRIP


def step15_basicinfo_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """Establish/BasicInfo save（基本信息保存）— 基于 mitm 实录的 42-key 真实成功 body 构建。

    ★ 关键认知：协议模式直接带 continueFlag="continueFlag" 即可跳过名称风险确认，
    不需要像 SPA 那样先 null → rt=2 → 再 continueFlag。
    先发 null 会导致 server session 状态变更，后续 continueFlag 也无法恢复。

    关键（相对旧版修正）：
    - signInfo 动态取值（preload 或上一步 load）
    - entPhone 是 RSA 加密密文
    - businessArea / busiAreaName 是明文
    - busiAreaData 是 URL-encoded JSON
    - flowData.busiId = None（首次 save 由服务端分配）
    - linkData.continueFlag = "continueFlag"（★ 一次通过，不走两阶段）
    """
    base = c.snapshot.get("basicinfo_busiData") or {}

    save_body = pb.build_basicinfo_save_body(
        c.case, base,
        ent_type=c.ent_type, name_id=c.name_id,
        user_id=c.user_id,
    )
    # ★ 确保 continueFlag="continueFlag"（_base_link_data 已默认设置，此处防护性确认）
    if "linkData" in save_body:
        save_body["linkData"]["continueFlag"] = "continueFlag"

    resp = _post_save_and_track_sign(
        client, API_EST_BASICINFO_OP, save_body, c,
        extra_headers={"Referer": REFERER_CORE},
    )
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        fd = bd.get("flowData") or {}
        new_bid = fd.get("busiId")
        if new_bid:
            c.snapshot["establish_busiId"] = str(new_bid)
            print(f"    [captured establish busiId after save] {new_bid}")
    except Exception:
        pass
    return resp


# ============================================================
# Phase 2 第二段：设立登记组件推进（step 16-25）
# ============================================================
#
# 推进策略（来自 docs/Phase2第二日突破_MemberInfo至SlUploadMaterial_20260423.md）：
#   - save 成功（resultType=0）→ 服务端记录该步完成
#   - 不需要主动 load 下一组件，由调用方连续调下一步 save
#   - 有 busi_id 后所有步骤的 flowData.busiId 用 establish_busiId（step 15 save 返回）
#
# 所有 save 路径：establish_comp_op(component_name)
# ============================================================


def _establish_busi_id(c: Phase2Context) -> Optional[str]:
    """取 establish busiId：
    1) 优先 step 15 BasicInfo save 返回的新 busiId
    2) 否则回退到 c.busi_id（断点续跑时，Phase 1 保存的 busi_id 就是 establish busiId）
    3) 最后 None（服务端推断）
    """
    return c.snapshot.get("establish_busiId") or c.busi_id or None


def _apply_dynamic_sign_info(body: Dict[str, Any], c: Phase2Context) -> Dict[str, Any]:
    """★ 关键铁律：signInfo 是动态签名，必须用上一次 load/save 返回的值。

    如果 snapshot 里有 last_sign_info，用它覆盖 body["signInfo"]。
    否则保留 builder 里的 fallback 常量。
    """
    last = c.snapshot.get("last_sign_info")
    if last and "signInfo" in body:
        body["signInfo"] = str(last)
    return body


def _load_component_with_context(client: "ICPSPClient", c: Phase2Context,
                                 comp_url: str,
                                 extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    import urllib.parse as _urlp
    _SUB_COMP_PARENT = {
        "MemberBaseInfo": "MemberPost",
        "MemberInfo": "MemberPool",
    }
    parent = _SUB_COMP_PARENT.get(comp_url)
    prev_fd = c.snapshot.get("last_save_flowData") or {}
    prev_ld = c.snapshot.get("last_save_linkData") or {}
    if prev_fd and prev_fd.get("busiId"):
        load_fd = dict(prev_fd)
        load_fd["currCompUrl"] = comp_url
    else:
        load_fd = pb._base_flow_data(c.ent_type, c.name_id, comp_url,
                                         busi_id=_establish_busi_id(c))
    if prev_ld and prev_ld.get("busiCompComb"):
        load_ld = dict(prev_ld)
        load_ld["compUrl"] = comp_url
        load_ld["opeType"] = "load"
        load_ld["compUrlPaths"] = [parent, comp_url] if parent else [comp_url]
    else:
        load_ld = pb._base_link_data(comp_url, ope_type="load")
        if parent:
            load_ld["compUrlPaths"] = [parent, comp_url]
    if parent:
        load_ld["busiCompUrlPaths"] = _urlp.quote(
            '[{"compUrl":"%s","id":""}]' % parent)
    load_body = {
        "flowData": load_fd,
        "linkData": load_ld,
        "itemId": "",
    }
    print(f"    [DEBUG preload] comp={comp_url}")
    print(f"    [DEBUG preload] load_fd.busiId={load_fd.get('busiId')}")
    print(f"    [DEBUG preload] load_ld.busiCompComb={bool(load_ld.get('busiCompComb'))}")
    print(f"    [DEBUG preload] load_ld.compUrlPaths={load_ld.get('compUrlPaths')}")
    print(f"    [DEBUG preload] prev_ld keys={list(prev_ld.keys()) if prev_ld else 'N/A'}")
    try:
        load_resp = client.post_json(establish_comp_load(comp_url), load_body,
                                       extra_headers=extra_headers)
        code = load_resp.get("code")
        bd = (load_resp.get("data") or {}).get("busiData") or {}
        if code == "00000" and bd:
            c.snapshot[f"{comp_url}_busiData"] = bd
            srv_ld = bd.get("linkData") or {}
            if srv_ld.get("busiCompComb"):
                c.snapshot[f"{comp_url}_srv_linkData"] = srv_ld
            si = bd.get("signInfo")
            if si:
                c.snapshot["last_sign_info"] = str(si)
                c.snapshot[f"{comp_url}_signInfo"] = str(si)
                print(f"    [preload {comp_url}] signInfo={si}")
            else:
                pk = bd.get("pkAndMem")
                print(f"    [preload {comp_url}] code=00000 无signInfo, pkAndMem={'有' if pk else '无'}")
        elif code and code != "00000":
            print(f"    [preload {comp_url}] code={code} — 无 signInfo，保留 last_sign_info")
        return load_resp
    except Exception as e:
        print(f"    [WARN] preload {comp_url} failed: {e}")
        return {"code": "ERROR", "msg": str(e)}


def _preload_component_sign_info(client: "ICPSPClient", c: Phase2Context,
                                   comp_url: str,
                                   extra_headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """★ 浏览器行为模拟：切到新组件前先 loadBusinessDataInfo 拿该组件的 signInfo。

    MemberPost/MemberInfo/ComplementInfo/TaxInvoice/BusinessLicenceWay/YbbSelect/PreElectronicDoc
    等组件没有单独的 load 步骤，但**每个组件都有自己的 signInfo**，save 前必须先 load 一次。
    否则用上一组件的 signInfo 会 D0022/D0003/A0002。
    """
    load_resp = _load_component_with_context(client, c, comp_url, extra_headers=extra_headers)
    bd = (load_resp.get("data") or {}).get("busiData") or {}
    si = bd.get("signInfo")
    return str(si) if si else None


def _post_save_and_track_sign(client: "ICPSPClient", url: str,
                              body: Dict[str, Any], c: Phase2Context,
                              extra_headers: Optional[Dict[str, str]] = None,
                              preload_comp_url: Optional[str] = None) -> Dict[str, Any]:
    """发 save，自动处理动态 signInfo。

    Args:
        preload_comp_url: 若指定，在 save 前先 load 该组件拿最新 signInfo（★ 浏览器行为）
                         如 "MemberPost" / "ComplementInfo" 等。
                         BasicInfo 已有单独的 step14 load，不需要 preload。
    """
    if preload_comp_url:
        _preload_component_sign_info(client, c, preload_comp_url, extra_headers=extra_headers)
        # ★ 不注入 busiCompComb/compCombArr — 真实捕获体证明 save linkData 不应包含这些字段
    _apply_dynamic_sign_info(body, c)
    # ★ DEBUG: dump save body for D0019/A0002 diagnosis
    import json as _json
    print(f"    [DEBUG save] url={url}")
    print(f"    [DEBUG save] flowData.busiId={body.get('flowData',{}).get('busiId')}")
    print(f"    [DEBUG save] flowData.currCompUrl={body.get('flowData',{}).get('currCompUrl')}")
    print(f"    [DEBUG save] linkData.compUrl={body.get('linkData',{}).get('compUrl')}")
    print(f"    [DEBUG save] linkData.busiCompComb={bool(body.get('linkData',{}).get('busiCompComb'))}")
    print(f"    [DEBUG save] linkData.compUrlPaths={body.get('linkData',{}).get('compUrlPaths')}")
    print(f"    [DEBUG save] signInfo={body.get('signInfo')}")
    _pkm = body.get("pkAndMem", {})
    print(f"    [DEBUG save] pkAndMem roles={list(_pkm.keys())} count={sum(len(v) for v in _pkm.values() if isinstance(v, list))}")
    resp = client.post_json(url, body, extra_headers=extra_headers)
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        new_si = bd.get("signInfo")
        if new_si:
            c.snapshot["last_sign_info"] = str(new_si)
        # ★ 存储 save 响应的完整 linkData/flowData，供下一步 preload 使用
        srv_ld = bd.get("linkData") or {}
        if srv_ld:
            c.snapshot["last_save_linkData"] = srv_ld
        srv_fd = bd.get("flowData") or {}
        if srv_fd:
            c.snapshot["last_save_flowData"] = srv_fd
    except Exception:
        pass
    return resp


def step16_memberpost_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """MemberPost save — 4-API 组合操作（真实浏览器流程）。

    ★ 2026-04-25 根因修复：必须先 MemberBaseInfo save 让服务端创建 member 记录，
    再 MemberPool list load 拿 itemId，最后 MemberPost save。
    直接 MemberPost save 会导致 A0002（服务端无 member 记录 → NPE）。

    内部 4 步：
      1. MemberBaseInfo load → 拿 49-key 模板 + signInfo
      2. MemberBaseInfo save（cerNo RSA）→ 服务端创建 member 记录分配 itemId
      3. MemberPool/list load → 拿 member list[0] 含 itemId
      4. MemberPost save → pkAndMem 4 角色 × 完整 member 对象
    """
    import time as _time
    busi_id = _establish_busi_id(c)

    # ════════════════════════════════════════
    # Sub-step 1: MemberBaseInfo load（拿模板）
    # ★ MemberBaseInfo 是 MemberPost 的子组件，compUrlPaths 必须是 ["MemberPost","MemberBaseInfo"]
    # ════════════════════════════════════════
    print("    [step16] sub-1: MemberBaseInfo load ...")
    import urllib.parse as _urlp
    prev_fd = c.snapshot.get("last_save_flowData") or {}
    if prev_fd and prev_fd.get("busiId"):
        mbi_load_fd = dict(prev_fd)
        mbi_load_fd["currCompUrl"] = "MemberBaseInfo"
    else:
        mbi_load_fd = pb._base_flow_data(c.ent_type, c.name_id, "MemberBaseInfo",
                                             busi_id=busi_id)
    mbi_load_ld = pb._base_link_data("MemberBaseInfo", ope_type="load")
    # ★ 子组件特殊路径
    mbi_load_ld["compUrlPaths"] = ["MemberPost", "MemberBaseInfo"]
    mbi_load_ld["busiCompUrlPaths"] = _urlp.quote('[{"compUrl":"MemberPost","id":""}]')
    mbi_load_body = {"flowData": mbi_load_fd, "linkData": mbi_load_ld, "itemId": ""}
    mbi_load_resp = client.post_json(establish_comp_load("MemberBaseInfo"), mbi_load_body,
                                     extra_headers={"Referer": REFERER_CORE})
    mbi_base = {}
    mbi_load_code = mbi_load_resp.get("code")
    if mbi_load_code == "00000":
        mbi_base = (mbi_load_resp.get("data") or {}).get("busiData") or {}
        c.snapshot["MemberBaseInfo_busiData"] = mbi_base
        si = mbi_base.get("signInfo")
        if si:
            c.snapshot["last_sign_info"] = str(si)
            c.snapshot["MemberBaseInfo_signInfo"] = str(si)
    print(f"    [step16] MBI load code={mbi_load_code}, keys={len(mbi_base)}, "
          f"signInfo={mbi_base.get('signInfo')}, itemId={mbi_base.get('itemId','?')}")
    _time.sleep(1.0)

    # ════════════════════════════════════════
    # Sub-step 2: MemberBaseInfo save（服务端创建 member 记录）
    # ════════════════════════════════════════
    print("    [step16] sub-2: MemberBaseInfo save ...")
    mbi_body = pb.build_memberbaseinfo_save_body(
        c.case, mbi_base,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=busi_id,
        user_id=c.user_id,
    )
    # 用动态 signInfo（MemberBaseInfo load 返回的）
    _apply_dynamic_sign_info(mbi_body, c)
    print(f"    [step16] MBI save signInfo={mbi_body.get('signInfo')}")

    mbi_resp = client.post_json(establish_comp_op("MemberBaseInfo"), mbi_body,
                                extra_headers={"Referer": REFERER_CORE})
    mbi_code = mbi_resp.get("code")
    mbi_rt = (mbi_resp.get("data") or {}).get("resultType", "")
    mbi_msg = (mbi_resp.get("data") or {}).get("msg", "")
    print(f"    [step16] MBI save => code={mbi_code} rt={mbi_rt} msg={mbi_msg[:80]}")
    # 记录 signInfo/flowData/linkData
    try:
        mbi_bd = (mbi_resp.get("data") or {}).get("busiData") or {}
        if mbi_bd.get("signInfo"):
            c.snapshot["last_sign_info"] = str(mbi_bd["signInfo"])
        if mbi_bd.get("linkData"):
            c.snapshot["last_save_linkData"] = mbi_bd["linkData"]
        if mbi_bd.get("flowData"):
            c.snapshot["last_save_flowData"] = mbi_bd["flowData"]
    except Exception:
        pass
    if mbi_code != "00000" or mbi_rt not in ("0", ""):
        print(f"    [step16] MBI save 未成功 — 尝试继续")
    _time.sleep(1.5)

    # ════════════════════════════════════════
    # Sub-step 3+4: MemberPost load（拿 pkAndMem + itemId） + save
    # ★ MemberBaseInfo save 后，member 数据在 MemberPost/load 的 pkAndMem 里，
    #   不在 MemberPool/list（list 返回空）。
    # ════════════════════════════════════════
    print("    [step16] sub-3: MemberPost load (get pkAndMem + itemId) ...")
    _preload_component_sign_info(client, c, "MemberPost",
                                 extra_headers={"Referer": REFERER_CORE})

    # 从 MemberPost load 的 pkAndMem 提取 raw_member（含真实 itemId）
    raw_member = None
    preload_bd = c.snapshot.get("MemberPost_busiData") or {}
    pk = preload_bd.get("pkAndMem") or {}
    for role_key in ("FR05", "WTDLR", "LLY", "CWFZR"):
        members = pk.get(role_key)
        if isinstance(members, list) and members:
            raw_member = members[0]
            item_id = raw_member.get("itemId") or ""
            c.snapshot["memberpool_raw_member"] = raw_member
            c.snapshot["memberpool_item_id"] = str(item_id)
            print(f"    [step16] pkAndMem.{role_key}[0].itemId={item_id}, name={raw_member.get('name','?')}")
            break
    if not raw_member:
        print("    [WARN] MemberPost load pkAndMem 无 member — fallback to case")
    _time.sleep(1.0)

    print("    [step16] sub-4: MemberPost save ...")
    body = pb.build_memberpost_save_body(
        c.case, raw_member=raw_member,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=busi_id,
        user_id=c.user_id,
    )
    # 合并服务端 linkData + 动态 signInfo
    srv_ld = c.snapshot.get("MemberPost_srv_linkData") or {}
    if srv_ld and "linkData" in body:
        for k in ("busiCompComb", "compCombArr"):
            if srv_ld.get(k) is not None:
                body["linkData"][k] = srv_ld[k]
        if srv_ld.get("compUrlPaths"):
            body["linkData"]["compUrlPaths"] = srv_ld["compUrlPaths"]
    _apply_dynamic_sign_info(body, c)

    # DEBUG
    print(f"    [DEBUG save] signInfo={body.get('signInfo')}")
    _pkm = body.get("pkAndMem", {})
    for rk, rv in _pkm.items():
        if rv and isinstance(rv, list):
            print(f"    [DEBUG save] pkAndMem.{rk}[0].itemId={rv[0].get('itemId','?')}")

    resp = client.post_json(establish_comp_op("MemberPost"), body,
                            extra_headers={"Referer": REFERER_CORE})
    # 记录响应状态
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        new_si = bd.get("signInfo")
        if new_si:
            c.snapshot["last_sign_info"] = str(new_si)
        srv_ld_resp = bd.get("linkData") or {}
        if srv_ld_resp:
            c.snapshot["last_save_linkData"] = srv_ld_resp
        srv_fd_resp = bd.get("flowData") or {}
        if srv_fd_resp:
            c.snapshot["last_save_flowData"] = srv_fd_resp
    except Exception:
        pass
    return resp


def step17_memberpool_list_load(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """MemberPool/loadBusinessInfoList — 拉取成员列表，用于 step 18 的 raw_member。

    成功后把 list[0] 存到 snapshot["memberpool_raw_member"]。
    """
    body = {
        "flowData": pb._base_flow_data(c.ent_type, c.name_id, "MemberPool",
                                           busi_id=_establish_busi_id(c)),
        "linkData": pb._base_link_data("MemberPool", ope_type="", continue_flag=""),
        "itemId": "",
    }
    body["linkData"].pop("continueFlag", None)
    resp = client.post_json(establish_comp_list("MemberPool"), body,
                              extra_headers={"Referer": REFERER_CORE})
    try:
        data = resp.get("data") or {}
        bd = data.get("busiData") or {}
        lst = bd.get("list") or []
        if lst:
            c.snapshot["memberpool_raw_member"] = lst[0]
            c.snapshot["memberpool_item_id"] = str(lst[0].get("itemId") or "")
            print(f"    [captured memberpool member0 itemId] {c.snapshot['memberpool_item_id']}")
    except Exception:
        pass
    return resp


def step18_memberinfo_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """MemberInfo save（池内）— 成员详情：politicsVisage + agentMemPartDto + gdMemPartDto。

    ★ 2026-04-25 修复：必须先 MemberInfo/load（带 itemId）拿完整模板，再填充 save。
    空 itemId load 只返回空模板，save 时服务端找不到 member → A0002。
    """
    import time as _time
    import urllib.parse as _urlp

    item_id = c.snapshot.get("memberpool_item_id") or ""
    busi_id = _establish_busi_id(c)

    # ── Step 1: MemberInfo load（带 itemId 拿完整 member 模板） ──
    print(f"    [step18] MemberInfo load (itemId={item_id}) ...")
    prev_fd = c.snapshot.get("last_save_flowData") or {}
    if prev_fd and prev_fd.get("busiId"):
        mi_load_fd = dict(prev_fd)
        mi_load_fd["currCompUrl"] = "MemberInfo"
    else:
        mi_load_fd = pb._base_flow_data(c.ent_type, c.name_id, "MemberInfo",
                                            busi_id=busi_id)
    mi_load_ld = pb._base_link_data("MemberInfo", ope_type="load", parents=["MemberPool"])
    mi_load_body = {"flowData": mi_load_fd, "linkData": mi_load_ld, "itemId": item_id}
    mi_load_resp = client.post_json(establish_comp_load("MemberInfo"), mi_load_body,
                                    extra_headers={"Referer": REFERER_CORE})
    mi_load_code = mi_load_resp.get("code")
    mi_base = {}
    if mi_load_code == "00000":
        mi_base = (mi_load_resp.get("data") or {}).get("busiData") or {}
        si = mi_base.get("signInfo")
        if si:
            c.snapshot["last_sign_info"] = str(si)
            c.snapshot["MemberInfo_signInfo"] = str(si)
        srv_ld = mi_base.get("linkData") or {}
        if srv_ld.get("busiCompComb"):
            c.snapshot["MemberInfo_srv_linkData"] = srv_ld
    print(f"    [step18] MemberInfo load code={mi_load_code}, keys={len(mi_base)}, "
          f"signInfo={mi_base.get('signInfo')}")
    _time.sleep(1.0)

    # ── Step 2: 用 load 返回的完整模板构建 save body ──
    raw = mi_base if mi_base else (c.snapshot.get("memberpool_raw_member") or {})
    if not raw:
        raw = {"itemId": item_id}
    body = pb.build_memberinfo_save_body(
        c.case, raw,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=busi_id,
        item_id=item_id,
        user_id=c.user_id,
    )

    # ── Step 3: 合并服务端 linkData + 动态 signInfo + post ──
    srv_ld = c.snapshot.get("MemberInfo_srv_linkData") or {}
    if srv_ld and "linkData" in body:
        for k in ("busiCompComb", "compCombArr"):
            if srv_ld.get(k) is not None:
                body["linkData"][k] = srv_ld[k]
    _apply_dynamic_sign_info(body, c)

    print(f"    [step18] MemberInfo save signInfo={body.get('signInfo')}, itemId={body.get('itemId')}")
    resp = client.post_json(establish_comp_op("MemberInfo"), body,
                            extra_headers={"Referer": REFERER_CORE})
    # 记录响应
    mi_rt = ""
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        mi_rt = str((resp.get("data") or {}).get("resultType", ""))
        if bd.get("signInfo"):
            c.snapshot["last_sign_info"] = str(bd["signInfo"])
        if bd.get("linkData"):
            c.snapshot["last_save_linkData"] = bd["linkData"]
        if bd.get("flowData"):
            c.snapshot["last_save_flowData"] = bd["flowData"]
    except Exception:
        pass

    # ── Step 4: MemberPool advance（从 MemberInfo 子组件回到 MemberPool 推进到 ComplementInfo）──
    # ★ MemberInfo 是 MemberPool 的子组件，save 后服务端仍停在 MemberInfo。
    #   必须再发一次 MemberPool save（空体推进）才能推进到 ComplementInfo，否则 D0009。
    if resp.get("code") == "00000" and mi_rt in ("0", ""):
        _time.sleep(1.5)
        print("    [step18] MemberPool advance save ...")
        _preload_component_sign_info(client, c, "MemberPool",
                                     extra_headers={"Referer": REFERER_CORE})
        mp_body = pb.build_empty_advance_save_body(
            "MemberPool", ent_type=c.ent_type, name_id=c.name_id,
            busi_id=busi_id,
            user_id=c.user_id,
        )
        _apply_dynamic_sign_info(mp_body, c)
        # 合并服务端 linkData
        mp_srv_ld = c.snapshot.get("last_save_linkData") or {}
        if mp_srv_ld and "linkData" in mp_body:
            for k in ("busiCompComb", "compCombArr"):
                if mp_srv_ld.get(k) is not None:
                    mp_body["linkData"][k] = mp_srv_ld[k]
        mp_resp = client.post_json(establish_comp_op("MemberPool"), mp_body,
                                   extra_headers={"Referer": REFERER_CORE})
        mp_code = mp_resp.get("code")
        mp_rt = (mp_resp.get("data") or {}).get("resultType", "")
        print(f"    [step18] MemberPool advance => code={mp_code} rt={mp_rt}")
        # 更新 snapshot
        try:
            mp_bd = (mp_resp.get("data") or {}).get("busiData") or {}
            if mp_bd.get("signInfo"):
                c.snapshot["last_sign_info"] = str(mp_bd["signInfo"])
            if mp_bd.get("linkData"):
                c.snapshot["last_save_linkData"] = mp_bd["linkData"]
            if mp_bd.get("flowData"):
                c.snapshot["last_save_flowData"] = mp_bd["flowData"]
        except Exception:
            pass
        # 如果 MemberPool advance 成功，返回它的响应；否则返回 MemberInfo 的响应
        if mp_code == "00000" and str(mp_rt) in ("0", ""):
            return mp_resp
    return resp


def step19_complement_info_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """ComplementInfo save — 4540 个人独资，非公党建（全否）。

    ★ 真实浏览器请求体分析（2026-04-25 mitmproxy 捕获）：
    - partyBuildDto 有两层嵌套：otherDto + xzDto
    - estParSign / resParSecSign 等为 boolean false（不是字符串 "2"）
    - numParM 为 integer 0（不是字符串 "0"）
    - busiType = "02"（不是 "02_4"）
    - 其他 DTO（signerSupplementInfoDto 等）均为 null
    - linkData.busiCompUrlPaths = "%5B%5D"（不回传 srv 的 busiCompComb）
    """
    hdrs = {"Referer": REFERER_CORE}

    # preload 只为获取动态 signInfo
    _preload_component_sign_info(client, c, "ComplementInfo", extra_headers=hdrs)

    busi_id = _establish_busi_id(c)

    # ★ 按真实捕获结构构造 body
    body: Dict[str, Any] = {
        "signerSupplementInfoDto": None,
        "sendPdfInfoDto":          None,
        "promiseInfoDto":          None,
        "partyBuildDto": {
            "partyBuildFlag": "6",
            "otherDto": {
                "numFormalParM":          None,
                "numProParM":             None,
                "organizationName":       None,
                "parRegisterDate":        None,
                "parIns":                 "1",
                "resParSecSign":          False,
                "djgAsSecretary":         False,
                "entWithPartyBuild":      False,
                "parOrgSecName":          None,
                "parOrgSecTel":           None,
                "encryptedParOrgSecTel":  None,
                "supOrganizationName":    None,
                "estParSign":             False,
                "numParM":                0,
                "numParNmae":             None,
                "parOrgw":                "1",
                "resParMSign":            False,
                "anOrgParSign":           False,
            },
            "xzDto": {
                "estParSign":    False,
                "parIns":        "1",
                "parOrgw":       "1",
                "standardEsFlag": False,
            },
        },
        "guardianInfoDto":    None,
        "extendInfoDto":      None,
        "xzPushGsDto":        None,
        "entAssertDto":       None,
        "authorizedInfoDto":  None,
        "flowData": {
            "busiId":           busi_id,
            "entType":          c.ent_type,
            "busiType":         "02",
            "ywlbSign":         "4",
            "busiMode":         None,
            "nameId":           c.name_id,
            "marPrId":          None,
            "secondId":         None,
            "vipChannel":       None,
            "currCompUrl":      "ComplementInfo",
            "status":           "10",
            "matterCode":       None,
            "interruptControl": None,
        },
        "linkData": {
            "compUrl":           "ComplementInfo",
            "opeType":           "save",
            "compUrlPaths":      ["ComplementInfo"],
            "busiCompUrlPaths":  "%5B%5D",
            "token":             "",
        },
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId":   "",
    }

    _apply_dynamic_sign_info(body, c)
    print(f"    [step19] partyBuildDto.partyBuildFlag=6 (非公党建全否, 布尔类型)")

    resp = client.post_json(establish_comp_op("ComplementInfo"), body, extra_headers=hdrs)
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        new_si = bd.get("signInfo")
        if new_si:
            c.snapshot["last_sign_info"] = str(new_si)
        r_ld = bd.get("linkData") or {}
        if r_ld:
            c.snapshot["last_save_linkData"] = r_ld
        r_fd = bd.get("flowData") or {}
        if r_fd:
            c.snapshot["last_save_flowData"] = r_fd
    except Exception:
        pass
    return resp


def step20_tax_invoice_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """TaxInvoice save — 4540 不是空体，需回传广西税务默认态。"""
    hdrs = {"Referer": REFERER_CORE}
    _preload_component_sign_info(client, c, "TaxInvoice", extra_headers=hdrs)
    tax_bd = c.snapshot.get("TaxInvoice_busiData") or {}
    body = pb.build_taxinvoice_save_body(
        tax_bd,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=_establish_busi_id(c),
        user_id=c.user_id,
    )
    return _post_save_and_track_sign(
        client, establish_comp_op("TaxInvoice"), body, c,
        extra_headers=hdrs,
    )


def step21_sl_upload_material(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """SlUploadMaterial 三步法：
      1. upload 文件 → fileId
      2. special API 绑定 fileId 到 materialCode (cerno 必须小写)
      3. save 推进（如果还有必传材料则多次循环 1-2）

    case.upload_materials 示例：
        [{"code": "176", "name": "租赁合同或其他使用证明", "path": "G:\\\\...\\\\rent.jpg"}]

    如果 case 没配上传项，返回 advance save（跳过）。
    """
    # 优先取 case.upload_materials（显式清单），否则从 case.assets 自动推导
    upload_items = list(c.case.get("upload_materials") or [])
    if not upload_items:
        try:
            from phase2_enums import material_code_for_property, use_mode as _use_mode
        except Exception:
            material_code_for_property = lambda v: "176"
            _use_mode = lambda v, default="02": default
        assets = c.case.get("assets") or {}
        property_use = c.case.get("property_use_mode") or c.case.get("use_mode") or "租赁"
        use_mode_code = _use_mode(property_use)
        property_cert = assets.get("property_cert")
        lease_contract = assets.get("lease_contract")
        domicile_cert = assets.get("domicile_cert")
        if property_cert:
            upload_items.append({
                "code": "175",
                "name": "住所(经营场所)使用证明",
                "path": property_cert,
            })
        if lease_contract:
            upload_items.append({
                "code": material_code_for_property(use_mode_code),
                "name": "租赁合同或其他使用证明",
                "path": lease_contract,
            })
        if (not property_cert) and (not lease_contract) and domicile_cert:
            upload_items.append({
                "code": material_code_for_property(use_mode_code),
                "name": "住所(经营场所)使用证明",
                "path": domicile_cert,
            })
        id_front = assets.get("id_front")
        id_back = assets.get("id_back")
        if id_front:
            upload_items.append({
                "code": "200",
                "name": "投资人身份证(正面)",
                "path": id_front,
            })
        if id_back:
            upload_items.append({
                "code": "200",
                "name": "投资人身份证(反面)",
                "path": id_back,
            })
    hdrs = {"Referer": REFERER_CORE}
    person = c.case.get("person") or {}
    _preload_component_sign_info(client, c, "SlUploadMaterial", extra_headers=hdrs)

    def _sl_sort_id() -> str:
        sl_bd = c.snapshot.get("SlUploadMaterial_busiData") or {}
        return str(
            sl_bd.get("sortId")
            or ((sl_bd.get("businessDataInfo") or {}).get("data") or {}).get("sortId")
            or ((sl_bd.get("data") or {}).get("sortId"))
            or ""
        )

    if not upload_items:
        body = pb.build_sl_upload_save_body(
            sort_id=_sl_sort_id(),
            ent_type=c.ent_type, name_id=c.name_id,
            busi_id=_establish_busi_id(c),
            user_id=c.user_id,
        )
        return _post_save_and_track_sign(
            client, establish_comp_op("SlUploadMaterial"), body, c,
            extra_headers=hdrs,
        )

    results = []
    UPLOAD_URL = "/icpsp-api/v4/pc/common/tools/upload/uploadfile"
    for item in upload_items:
        path = item.get("path")
        code = item.get("code") or "176"
        name = item.get("name") or "租赁合同或其他使用证明"
        if not path or not Path(path).exists():
            results.append({"code": code, "status": "skip", "reason": f"file not found: {path}"})
            continue

        # 1. upload (multipart)
        import time as _t
        with open(path, "rb") as f:
            files = {"file": (Path(path).name, f, "application/octet-stream")}
            # 单独取 auth headers，移除 Content-Type 让 requests 自动设 multipart/form-data
            up_headers = client._headers()
            up_headers.pop("Content-Type", None)
            up_headers["Referer"] = REFERER_CORE
            up_headers["language"] = "CH"
            up_resp = client.s.post(
                client.base + UPLOAD_URL + f"?t={int(_t.time()*1000)}",
                files=files,
                headers=up_headers,
                timeout=60,
            )
        up_j = up_resp.json() if up_resp.content else {}
        file_id = ((up_j.get("data") or {}).get("busiData")) if isinstance(up_j, dict) else None
        if not file_id:
            results.append({"code": code, "status": "upload_fail", "resp": up_j})
            continue

        # 2. special bind
        _preload_component_sign_info(client, c, "SlUploadMaterial", extra_headers=hdrs)
        sp_body = pb.build_sl_upload_special_body(
            file_id=file_id, mat_code=code, mat_name=name,
            id_card_zm_uuid=person.get("id_front_uuid") or None,
            id_card_fm_uuid=person.get("id_back_uuid") or None,
            ent_type=c.ent_type, name_id=c.name_id,
            busi_id=_establish_busi_id(c),
            user_id=c.user_id,
        )
        _apply_dynamic_sign_info(sp_body, c)
        sp_resp = client.post_json(establish_comp_op("SlUploadMaterial"), sp_body,
                                     extra_headers=hdrs)
        results.append({
            "code": code,
            "status": "ok",
            "fileId": file_id,
            "sp_code": sp_resp.get("code"),
            "sp_rt": (sp_resp.get("data") or {}).get("resultType"),
            "sp_msg": (sp_resp.get("data") or {}).get("msg") or sp_resp.get("msg"),
        })
        if sp_resp.get("code") != "00000" or str((sp_resp.get("data") or {}).get("resultType") or "0") != "0":
            if sp_resp.get("data") is None:
                sp_resp["data"] = {}
            sp_resp["data"]["_upload_results"] = results
            return sp_resp

    # 3. 最终 save 推进
    _preload_component_sign_info(client, c, "SlUploadMaterial", extra_headers=hdrs)
    body = pb.build_sl_upload_save_body(
        sort_id=_sl_sort_id(),
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=_establish_busi_id(c),
        user_id=c.user_id,
    )
    final = _post_save_and_track_sign(
        client, establish_comp_op("SlUploadMaterial"), body, c,
        extra_headers=hdrs,
    )
    if final.get("data") is None:
        final["data"] = {}
    final["data"]["_upload_results"] = results
    final["data"]["_sl_sortId"] = body.get("sortId")
    return final


def step22_licence_way_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """BusinessLicenceWay save — 按真实邮寄领照 body 回传。

    2026-04-26 实测：save 返回 00000/rt=0 后服务端 currCompUrl=None
    （YbbSelect 是可选组件，服务端不自动定位到它）。
    下一步 step23 YbbSelect load 可直接访问，无需 producePdf follow-up。
    """
    hdrs = {"Referer": REFERER_CORE}
    _preload_component_sign_info(client, c, "BusinessLicenceWay", extra_headers=hdrs)
    blw_bd = c.snapshot.get("BusinessLicenceWay_busiData") or {}
    body = pb.build_business_licence_way_save_body(
        c.case, blw_bd,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=_establish_busi_id(c),
        user_id=c.user_id,
    )
    return _post_save_and_track_sign(
        client, establish_comp_op("BusinessLicenceWay"), body, c,
        extra_headers=hdrs,
    )


def step23_ybb_select_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """YbbSelect save — isSelectYbb=0 (一般流程，不走云帮办)。"""
    hdrs = {"Referer": REFERER_CORE}
    _preload_component_sign_info(client, c, "YbbSelect", extra_headers=hdrs)
    ybb_bd = c.snapshot.get("YbbSelect_busiData") or {}
    save_resp = _post_save_and_track_sign(
        client,
        establish_comp_op("YbbSelect"),
        pb.build_ybb_select_save_body(
            c.case,
            base=ybb_bd,
            ent_type=c.ent_type, name_id=c.name_id,
            busi_id=_establish_busi_id(c),
            user_id=c.user_id,
        ),
        c,
        extra_headers=hdrs,
    )
    data = save_resp.get("data") or {}
    rt = str(data.get("resultType") or "")
    protocol_extracted = {
        "ybb_transition_mode": "save_then_produce_pdf",
    }
    if save_resp.get("code") != "00000" or rt not in ("0", ""):
        save_resp["_protocol_extracted"] = protocol_extracted
        return save_resp

    # ★ 前端 JS: producePdf(t, n) { t.linkData.token = u(); ... }
    #   t 是当前 flowData/linkData 的完整引用，前端在已有对象上设 token 后直接发
    #   所以 producePdf 的请求体必须包含 save 响应的完整 flowData 和 linkData
    #
    #   ★★ 关键发现：producePdf 之前需要先 load YbbSelect 获取服务端最新状态
    #   前端在 save 成功后，Vue 组件的 flowData 已被 save 响应更新，
    #   然后 producePdf 直接用这个更新后的 flowData 发请求。
    #   我们需要模拟这个行为：先 load YbbSelect 获取最新 flowData，再调 producePdf。

    # Step 1: Load YbbSelect to get fresh flowData/linkData after save
    import time as _time
    _time.sleep(1.0)  # 等待服务端状态刷新
    fresh_load_resp = _load_component_with_context(client, c, "YbbSelect", extra_headers=hdrs)
    fresh_bd = (fresh_load_resp.get("data") or {}).get("busiData") or {}

    # Step 2: 用 fresh load 的数据构建 producePdf body
    pdf_flow_data = copy.deepcopy(
        fresh_bd.get("flowData")
        or c.snapshot.get("last_save_flowData")
        or {}
    )
    # ★ 确保 flowData 有 busiId
    if not pdf_flow_data.get("busiId"):
        pdf_flow_data["busiId"] = _establish_busi_id(c)
    if not pdf_flow_data.get("nameId"):
        pdf_flow_data["nameId"] = c.name_id
    if not pdf_flow_data.get("entType"):
        pdf_flow_data["entType"] = c.ent_type
    if not pdf_flow_data.get("busiType"):
        pdf_flow_data["busiType"] = "02"
    if not pdf_flow_data.get("currCompUrl"):
        pdf_flow_data["currCompUrl"] = "YbbSelect"

    # ★ linkData 用 fresh load 返回的完整对象
    pdf_link_data = copy.deepcopy(
        fresh_bd.get("linkData")
        or c.snapshot.get("last_save_linkData")
        or {}
    )
    pdf_link_data["token"] = c.user_id   # ★ 前端 JS: t.linkData.token = u() = userinfo.user.id
    pdf_link_data["compUrl"] = "YbbSelect"
    if not pdf_link_data.get("compUrlPaths"):
        pdf_link_data["compUrlPaths"] = ["YbbSelect"]
    # continueFlag 清空（producePdf 不需要 continueFlag）
    pdf_link_data["continueFlag"] = ""

    produce_pdf_body = {
        "flowData": pdf_flow_data,
        "linkData": pdf_link_data,
    }
    print(f"    [DEBUG producePdf] flowData.busiId={pdf_flow_data.get('busiId')}")
    print(f"    [DEBUG producePdf] flowData.currCompUrl={pdf_flow_data.get('currCompUrl')}")
    print(f"    [DEBUG producePdf] flowData.status={pdf_flow_data.get('status')}")
    print(f"    [DEBUG producePdf] linkData.token={c.user_id}")
    print(f"    [DEBUG producePdf] linkData keys={list(pdf_link_data.keys())}")
    print(f"    [DEBUG producePdf] fresh_load_code={fresh_load_resp.get('code')}")
    produce_pdf_resp = client.post_json(
        "/icpsp-api/v4/pc/register/establish/producePdf",
        produce_pdf_body,
        extra_headers=hdrs,
    )
    produce_pdf_data = produce_pdf_resp.get("data") or {}
    protocol_extracted.update({
        "ybb_followup_component": "producePdf",
        "ybb_followup_code": str(produce_pdf_resp.get("code") or ""),
        "ybb_followup_result_type": str(produce_pdf_data.get("resultType") or ""),
        "ybb_followup_message": str(produce_pdf_data.get("msg") or produce_pdf_resp.get("msg") or "")[:200],
    })
    if produce_pdf_resp.get("code") == "00000":
        save_resp["_protocol_extracted"] = protocol_extracted
        return save_resp

    if produce_pdf_resp.get("code") in ("D0010", "A0002"):
        protocol_extracted["ybb_followup_accessible"] = False
        if run_ybb_select_general_flow is not None:
            cdp_ret = run_ybb_select_general_flow()
            protocol_extracted["ybb_cdp_fallback"] = cdp_ret

    save_resp["_protocol_extracted"] = protocol_extracted
    return save_resp


def step24_pre_electronic_doc_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """PreElectronicDoc submit — 云帮办提交后显式确认 PreSubmitSuccess。"""
    hdrs = {"Referer": REFERER_CORE}
    preload_resp = _load_component_with_context(client, c, "PreElectronicDoc", extra_headers=hdrs)
    preload_data = preload_resp.get("data") or {}
    preload_bd = preload_data.get("busiData") or {}
    base = preload_bd if isinstance(preload_bd, dict) and preload_bd else {
        "flowData": copy.deepcopy(c.snapshot.get("last_save_flowData") or {}),
        "linkData": copy.deepcopy(c.snapshot.get("last_save_linkData") or {}),
        "signInfo": c.snapshot.get("last_sign_info") or "",
        "itemId": "",
    }
    save_resp = _post_save_and_track_sign(
        client,
        establish_comp_op("PreElectronicDoc"),
        pb.build_pre_electronic_doc_save_body(
            base=base,
            ent_type=c.ent_type,
            name_id=c.name_id,
            busi_id=_establish_busi_id(c),
            user_id=c.user_id,
        ),
        c,
        extra_headers=hdrs,
    )
    save_data = save_resp.get("data") or {}
    save_rt = str(save_data.get("resultType") or "")
    protocol_extracted = {
        "pre_doc_transition_mode": "save_then_load",
        "pre_doc_action_semantics": "pre_submit_ybb",
        "pre_doc_action_label": "云帮办提交",
        "pre_doc_preload_code": str(preload_resp.get("code") or ""),
        "pre_doc_preload_result_type": str(preload_data.get("resultType") or ""),
        "pre_doc_preload_message": str(preload_data.get("msg") or preload_resp.get("msg") or "")[:200],
        "pre_doc_submit_code": str(save_resp.get("code") or ""),
        "pre_doc_submit_result_type": save_rt,
        "pre_doc_submit_message": str(save_data.get("msg") or save_resp.get("msg") or "")[:200],
    }
    if save_resp.get("code") not in ("00000", "D0018") or (save_resp.get("code") == "00000" and save_rt not in ("0", "")):
        save_resp["_protocol_extracted"] = protocol_extracted
        return save_resp

    next_resp = _load_component_with_context(client, c, "PreSubmitSuccess", extra_headers=hdrs)
    next_data = next_resp.get("data") or {}
    next_bd = next_data.get("busiData") or {}
    next_fd = next_bd.get("flowData") or {}
    protocol_extracted.update({
        "pre_doc_followup_component": "PreSubmitSuccess",
        "pre_doc_followup_code": str(next_resp.get("code") or ""),
        "pre_doc_followup_result_type": str(next_data.get("resultType") or ""),
        "pre_doc_followup_message": str(next_data.get("msg") or next_resp.get("msg") or "")[:200],
        "pre_doc_followup_status": str(next_fd.get("status") or ""),
    })
    if next_resp.get("code") == "00000" and isinstance(next_bd, dict) and next_bd:
        merged = copy.deepcopy(next_resp)
        protocol_extracted["pre_doc_followup_accessible"] = True
        merged["_protocol_extracted"] = protocol_extracted
        if next_bd.get("flowData"):
            c.snapshot["last_save_flowData"] = next_bd["flowData"]
        if next_bd.get("linkData"):
            c.snapshot["last_save_linkData"] = next_bd["linkData"]
        if next_bd.get("signInfo"):
            c.snapshot["last_sign_info"] = str(next_bd["signInfo"])
        return merged

    save_resp["_protocol_extracted"] = protocol_extracted
    return save_resp


def step25_pre_submit_success_load(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """PreSubmitSuccess loadBusinessDataInfo — 终点（预提交成功页）。

    这一步只是 load 确认状态，不再有 save。后续 ElectronicDoc（电子签章）需要 CA 证书，超出协议化范围。
    """
    body = {
        "flowData": pb._base_flow_data(c.ent_type, c.name_id, "PreSubmitSuccess",
                                           busi_id=_establish_busi_id(c)),
        "linkData": {"compUrl": "PreSubmitSuccess", "compUrlPaths": ["PreSubmitSuccess"], "token": c.user_id},
        "itemId": "",
    }
    return client.post_json(establish_comp_load("PreSubmitSuccess"), body,
                             extra_headers={"Referer": REFERER_CORE})


def step26_establish_submit(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """establish/submit — 最终提交（从预提交到正式提交审核）。

    前端 JS: $api.flow.submit(body) → POST /{busiType}/submit
    body 结构与 load 相同，linkData.token = userinfo.user.id。
    提交后办件状态变为"待受理"，不可再修改。

    ★ 此步骤默认不执行 — 需在 case 中设置 run_goal 含 "submit" 才会激活。
    """
    hdrs = {"Referer": REFERER_CORE}
    submit_body = {
        "flowData": pb._base_flow_data(c.ent_type, c.name_id, "PreSubmitSuccess",
                                           busi_id=_establish_busi_id(c)),
        "linkData": {
            "compUrl": "PreSubmitSuccess",
            "compUrlPaths": ["PreSubmitSuccess"],
            "token": c.user_id,
        },
        "itemId": "",
    }
    submit_resp = client.post_json(
        "/icpsp-api/v4/pc/register/establish/submit",
        submit_body,
        extra_headers=hdrs,
    )
    return submit_resp


def step13_ybb_select(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """云帮办选择页 — 这是我们的停点（不做任何写入）。
    对齐 mitm 样本 body：
    - flowData 必须含 nameId（从 step 9 captured）
    - 不带 extraDto
    - busiType="02"
    """
    est_bt = _establish_busi_type(c.ent_type)
    bt_short = est_bt.split("_")[0]  # "02"
    ywlb = est_bt.split("_")[1] if "_" in est_bt else "4"
    body = {
        "flowData": {
            "busiId": c.busi_id,
            "entType": c.ent_type,
            "busiType": bt_short,
            "ywlbSign": ywlb,
            "busiMode": None,
            "nameId": c.name_id,   # 关键！D0021 就是因为这个
            "marPrId": None,
            "secondId": None,
            "vipChannel": None,
            "currCompUrl": "YbbSelect",
            "status": "10",
            "matterCode": None,
            "interruptControl": None,
        },
        "linkData": {
            "compUrl": "YbbSelect",
            "compUrlPaths": ["YbbSelect"],
            "token": c.user_id,
        },
        "itemId": "",
    }
    # YbbSelect 在 core.html 上下文调用 — 用匹配 Referer
    return client.post_json(API_YBB_LOAD, body, extra_headers={
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
    })


def step7_save_name_supplement(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """保存补充信息（经营范围 + 承办人 + 住所）。经营范围 AES 加密。

    注意：busiAreaCode/busiAreaName/businessArea/busiAreaData 都要用服务端字典里存在的值，
    否则 rt=1 会导致整个事务回滚（isPromiseLetterFlag 等都不会落库）。
    """
    # 构造经营范围（用字典里已存在的主行业+通用语，避免失配）
    business_area_plain = _build_business_area_plaintext(c.case)
    business_area_enc = aes_encrypt(business_area_plain)
    _biz_area_name = c.case.get("busiAreaName") or "软件开发"
    busi_area_name_enc = aes_encrypt(_biz_area_name)
    busi_area_data_enc = business_area_enc  # 同一数据
    _industry_code = c.case.get("phase1_industry_code") or c.case.get("itemIndustryTypeCode") or "6513"
    _industry_name = c.case.get("phase1_industry_name") or c.case.get("industryTypeName") or "应用软件开发"
    _biz_area_code = c.case.get("busiAreaCode") or "I3006"

    body = {
        "industry": _industry_code,
        "industryName": _industry_name,
        "indChaEntFlag": "0",
        "indRegNo": None,
        "rcMoneyKindCode": "",
        "rcMoneyKindName": "人民币",
        "regCapUSDRate": None,
        "regCapRMBRate": None,
        "investMoney": None,
        "investAmountUSD": None,
        "investAmountRMB": None,
        "busiAreaName": busi_area_name_enc,
        "busiAreaCode": _biz_area_code,
        "genBusiArea": "",
        "businessArea": business_area_enc,
        "busiAreaData": busi_area_data_enc,
        "businessUuid": None,
        "zlBusinessInd": None,
        "orgId": "145090000000000046",
        "orgName": "容西市监所",
        "busiteCodes": "",
        "parentEntName": "",
        "parentBusinessArea": None,
        "parentSign": None,
        "longTerm": None,
        "parentBusinessEndDate": None,
        "certype": None,
        "gtZmUuid": None,
        "gtFmUuid": None,
        "name": None,
        "cerno": None,
        "encryptedCerno": None,
        "phone": None,
        "encryptedPhone": None,
        "registerCapital": str(int(c.case.get("capital_wan") or 10)),  # 10 万
        "regCapitalUSD": None,
        "areaCode": c.dist_code,
        "distCode": c.dist_code,
        "fileSize": "5120",
        "cutImgSize": "5120",
        "havaAdress": None,
        "netNameStr": None,
        "netMessageStr": None,
        "entName": c.full_name,
        "detAddress": "",
        "distCodeArr": list(c.dist_codes),
        "address": c.case.get("address_full") or c.address,
        "allGetAddressInfo": None,
        "estate": {
            "havaCred": False,
            "serialNum": None,
            "cerNo": None,
            "serialType": None,
            "rentalHousing": None,
            "realHouseDistCode": None,
        },
        "xfz": "open",
        "industryId": None,
        "freTraDisFlag": None,
        "agent": _build_agent_block(c),
        "isPromiseLetterFlag": "1",    # 承诺书已确认（必需，否则 A0002）
        "flowData": _flow_data(c, "NameSupplement"),
        "linkData": {
            "compUrl": "NameSupplement",
            "opeType": "save",
            "compUrlPaths": ["NameSupplement"],
            "busiCompUrlPaths": "%5B%5D",
            "token": c.user_id,
        },
        "extraDto": _extra_dto(c),
        "signInfo": "-252238669",
        "itemId": "",
    }
    return client.post_json(API_NSUPP_OP, body)


# ─── 主驱动 ───
def extract_phase1_busi_id() -> Optional[str]:
    if not PHASE1_LATEST.exists():
        return None
    try:
        data = json.loads(PHASE1_LATEST.read_text(encoding="utf-8"))
        bid = ((data.get("final") or {}).get("busi_id")) or None
        return str(bid) if bid else None
    except Exception:
        return None


def _decode(res: Dict[str, Any]) -> Dict[str, Any]:
    """提取常见字段 code/resultType/msg/busiData preview。"""
    code = str(res.get("code") or "")
    data = res.get("data") or {}
    rt = str(data.get("resultType") or "")
    msg = str(data.get("msg") or res.get("msg") or "")
    busi = data.get("busiData") or {}
    return {"code": code, "resultType": rt, "msg": msg, "busiData": busi}


# ════════════════════════════════════════════════════════════════════
# ★ 1151 有限责任公司（自然人独资）专用 step 函数
# ════════════════════════════════════════════════════════════════════
#
# 与 4540 的差异点：
#   - MemberPost: 7 角色, cerNo RSA 加密
#   - MemberInfo: role-specific DTOs (dsMemPartDto/legalPersonMemPartDto/gdMemPartDto/...)
#   - ComplementInfo: 非公党建 + 受益所有人 BenefitUsers（dataAdd.do → BenefitCallback）
#   - Rules: 章程自动生成 + 日期字段
#   - MedicalInsured/YjsRegPrePack: 空体推进（4540 没有这些组件）
# ════════════════════════════════════════════════════════════════════


def step16_1151_memberpost_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 MemberPost save — 4-API 组合操作（与 4540 step16 同理）。

    ★ 根因：直接 MemberPost save 会导致 A0002，服务端没有 member 记录 → NPE。
    必须先 MemberBaseInfo save 让服务端创建 member 记录并分配 itemId。

    内部 4 步：
      1. MemberBaseInfo load → 拿 template + signInfo
      2. MemberBaseInfo save → 服务端创建 member (7 角色 postCode)
      3. MemberPost load → 拿 pkAndMem (含真实 itemId)
      4. MemberPost save → 7 角色 × 完整 member 对象
    """
    import time as _time
    import urllib.parse as _urlp
    busi_id = _establish_busi_id(c)
    hdrs = {"Referer": REFERER_CORE}

    # ═══ Sub-step 1: MemberBaseInfo load ═══
    print("    [step16] sub-1: MemberBaseInfo load ...")
    prev_fd = c.snapshot.get("last_save_flowData") or {}
    if prev_fd and prev_fd.get("busiId"):
        mbi_load_fd = dict(prev_fd)
        mbi_load_fd["currCompUrl"] = "MemberBaseInfo"
    else:
        mbi_load_fd = pb._base_flow_data(c.ent_type, c.name_id, "MemberBaseInfo",
                                             busi_id=busi_id)
    mbi_load_ld = pb._base_link_data("MemberBaseInfo", ope_type="load")
    mbi_load_ld["compUrlPaths"] = ["MemberPost", "MemberBaseInfo"]
    mbi_load_ld["busiCompUrlPaths"] = _urlp.quote('[{"compUrl":"MemberPost","id":""}]')
    mbi_load_body = {"flowData": mbi_load_fd, "linkData": mbi_load_ld, "itemId": ""}
    mbi_load_resp = client.post_json(establish_comp_load("MemberBaseInfo"), mbi_load_body,
                                     extra_headers=hdrs)
    mbi_base = {}
    mbi_load_code = mbi_load_resp.get("code")
    if mbi_load_code == "00000":
        mbi_base = (mbi_load_resp.get("data") or {}).get("busiData") or {}
        c.snapshot["MemberBaseInfo_busiData"] = mbi_base
        si = mbi_base.get("signInfo")
        if si:
            c.snapshot["last_sign_info"] = str(si)
            c.snapshot["MemberBaseInfo_signInfo"] = str(si)
    print(f"    [step16] MBI load code={mbi_load_code}, keys={len(mbi_base)}, "
          f"signInfo={mbi_base.get('signInfo')}, itemId={mbi_base.get('itemId','?')}")
    _time.sleep(1.0)

    # ═══ Sub-step 2: MemberBaseInfo save ═══
    print("    [step16] sub-2: MemberBaseInfo save ...")
    mbi_body = pb.build_memberbaseinfo_save_body(
        c.case, mbi_base,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=busi_id,
        user_id=c.user_id,
    )
    _apply_dynamic_sign_info(mbi_body, c)
    print(f"    [step16] MBI save signInfo={mbi_body.get('signInfo')}, postCode={mbi_body.get('postCode')}")
    mbi_resp = client.post_json(establish_comp_op("MemberBaseInfo"), mbi_body,
                                extra_headers=hdrs)
    mbi_code = mbi_resp.get("code")
    mbi_rt = (mbi_resp.get("data") or {}).get("resultType", "")
    mbi_msg = (mbi_resp.get("data") or {}).get("msg", "")
    print(f"    [step16] MBI save => code={mbi_code} rt={mbi_rt} msg={mbi_msg[:80]}")
    try:
        mbi_bd = (mbi_resp.get("data") or {}).get("busiData") or {}
        if mbi_bd.get("signInfo"):
            c.snapshot["last_sign_info"] = str(mbi_bd["signInfo"])
        if mbi_bd.get("linkData"):
            c.snapshot["last_save_linkData"] = mbi_bd["linkData"]
        if mbi_bd.get("flowData"):
            c.snapshot["last_save_flowData"] = mbi_bd["flowData"]
    except Exception:
        pass
    if mbi_code != "00000" or mbi_rt not in ("0", ""):
        print(f"    [step16] MBI save 未成功 — 尝试继续")
    _time.sleep(1.5)

    # ═══ Sub-step 3: MemberPost load (get pkAndMem + itemId) ═══
    print("    [step16] sub-3: MemberPost load (get pkAndMem + itemId) ...")
    _preload_component_sign_info(client, c, "MemberPost", extra_headers=hdrs)

    raw_member = None
    preload_bd = c.snapshot.get("MemberPost_busiData") or {}
    pk = preload_bd.get("pkAndMem") or {}
    from phase2_constants import MEMBERPOST_ROLES_1151 as _ROLES_1151
    for role_key in _ROLES_1151:
        members = pk.get(role_key)
        if isinstance(members, list) and members:
            raw_member = members[0]
            item_id = raw_member.get("itemId") or ""
            c.snapshot["memberpool_raw_member"] = raw_member
            c.snapshot["memberpool_item_id"] = str(item_id)
            print(f"    [step16] pkAndMem.{role_key}[0].itemId={item_id}, name={raw_member.get('name','?')}")
            break
    if not raw_member:
        print("    [WARN] MemberPost load pkAndMem 无 member — fallback to case")
    _time.sleep(1.0)

    # ═══ Sub-step 4: MemberPost save ═══
    print("    [step16] sub-4: MemberPost save (7 roles) ...")
    body = pb.build_memberpost_save_body_1151(
        c.case, raw_member=raw_member,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=busi_id,
        user_id=c.user_id,
        item_id=c.snapshot.get("memberpool_item_id") or "",
    )
    srv_ld = c.snapshot.get("MemberPost_srv_linkData") or {}
    if srv_ld and "linkData" in body:
        for k in ("busiCompComb", "compCombArr"):
            if srv_ld.get(k) is not None:
                body["linkData"][k] = srv_ld[k]
        if srv_ld.get("compUrlPaths"):
            body["linkData"]["compUrlPaths"] = srv_ld["compUrlPaths"]
    _apply_dynamic_sign_info(body, c)

    print(f"    [DEBUG save] signInfo={body.get('signInfo')}")
    _pkm = body.get("pkAndMem", {})
    for rk, rv in _pkm.items():
        if rv and isinstance(rv, list):
            print(f"    [DEBUG save] pkAndMem.{rk}[0].itemId={rv[0].get('itemId','?')}")

    resp = client.post_json(establish_comp_op("MemberPost"), body,
                            extra_headers=hdrs)
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        if bd.get("signInfo"):
            c.snapshot["last_sign_info"] = str(bd["signInfo"])
        srv_ld_resp = bd.get("linkData") or {}
        if srv_ld_resp:
            c.snapshot["last_save_linkData"] = srv_ld_resp
        srv_fd_resp = bd.get("flowData") or {}
        if srv_fd_resp:
            c.snapshot["last_save_flowData"] = srv_fd_resp
    except Exception:
        pass
    return resp


def step18_1151_memberinfo_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 MemberInfo save（池内）— 含 dsMemPartDto/legalPersonMemPartDto/gdMemPartDto 等。

    依赖 step17 的 memberpool_raw_member。
    """
    raw = c.snapshot.get("memberpool_raw_member") or {}
    if not raw:
        raw = {"itemId": c.snapshot.get("memberpool_item_id") or ""}
    body = pb.build_memberinfo_save_body_1151(
        c.case, raw,
        ent_type=c.ent_type, name_id=c.name_id,
        busi_id=_establish_busi_id(c),
        item_id=c.snapshot.get("memberpool_item_id") or "",
        user_id=c.user_id,
    )
    return _post_save_and_track_sign(
        client, establish_comp_op("MemberInfo"), body, c,
        extra_headers={"Referer": REFERER_CORE},
        preload_comp_url="MemberInfo",
    )


def step19_1151_complement_info_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 ComplementInfo save — 含受益所有人 BenefitUsers 处理 + 非公党建。

    ★ 三级策略：
    L1. 先试纯协议 save — 如果服务端已记录受益所有人(断点续跑)，直接通过。
    L2. resultType=1(未填报) → 尝试 HTTP BenefitCallback 回调 → 重试 save。
    L3. L2 失败 → 调用 CDP 驱动浏览器完成 syr iframe 交互 → 重试 save。

    ★ 注意：L3 需要 Edge Dev 已打开且已登录（CDP 端口 9225）。
    """
    hdrs = {"Referer": REFERER_CORE}
    busi_id = _establish_busi_id(c)

    def _do_save() -> Dict[str, Any]:
        """内部辅助：preload + 构造 body + save。"""
        _preload_component_sign_info(client, c, "ComplementInfo", extra_headers=hdrs)
        preloaded = c.snapshot.get("ComplementInfo_busiData") or {}
        body = pb.build_complement_info_save_body_1151(
            c.case, ent_type=c.ent_type, name_id=c.name_id,
            busi_id=busi_id, preloaded_data=preloaded,
            user_id=c.user_id,
        )
        body["flowData"]["currCompUrl"] = "ComplementInfo"
        _apply_dynamic_sign_info(body, c)
        return client.post_json(establish_comp_op("ComplementInfo"), body, extra_headers=hdrs)

    def _is_benefit_block(r: Dict[str, Any]) -> bool:
        d = r.get("data") or {}
        if str(d.get("resultType")) != "1":
            return False
        msg = str(d.get("msg") or "").lower()
        return "受益所有人" in msg or "benefitusers" in msg or "benefit" in msg

    # ── L1：纯协议 save ──
    resp = _do_save()
    if not _is_benefit_block(resp):
        return _track_sign_info_and_return(resp, c)

    # ── L2：HTTP BenefitCallback ──
    print("    [1151 ComplementInfo] 受益所有人未填报 — L2: 尝试 HTTP BenefitCallback...")
    try:
        cb_url = f"{API_BENEFIT_CALLBACK}?busiId={busi_id}"
        cb_resp = client.post_json(cb_url, {}, extra_headers=hdrs)
        print(f"    [BenefitCallback] code={cb_resp.get('code')}")
        resp = _do_save()
        if not _is_benefit_block(resp):
            return _track_sign_info_and_return(resp, c)
    except Exception as e:
        print(f"    [BenefitCallback FAILED] {e}")

    # ── L3：CDP 驱动 syr iframe ──
    if _cdp_benefit_commit is None:
        print("    [1151 ComplementInfo] CDP 模块不可用 — 无法完成受益所有人，跳过")
        return _track_sign_info_and_return(resp, c)

    print("    [1151 ComplementInfo] L3: CDP 驱动 syr iframe 受益所有人流程...")
    cdp_ret = _cdp_benefit_commit(
        busi_id=busi_id,
        name_id=c.name_id,
        ent_type=c.ent_type,
        busi_type=_establish_busi_type(c.ent_type),
    )
    print(f"    [CDP BenefitUsers] success={cdp_ret.get('success')}, stage={cdp_ret.get('stage')}")
    if cdp_ret.get("success"):
        time.sleep(2)
        resp = _do_save()
    else:
        print(f"    [CDP BenefitUsers FAILED] {cdp_ret.get('error')}")
    return _track_sign_info_and_return(resp, c)


def _track_sign_info_and_return(resp: Dict[str, Any], c: Phase2Context) -> Dict[str, Any]:
    """追踪 signInfo 并返回。"""
    try:
        bd = (resp.get("data") or {}).get("busiData") or {}
        new_si = bd.get("signInfo")
        if new_si:
            c.snapshot["last_sign_info"] = str(new_si)
    except Exception:
        pass
    return resp


def step20_1151_rules_save(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 Rules save — 决议及章程（自动生成模式，需日期字段）。

    ★ selectMode=2, temSerial="09-02-rule_rec-111"（单股东不设董事会不设监事会章程）
    ★ 5 个日期字段: invDecideDate, invSignDate, boardDecideDate, boardSignDate, mainRuleSignTime
    """
    body = pb.build_rules_save_body_1151(
        c.case, ent_type=c.ent_type, name_id=c.name_id,
        busi_id=_establish_busi_id(c),
        user_id=c.user_id,
    )
    return _post_save_and_track_sign(
        client, establish_comp_op("Rules"), body, c,
        extra_headers={"Referer": REFERER_CORE},
        preload_comp_url="Rules",
    )


def step21_1151_medical_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 MedicalInsured save — 空体推进（医保信息，无需用户输入）。"""
    body = pb.build_empty_advance_save_body("MedicalInsured",
                                                 ent_type=c.ent_type, name_id=c.name_id,
                                                 busi_id=_establish_busi_id(c),
                                                 user_id=c.user_id)
    return _post_save_and_track_sign(
        client, establish_comp_op("MedicalInsured"), body, c,
        extra_headers={"Referer": REFERER_CORE},
        preload_comp_url="MedicalInsured",
    )


def step22_1151_tax_invoice_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 TaxInvoice save — 空体推进。"""
    body = pb.build_empty_advance_save_body("TaxInvoice",
                                                 ent_type=c.ent_type, name_id=c.name_id,
                                                 busi_id=_establish_busi_id(c),
                                                 user_id=c.user_id)
    return _post_save_and_track_sign(
        client, establish_comp_op("TaxInvoice"), body, c,
        extra_headers={"Referer": REFERER_CORE},
        preload_comp_url="TaxInvoice",
    )


def step23_1151_yjs_prepack_advance(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 YjsRegPrePack save — 空体推进（仅销售预包装食品备案）。"""
    body = pb.build_empty_advance_save_body("YjsRegPrePack",
                                                 ent_type=c.ent_type, name_id=c.name_id,
                                                 busi_id=_establish_busi_id(c),
                                                 user_id=c.user_id)
    return _post_save_and_track_sign(
        client, establish_comp_op("YjsRegPrePack"), body, c,
        extra_headers={"Referer": REFERER_CORE},
        preload_comp_url="YjsRegPrePack",
    )


def step24_1151_sl_upload(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 SlUploadMaterial — 复用 4540 上传逻辑。"""
    return step21_sl_upload_material(client, c)


def step25_1151_licence_way(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 BusinessLicenceWay — 复用 4540 空体推进。"""
    return step22_licence_way_advance(client, c)


def step26_1151_ybb_select(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 YbbSelect — 复用 4540 逻辑。"""
    return step23_ybb_select_save(client, c)


def step27_1151_pre_doc(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 PreElectronicDoc — 复用 4540 空体推进。"""
    return step24_pre_electronic_doc_advance(client, c)


def step28_1151_pre_submit(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """1151 PreSubmitSuccess — 复用 4540 load。"""
    return step25_pre_submit_success_load(client, c)


# ════════════════════════════════════════════════════════════════════
# ★ Phase 2 25 步协议链单一事实源 (Single Source of Truth) ★
#
# 格式：(step_number, display_name, callable, optional)
#   - optional=True 的步骤失败不中断流程（如 YbbSelect 返回 D0021 是正常）
#
# 消费方：
#   - 本模块 run() — CLI 直跑驱动
#   - phase1_service.api.core.phase2_adapter — FastAPI 包装
#   - 其他新增的调用路径（CLI / 脚本）统一从这里读
#
# 历史教训（2026-04-24）：以前 adapter 另有一份 _get_steps_spec，漏同步
# step 16-25，导致 /api/phase2/register start_from=25 走空路径。现在
# 彻底统一到这个常量，禁止任何地方重复定义 step 列表。
# ════════════════════════════════════════════════════════════════════
STEPS_SPEC: List[Tuple[int, str, Any, bool]] = [
    (1, "name/loadCurrentLocationInfo", step1_load_current_location, False),
    (2, "NameSupplement/loadBusinessDataInfo", step2_load_name_supplement, False),
    (3, "NameShareholder/loadBusinessInfoList", step3_load_shareholder_list, False),
    (4, "NameShareholder/loadBusinessDataInfo", step4_load_shareholder_form, False),
    (5, "NameShareholder/operationBusinessDataInfo [save]", step5_save_shareholder, False),
    (6, "NameShareholder/loadBusinessInfoList [reload]", step6_reload_shareholder_list, False),
    (7, "NameSupplement/operationBusinessDataInfo [save]", step7_save_name_supplement, False),
    (8, "name/submit", step8_name_submit, False),
    (9, "NameSuccess/loadBusinessDataInfo", step9_load_name_success, False),
    (10, "matters/operate [108,before]", step10_matters_before, False),
    (11, "matters/operate [108,operate]", step11_matters_operate, False),
    (12, "establish/loadCurrentLocationInfo", step12_establish_location, False),
    (13, "YbbSelect/loadBusinessDataInfo [D0021 optional]", step13_ybb_select, True),
    (14, "establish/BasicInfo/loadBusinessDataInfo", step14_basicinfo_load, False),
    (15, "establish/BasicInfo/operationBusinessDataInfo [save]", step15_basicinfo_save, False),
    (16, "establish/MemberPost/operationBusinessDataInfo [save]", step16_memberpost_save, False),
    (17, "establish/MemberPool/loadBusinessInfoList", step17_memberpool_list_load, True),
    (18, "establish/MemberInfo/operationBusinessDataInfo [save]", step18_memberinfo_save, False),
    (19, "establish/ComplementInfo/operationBusinessDataInfo [save]", step19_complement_info_advance, False),
    (20, "establish/TaxInvoice/operationBusinessDataInfo [save]", step20_tax_invoice_advance, False),
    (21, "establish/SlUploadMaterial [upload+bind+save]", step21_sl_upload_material, False),
    (22, "establish/BusinessLicenceWay/operationBusinessDataInfo [save]", step22_licence_way_advance, False),
    (23, "establish/YbbSelect/operationBusinessDataInfo [save]", step23_ybb_select_save, False),
    (24, "establish/PreElectronicDoc/operationBusinessDataInfo [save]", step24_pre_electronic_doc_advance, False),
    (25, "establish/PreSubmitSuccess/loadBusinessDataInfo [终点]", step25_pre_submit_success_load, False),
    (26, "establish/submit [最终提交]", step26_establish_submit, True),
]


# ════════════════════════════════════════════════════════════════════
# ★ 1151 有限责任公司 29 步协议链 ★
#
# Steps 1-15 与 4540 完全相同（Phase 1 核名 + establish 入口 + BasicInfo）。
# Steps 16-28 是 1151 专用（MemberPost 7 角色 / MemberInfo 复杂 DTOs /
#   ComplementInfo 含受益所有人 / Rules 章程 / MedicalInsured / YjsRegPrePack 等）。
# ════════════════════════════════════════════════════════════════════
STEPS_SPEC_1151: List[Tuple[int, str, Any, bool]] = [
    # ── Phase 1 核名（与 4540 相同） ──
    (1,  "name/loadCurrentLocationInfo", step1_load_current_location, False),
    (2,  "NameSupplement/loadBusinessDataInfo", step2_load_name_supplement, False),
    (3,  "NameShareholder/loadBusinessInfoList", step3_load_shareholder_list, False),
    (4,  "NameShareholder/loadBusinessDataInfo", step4_load_shareholder_form, False),
    (5,  "NameShareholder/operationBusinessDataInfo [save]", step5_save_shareholder, False),
    (6,  "NameShareholder/loadBusinessInfoList [reload]", step6_reload_shareholder_list, False),
    (7,  "NameSupplement/operationBusinessDataInfo [save]", step7_save_name_supplement, False),
    (8,  "name/submit", step8_name_submit, False),
    (9,  "NameSuccess/loadBusinessDataInfo", step9_load_name_success, False),
    (10, "matters/operate [108,before]", step10_matters_before, False),
    (11, "matters/operate [108,operate]", step11_matters_operate, False),
    (12, "establish/loadCurrentLocationInfo", step12_establish_location, False),
    (13, "YbbSelect/loadBusinessDataInfo [D0021 optional]", step13_ybb_select, True),
    (14, "establish/BasicInfo/loadBusinessDataInfo", step14_basicinfo_load, False),
    (15, "establish/BasicInfo/operationBusinessDataInfo [save]", step15_basicinfo_save, False),
    # ── 1151 专用 establish 组件 ──
    (16, "establish/MemberPost/operationBusinessDataInfo [save,1151,7roles]", step16_1151_memberpost_save, False),
    (17, "establish/MemberPool/loadBusinessInfoList", step17_memberpool_list_load, True),
    (18, "establish/MemberInfo/operationBusinessDataInfo [save,1151,DTOs]", step18_1151_memberinfo_save, False),
    (19, "establish/ComplementInfo/operationBusinessDataInfo [save,1151,BenefitUsers]", step19_1151_complement_info_advance, False),
    (20, "establish/Rules/operationBusinessDataInfo [save,1151,章程]", step20_1151_rules_save, False),
    (21, "establish/MedicalInsured/operationBusinessDataInfo [save,1151,空体]", step21_1151_medical_advance, False),
    (22, "establish/TaxInvoice/operationBusinessDataInfo [save,1151,空体]", step22_1151_tax_invoice_advance, False),
    (23, "establish/YjsRegPrePack/operationBusinessDataInfo [save,1151,空体]", step23_1151_yjs_prepack_advance, False),
    (24, "establish/SlUploadMaterial [upload+bind+save]", step24_1151_sl_upload, False),
    (25, "establish/BusinessLicenceWay/operationBusinessDataInfo [save]", step25_1151_licence_way, False),
    (26, "establish/YbbSelect/operationBusinessDataInfo [save]", step26_1151_ybb_select, False),
    (27, "establish/PreElectronicDoc/operationBusinessDataInfo [save]", step27_1151_pre_doc, False),
    (28, "establish/PreSubmitSuccess/loadBusinessDataInfo [终点]", step28_1151_pre_submit, False),
    (29, "establish/submit [最终提交,1151]", step26_establish_submit, True),
]


def get_steps_spec(ent_type: Optional[str] = None) -> List[Tuple[int, str, Any, bool]]:
    """返回指定 entType 的 STEPS_SPEC 浅拷贝。

    Args:
        ent_type: "1151" 返回 STEPS_SPEC_1151（29 步）；
                  其他或 None 返回 STEPS_SPEC（4540 默认 26 步）。

    消费方应该调这个函数，而不是直接引用常量，避免耦合到常量的可变性。
    """
    if ent_type == "1151":
        return list(STEPS_SPEC_1151)
    return list(STEPS_SPEC)


def run(case_path: Path, *, verbose: bool = False, stop_after: int = 4,
         start_from: int = 1, preset_name_id: Optional[str] = None) -> int:
    if not case_path.exists():
        print(f"[phase2] 案件文件不存在: {case_path}")
        return 2

    case = json.loads(case_path.read_text(encoding="utf-8"))
    busi_id = extract_phase1_busi_id()
    if not busi_id:
        print("[phase2] 未在 phase1_protocol_driver_latest.json 中找到 busi_id — 请先跑 Phase 1")
        return 2
    c = Phase2Context.from_case(case, busi_id)
    if preset_name_id:
        c.name_id = preset_name_id

    print("=== Phase 2 纯协议驱动器（阶段 A：读操作 1-4） ===")
    print(f"  busiId      : {c.busi_id}")
    print(f"  entType     : {c.ent_type}")
    print(f"  full_name   : {c.full_name}")
    print(f"  investor    : {c.person_name}  ID={c.person_id_no}")
    print(f"  stop_after  : 步骤 {stop_after}")
    print()

    client = ICPSPClient()

    active_spec = get_steps_spec(c.ent_type)
    max_step = active_spec[-1][0] if active_spec else 25
    print(f"  entType spec : {'1151 有限公司' if c.ent_type == '1151' else '4540 个人独资'} ({len(active_spec)} 步)")
    print()

    steps_out: List[Dict[str, Any]] = []
    exit_code = 0
    for i, name, fn, _optional in active_spec:
        if i < start_from:
            continue
        if i > stop_after:
            break
        t0 = time.time()
        try:
            res = fn(client, c)
            decoded = _decode(res)
            dt = int((time.time() - t0) * 1000)
            rec = {
                "i": i,
                "name": name,
                "ok": decoded["code"] == "00000",
                "code": decoded["code"],
                "resultType": decoded["resultType"],
                "msg": decoded["msg"],
                "duration_ms": dt,
                "busiData_preview": json.dumps(decoded["busiData"], ensure_ascii=False)[:300],
            }
            steps_out.append(rec)
            flag = "OK" if rec["ok"] else "FAIL"
            print(f"[{i}] {name:<50s}  {flag}  code={rec['code']} rt={rec['resultType']} ({dt}ms)")
            if rec["msg"]:
                print(f"    msg: {rec['msg'][:200]}")
            if verbose:
                print(f"    busiData: {rec['busiData_preview']}")
            if decoded["code"] == SESSION_GATE_CODE:
                print("    [session gate] Authorization 失效，请跑 login_qrcode_pure_http --check")
                exit_code = 3
                break
            if decoded["code"] == RATE_LIMIT_CODE:
                print("    [rate limit] D0029 操作频繁 — 等几分钟再重试")
                exit_code = 4
                break
            # rt=1 是"警告"但非失败（Phase 1 经验）；rt=2 是"需用户确认"；rt=0 纯成功
            # 只在 code != 00000 或 rt == '-1' 时视为致命
            # 例外：标注 [optional,*skip*] 的步骤失败可以继续往后跑（如 YbbSelect D0021 对 4540 非必需）
            if decoded["code"] != "00000":
                if "[optional" in name and "skip" in name:
                    print(f"    [optional step] code={decoded['code']} — 跳过继续下一步")
                else:
                    exit_code = 4
                    break
            if decoded["resultType"] in ("-1",):
                exit_code = 4
                break
            # 类人节奏（加密写操作后停更久）
            if "operationBusinessDataInfo" in name or "submit" in name or "operate" in name:
                time.sleep(4.5)   # 关键写操作后 4-5s，模拟思考
            else:
                time.sleep(1.8)    # 读操作 1-2s
        except Exception as e:
            dt = int((time.time() - t0) * 1000)
            rec = {"i": i, "name": name, "ok": False, "err": str(e), "duration_ms": dt}
            steps_out.append(rec)
            print(f"[{i}] {name}  EXCEPTION: {e}")
            exit_code = 4
            break

    # 写结果
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "schema": "ufo.phase2_protocol_driver.v1",
        "started_at_case": str(case_path.relative_to(ROOT) if case_path.is_relative_to(ROOT) else case_path),
        "busi_id": c.busi_id,
        "entType": c.ent_type,
        "full_name": c.full_name,
        "steps": steps_out,
        "stopped_at_step": steps_out[-1]["i"] if steps_out else 0,
        "exit_code": exit_code,
        "notes": "阶段 A (步骤 1-4 读操作)。写步骤 5/7 需先破解 RSA/AES 加密。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {OUT_JSON}")

    if exit_code == 0 and stop_after >= 4:
        print("\n=== 阶段 A 完成 ===")
        print("  接下来需要破解前端加密（身份证 RSA / 经营范围 AES），才能推进步骤 5+")

    return exit_code


def main() -> int:
    p = argparse.ArgumentParser(description="Phase 2 纯协议驱动器（信息补充 → 股东 → 提交 → 设立）")
    p.add_argument("--case", default=str(DEFAULT_CASE), help="案件 JSON 路径")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--stop-after", type=int, default=4, help="跑到第几步停（默认 4 — 阶段 A 读操作全部）")
    p.add_argument("--start-from", type=int, default=1, help="从第几步开始（默认 1）；跳过已完成的 save/submit")
    p.add_argument("--preset-name-id", default=None, help="预填 nameId（当跳过 step 9 时用）")
    args = p.parse_args()
    return run(Path(args.case), verbose=args.verbose, stop_after=args.stop_after,
               start_from=args.start_from, preset_name_id=args.preset_name_id)


if __name__ == "__main__":
    sys.exit(main())
