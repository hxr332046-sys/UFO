"""NameSupplement + Submit 协议驱动。

基于 phase1_submit_chain_full.json 的真实抓包逆向，实现：
  Step 8: NameSupplement/operationBusinessDataInfo（信息补充保存）
  Step 9: /name/submit（名称登记提交）
  Step 10: NameSuccess/loadBusinessDataInfo（验证申报完成）

依赖：busiId（来自 Phase1 Step 1-7 的 register 端点）
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "system"))

from .rsa_encrypt import rsa_encrypt, rsa_encrypt_fields

# API 路径
API_NS_OP = "/icpsp-api/v4/pc/register/name/component/NameSupplement/operationBusinessDataInfo"
API_NS_LOAD = "/icpsp-api/v4/pc/register/name/component/NameSupplement/loadBusinessDataInfo"
API_SUBMIT = "/icpsp-api/v4/pc/register/name/submit"
API_SUCCESS_LOAD = "/icpsp-api/v4/pc/register/name/component/NameSuccess/loadBusinessDataInfo"


@dataclass
class SupplementInput:
    """信息补充所需的全部输入。"""
    busi_id: str
    ent_type: str = "4540"
    busi_type: str = "01"
    dist_code: str = "450921"
    dist_codes: List[str] = field(default_factory=lambda: ["450000", "450900", "450921"])
    address: str = "广西壮族自治区玉林市容县"

    # 行业
    industry_code: str = "6513"
    industry_name: str = "应用软件开发"

    # 经营范围（来自 scope 端点返回的条目）
    busi_area_items: List[Dict[str, Any]] = field(default_factory=list)
    busi_area_code: str = ""
    busi_area_name: str = ""
    gen_busi_area: str = ""

    # 登记机关
    org_id: str = ""
    org_name: str = ""

    # 注册资本
    register_capital: str = "5"

    # 经办人
    agent_name: str = ""
    agent_cert_type: str = "10"   # 10=身份证
    agent_cert_no: str = ""
    agent_mobile: str = ""

    # entName（完整名称，Phase1 step7 返回）
    ent_name: str = ""

    sign_info: int = -252238669


def _build_flow_data(inp: SupplementInput) -> Dict[str, Any]:
    return {
        "busiId": inp.busi_id,
        "entType": inp.ent_type,
        "busiType": inp.busi_type,
        "ywlbSign": "4",
        "busiMode": None,
        "nameId": None,
        "marPrId": None,
        "secondId": None,
        "vipChannel": "null",
        "currCompUrl": "NameShareholder",
        "status": "10",
        "matterCode": None,
        "interruptControl": None,
    }


def _build_extra_dto(inp: SupplementInput) -> Dict[str, Any]:
    return {
        "entType": inp.ent_type,
        "nameCode": "0",
        "distCode": inp.dist_code,
        "streetCode": None,
        "streetName": None,
        "address": inp.address,
        "rcMoneyKindCode": "",
        "distCodeArr": list(inp.dist_codes),
        "fzSign": "N",
        "parentEntRegno": "",
        "parentEntName": "",
        "regCapitalUSD": "",
    }


def _build_link_data_save() -> Dict[str, Any]:
    return {
        "compUrl": "NameSupplement",
        "opeType": "save",
        "compUrlPaths": ["NameSupplement"],
        "busiCompUrlPaths": "%5B%5D",
        "token": "",
    }


def _build_link_data_submit() -> Dict[str, Any]:
    return {
        "compUrl": "NameSupplement",
        "compUrlPaths": ["NameSupplement"],
        "continueFlag": "",
        "token": "",
    }


def build_supplement_body(inp: SupplementInput) -> Dict[str, Any]:
    """构造 NameSupplement/operationBusinessDataInfo 的请求体。

    敏感字段会 RSA 加密（busiAreaName, businessArea, busiAreaData, agent.certificateNo, agent.mobile）。
    """
    # 经营范围文本
    busi_area_name = inp.busi_area_name or inp.gen_busi_area or ""
    gen_busi_area = inp.gen_busi_area or busi_area_name
    busi_area_data = inp.busi_area_items or []

    # agent（经办人）
    agent: Dict[str, Any] = {
        "isOrgan": None,
        "organName": None,
        "organUnsid": None,
        "organTel": None,
        "encryptedOrganTel": None,
        "agentName": inp.agent_name,
        "certificateType": inp.agent_cert_type,
        "certificateTypeName": None,
        "certificateNo": inp.agent_cert_no,  # 待加密
        "idCardZmUuid": "uploadPluginValue",
        "idCardFmUuid": "uploadPluginValue",
        "encryptedCertificateNo": None,
        "phone": None,
        "encryptedPhone": None,
        "mobile": inp.agent_mobile,  # 待加密
        "encryptedMobile": None,
        "keepStartDate": int(time.time() * 1000),
        "keepEndDate": int(time.time() * 1000) + 91 * 86400 * 1000,  # +91天
        "modifyMaterial": "1",
        "modifyWord": "1",
        "modifyForm": "1",
        "otherModifyItem": "1",
        "license": "1",
        "isLegalPerson": None,
    }
    # RSA 加密经办人敏感字段
    if agent["certificateNo"]:
        agent["certificateNo"] = rsa_encrypt(agent["certificateNo"])
    if agent["mobile"]:
        agent["mobile"] = rsa_encrypt(agent["mobile"])

    body: Dict[str, Any] = {
        "industry": inp.industry_code,
        "industryName": inp.industry_name,
        "indChaEntFlag": "0",
        "indRegNo": None,
        "rcMoneyKindCode": "",
        "rcMoneyKindName": "人民币",
        "regCapUSDRate": None,
        "regCapRMBRate": None,
        "investMoney": None,
        "investAmountUSD": None,
        "investAmountRMB": None,
        "busiAreaName": busi_area_name,    # 待加密
        "busiAreaCode": inp.busi_area_code,
        "genBusiArea": gen_busi_area,       # 前端留空，但实际可能需要值
        "businessArea": gen_busi_area,      # 待加密
        "busiAreaData": json.dumps(busi_area_data, ensure_ascii=False) if busi_area_data else "",  # 待加密
        "businessUuid": None,
        "zlBusinessInd": None,
        "orgId": inp.org_id,
        "orgName": inp.org_name,
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
        "registerCapital": inp.register_capital,
        "regCapitalUSD": None,
        "areaCode": inp.dist_code,
        "distCode": inp.dist_code,
        "fileSize": "5120",
        "cutImgSize": "5120",
        "havaAdress": None,
        "netNameStr": None,
        "netMessageStr": None,
        "entName": inp.ent_name,
        "detAddress": "",
        "distCodeArr": list(inp.dist_codes),
        "address": inp.address,
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
        "agent": agent,
        "isPromiseLetterFlag": "1",
        "flowData": _build_flow_data(inp),
        "linkData": _build_link_data_save(),
        "extraDto": _build_extra_dto(inp),
        "signInfo": str(inp.sign_info),
    }

    # RSA 加密经营范围字段
    rsa_encrypt_fields(body, ["busiAreaName", "businessArea", "busiAreaData"])

    return body


def build_submit_body(inp: SupplementInput) -> Dict[str, Any]:
    """构造 /name/submit 请求体。"""
    return {
        "flowData": _build_flow_data(inp),
        "linkData": _build_link_data_submit(),
        "extraDto": _build_extra_dto(inp),
    }


def build_success_load_body(inp: SupplementInput) -> Dict[str, Any]:
    """构造 NameSuccess/loadBusinessDataInfo 请求体。"""
    flow = _build_flow_data(inp)
    flow["currCompUrl"] = "NameSuccess"
    flow["status"] = "20"
    return {
        "flowData": flow,
        "linkData": {
            "compUrl": "NameSuccess",
            "compUrlPaths": ["NameSuccess"],
            "token": "",
        },
        "extraDto": _build_extra_dto(inp),
        "itemId": "",
    }
