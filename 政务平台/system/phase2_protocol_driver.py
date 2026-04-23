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
from icpsp_crypto import rsa_encrypt, aes_encrypt  # noqa: E402

OUT_JSON = ROOT / "dashboard" / "data" / "records" / "phase2_protocol_driver_latest.json"
DEFAULT_CASE = ROOT / "docs" / "case_有为风.json"
PHASE1_LATEST = ROOT / "dashboard" / "data" / "records" / "phase1_protocol_driver_latest.json"

SESSION_GATE_CODE = "GS52010103E0302"
PRIVILEGE_CODE = "D0022"
RATE_LIMIT_CODE = "D0029"

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


SIGN_INFO_MAGIC = -252238669  # Phase 1 已验证的固定魔数


@dataclass
class Phase2Context:
    case: Dict[str, Any]
    busi_id: str = ""
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
    # 运行时
    last_http_status: int = 0
    snapshot: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_case(cls, case: Dict[str, Any], busi_id: str) -> "Phase2Context":
        ctx = cls(case=case, busi_id=busi_id)
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
        "linkData": {"token": ""},
    }
    return client.post_json(API_NAME_LOAD_LOC, body)


def step2_load_name_supplement(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    body = {
        "flowData": _flow_data(c, "NameSupplement"),
        "linkData": {
            "compUrl": "NameSupplement",
            "compUrlPaths": ["NameSupplement"],
            "token": "",
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
            "token": "",
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
            "token": "",
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
            "token": "",
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
    """构造经营范围明文 JSON。

    从服务端字典 API (`/common/busiterm/getThirdleveLBusitermList?keyWord=软件&indusTypeCode=6513`)
    确认的合法项：id=I3006, name=软件开发, stateCo=1, indusTypeCode=6511;6512;6513
    """
    items = [
        {
            "id": "I3006",
            "stateCo": "1",    # 字典项默认状态
            "name": "软件开发",
            "pid": "65",
            "minIndusTypeCode": "6511;6512;6513",
            "midIndusTypeCode": "651;651;651",
            "isMainIndustry": "1",
            "category": "I",
            "indusTypeCode": "6511;6512;6513",
            "indusTypeName": "软件开发",
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
            "token": "",
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
            "token": "",
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
    """matters/operate btnCode=101 dealFlag=before（前置检查）。"""
    body = {"busiId": c.busi_id, "btnCode": "101", "dealFlag": "before"}
    return client.post_json(API_MATTERS_OP, body)


def step11_matters_operate(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """matters/operate btnCode=101 dealFlag=operate（真正进入 establish）。"""
    body = {"busiId": c.busi_id, "btnCode": "101", "dealFlag": "operate"}
    return client.post_json(API_MATTERS_OP, body)


def step12_establish_location(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """进入 establish 流程定位（业务从 01 切 02）。对齐 mitm 样本用 nameId。"""
    body = {
        "flowData": {
            "busiType": "02_4",
            "entType": c.ent_type,
            "busiId": c.busi_id,
            "nameId": c.name_id or "",
            "marPrId": "",
        },
        "linkData": {"continueFlag": "continueFlag", "token": ""},
    }
    return client.post_json(API_EST_LOAD_LOC, body)


def step13_ybb_select(client: ICPSPClient, c: Phase2Context) -> Dict[str, Any]:
    """云帮办选择页 — 这是我们的停点（不做任何写入）。
    对齐 mitm 样本 body：
    - flowData 必须含 nameId（从 step 9 captured）
    - 不带 extraDto
    - busiType="02"
    """
    body = {
        "flowData": {
            "busiId": c.busi_id,
            "entType": c.ent_type,
            "busiType": "02",
            "ywlbSign": "4",
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
            "token": "",
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
    busi_area_name_enc = aes_encrypt("软件开发")    # 与字典项 name 一致
    busi_area_data_enc = business_area_enc  # 同一数据

    body = {
        "industry": "6513",
        "industryName": "应用软件开发",
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
        "busiAreaCode": "I3006",
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
            "token": "",
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

    steps_spec = [
        (1, "name/loadCurrentLocationInfo", step1_load_current_location),
        (2, "NameSupplement/loadBusinessDataInfo", step2_load_name_supplement),
        (3, "NameShareholder/loadBusinessInfoList", step3_load_shareholder_list),
        (4, "NameShareholder/loadBusinessDataInfo", step4_load_shareholder_form),
        (5, "NameShareholder/operationBusinessDataInfo [save]", step5_save_shareholder),
        (6, "NameShareholder/loadBusinessInfoList [reload]", step6_reload_shareholder_list),
        (7, "NameSupplement/operationBusinessDataInfo [save]", step7_save_name_supplement),
        (8, "name/submit", step8_name_submit),
        (9, "NameSuccess/loadBusinessDataInfo", step9_load_name_success),
        (10, "matters/operate [101,before]", step10_matters_before),
        (11, "matters/operate [101,operate]", step11_matters_operate),
        (12, "establish/loadCurrentLocationInfo", step12_establish_location),
        (13, "YbbSelect/loadBusinessDataInfo [STOP]", step13_ybb_select),
    ]

    steps_out: List[Dict[str, Any]] = []
    exit_code = 0
    for i, name, fn in steps_spec:
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
            if decoded["code"] != "00000":
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
