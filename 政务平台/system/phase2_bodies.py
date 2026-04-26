"""Phase 2 establish 组件 save body 构造器。

**设计理念**：不手写 body（易错易漏），而是用 mitm 抓到的**真实成功 save body**作模板，
针对 case 覆盖关键字段。

数据源：
- dashboard/data/records/establish_save_samples/BasicInfo__save.json  （42 keys ground truth）
- dashboard/data/records/establish_save_samples/MemberPost__save.json （8 keys ground truth）
- dashboard/data/records/establish_save_samples/MemberBaseInfo__save.json（48 keys ground truth）
- _archive/_phase2_mi_save_v7.py （MemberInfo 昨天验证成功的 JS body）
- _archive/_phase2_sl_cerno_lower.py（SlUploadMaterial three-step 昨天验证成功的 body）

铁律：
- signInfo 一律 "-1607173598"（SIGN_INFO_ESTABLISH）
- busiId 设为 None（establish 阶段用 nameId 激活，不需要 Phase1 的 busiId）
- entPhone / cerNo 要 RSA 加密（PKCS1v15 Base64）
- businessArea / busiAreaName 是**明文**（不要 AES）
- busiAreaData 是**URL-encoded JSON**（不要 AES）
- 每个组件的 flowData/linkData/compUrlPaths/busiCompUrlPaths 见 phase2_constants
"""
from __future__ import annotations

import copy
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "dashboard" / "data" / "records" / "establish_save_samples"

sys.path.insert(0, str(ROOT / "system"))
from icpsp_crypto import rsa_encrypt  # noqa: E402
from phase2_constants import (  # noqa: E402
    SIGN_INFO_ESTABLISH,
    BUSI_COMP_URL_PATHS_EMPTY,
    BUSI_COMP_URL_PATHS_MEMBERPOOL,
    BUSI_COMP_URL_PATHS_MEMBERPOST,
    BUSI_COMP_URL_PATHS_SLUPLOAD,
    MEMBERPOST_ROLES_1151,
    MEMBERPOST_POSTCODE_1151,
    busi_comp_url_paths,
)


def _load_sample(name: str) -> Dict[str, Any]:
    """加载 establish save 样本（mitm 实录）。若不存在抛错。"""
    f = SAMPLES / f"{name}.json"
    if not f.exists():
        raise FileNotFoundError(
            f"Sample not found: {f}\n"
            f"请先跑 system/_scan_all_establish_samples.py 生成。"
        )
    return json.load(f.open(encoding="utf-8"))["body"]


def _base_flow_data(ent_type: str, name_id: str, curr_comp: str, *,
                    busi_type: str = "02", ywlb_sign: str = "4",
                    busi_id: Optional[str] = None) -> Dict[str, Any]:
    """establish 阶段 flowData 骨架。busi_id 默认 None（establish 激活后由服务端管理）。"""
    return {
        "busiId": busi_id,
        "entType": ent_type,
        "busiType": busi_type,
        "ywlbSign": ywlb_sign,
        "busiMode": None,
        "nameId": name_id,
        "marPrId": None,
        "secondId": None,
        "vipChannel": None,
        "currCompUrl": curr_comp,
        "status": "10",
        "matterCode": None,
        "interruptControl": None,
    }


def _base_link_data(comp_url: str, *,
                     ope_type: str = "save",
                     parents: Optional[List[str]] = None,
                     continue_flag: Optional[str] = None) -> Dict[str, Any]:
    """通用 linkData 骨架。parents 是父组件路径（如 MemberInfo 的父是 ["MemberPool"]）。
    ★ continueFlag 默认 None（不发送）— 真实捕获体证明大多数组件 linkData 不含此字段。
      只有 BasicInfo 第二次 save 时显式传 continue_flag="continueFlag"。
    """
    paths = (parents or []) + [comp_url] if parents else [comp_url]
    ld: Dict[str, Any] = {
        "compUrl": comp_url,
        "opeType": ope_type,
        "compUrlPaths": paths,
        "busiCompUrlPaths": busi_comp_url_paths(parents),
        "token": "",
    }
    if continue_flag is not None:
        ld["continueFlag"] = continue_flag
    return ld


# ==== BasicInfo ====

def build_basicinfo_save_body(case: Dict[str, Any], base: Dict[str, Any],
                                ent_type: str, name_id: str) -> Dict[str, Any]:
    """基于 step14 load 返回的 busiData 基础 + case 覆盖，生成 BasicInfo save body。

    关键字段：
    - name / nameMark / regOrg / regOrgName: 来自 case
    - entPhone: RSA 加密手机号
    - businessArea: 明文
    - busiAreaData: URL-encoded JSON
    - busiAreaName: 明文（行业名）
    - entDomicileDto: load 返回 + case.address 覆盖
    - flowData.busiId = None
    """
    # 从 mitm 真实模板出发
    try:
        tmpl = _load_sample("BasicInfo__save")
    except FileNotFoundError:
        tmpl = {}

    # 优先用 load 返回值，其次 template，其次默认值
    body: Dict[str, Any] = {}
    body.update(tmpl)  # 42 keys from real sample

    # ★ 不要从 load 响应抄 entDomicileDto —— load 返回 190+ 元数据字段（estateType/
    # houseCheck/legalDocDeliverAddress 等服务端内部字段），回传会触发 A0002 "服务端异常"。
    # 真实 mitm save body 的 entDomicileDto 只有 41 字段，直接用 tmpl 里的就是干净的。

    person = case.get("person") or {}
    phone_plain = str(person.get("mobile") or case.get("person_mobile") or "18977514335")
    # 企业全名优先取核名通过后的规范化名（Phase 1 实际保存的名）
    ent_name_plain = (
        case.get("company_name_phase1_normalized")
        or case.get("phase1_check_name")
        or case.get("entName_full")
        or case.get("name_full")
        or case.get("name")
        or case.get("entName")
        or case.get("company_name_full")
        or ""
    )
    name_mark = case.get("name_mark") or case.get("nameMark") or ""
    dist_code = case.get("dist_code") or "450921"
    dist_name = case.get("dist_name") or "玉林市容县"
    address_plain = case.get("address") or "容州镇车站西路富盛广场1幢3203号房"
    post_code = str(case.get("postcode") or "537500")
    reg_org = case.get("regOrg") or case.get("reg_org") or "145090000000000046"
    reg_org_name = case.get("regOrgName") or case.get("reg_org_name") or "容西市监所"
    ent_type_name = case.get("entTypeName") or "个人独资企业"

    # 经营范围
    biz_area_text = case.get("business_area") or \
        "一般经营项目：软件开发（除依法须经批准的项目外，凭营业执照依法自主开展经营活动）"
    biz_area_name = case.get("busiAreaName") or "软件开发"
    biz_area_code = case.get("busiAreaCode") or "I3006"
    item_industry_code = case.get("itemIndustryTypeCode") or "6513"
    industry_name = case.get("industryTypeName") or "应用软件开发"
    area_category = case.get("areaCategory") or "I"

    # busiAreaData：URL-encoded JSON
    biz_area_data_items = case.get("busiAreaData_items") or [{
        "id": biz_area_code,
        "stateCo": "1",
        "name": biz_area_name,
        "pid": "65",
        "minIndusTypeCode": "6511;6512;6513",
        "midIndusTypeCode": "651;651;651",
        "isMainIndustry": "1",
        "category": area_category,
        "indusTypeCode": "6511;6512;6513",
        "indusTypeName": biz_area_name,
        "additionalValue": "",
    }]
    biz_area_data_json = json.dumps(
        {"firstPlace": "general", "param": biz_area_data_items},
        ensure_ascii=False, separators=(",", ":"),
    )
    biz_area_data_url = urllib.parse.quote(biz_area_data_json, safe="")

    # 覆盖业务字段
    body.update({
        "name": ent_name_plain,
        "nameMark": name_mark,
        "namePreFlag": True,
        "entType": ent_type,
        "entTypeName": ent_type_name,
        "entPhone": rsa_encrypt(phone_plain),  # ★ RSA 加密
        "regOrg": reg_org,
        "regOrgName": reg_org_name,
        "postcode": post_code,
        "businessArea": biz_area_text,         # ★ 明文
        "busiAreaName": biz_area_name,         # ★ 明文
        "busiAreaCode": biz_area_code,
        "busiAreaData": biz_area_data_url,     # ★ URL-encoded
        "itemIndustryTypeCode": item_industry_code,
        "industryTypeName": industry_name,
        "areaCategory": area_category,
        "operatorNum": str(case.get("operatorNum") or "1"),
        "accountType": str(case.get("accountType") or "1"),
        "organize": str(case.get("organize") or "1"),
        "businessModeGT": str(case.get("businessModeGT") or "10"),
        "shouldInvestWay": str(case.get("shouldInvestWay") or "01"),
        "subCapital": str(case.get("subCapital") or "10.000000"),
        "licenseRadio": str(case.get("licenseRadio") or "0"),
        "copyCerNum": int(case.get("copyCerNum") or 1),
        "moneyKindCode": "",
        "xfz": "close",
        "secretaryServiceEnt": "0",
    })

    # entDomicileDto 覆盖关键位置字段（保持其它 40 个子字段原样）
    dto = body.get("entDomicileDto") or {}
    if not isinstance(dto, dict):
        dto = {}
    dto.update({
        "distCode": dist_code,
        "distCodeName": dist_name,
        "regionCode": dist_code,
        "regionName": dist_name,
        "detAddress": address_plain,
        "detBusinessAddress": address_plain,
        "address": f"{dist_name}{address_plain}",
        "businessAddress": case.get("businessAddress_full") or \
            f"广西壮族自治区{dist_name}{address_plain}",
    })
    body["entDomicileDto"] = dto

    # 固定元数据 — 用 "BasicInfo"（保守，不进入子模块）
    # 注：mitm 真实样本是 OpManyAddress，但那是因为用户在 UI 里进入了"一址多照"子模块
    # 之后切回 BasicInfo 主表保存；协议化下我们没 load OpManyAddress 子组件，所以保持 BasicInfo
    body["flowData"] = _base_flow_data(ent_type, name_id, "BasicInfo")
    body["linkData"] = _base_link_data("BasicInfo", continue_flag="continueFlag")
    # ★ signInfo 是**动态签名**，每个办件状态唯一。必须回传 step 14 load 返回的值。
    # 硬编码 SIGN_INFO_ESTABLISH 只是 fallback（不同案例 load 签名会不同，D0022 越权的根因）
    # 2026-04-24 修复：之前跑通的 case_有为风 是因为 load 返回值恰巧一致
    body["signInfo"] = str(base.get("signInfo") or SIGN_INFO_ESTABLISH)
    body["itemId"] = ""
    # BasicInfo 真实实录 extraDto=None，不传
    body.pop("extraDto", None)

    return body


# ==== MemberBaseInfo (MemberPost 子组件) ====

def _infer_birthday_from_id(id_no: str) -> Optional[str]:
    """从 18 位身份证号推断生日 YYYY-MM-DD。"""
    if not id_no or len(id_no) < 14:
        return None
    try:
        y, m, d = id_no[6:10], id_no[10:12], id_no[12:14]
        return f"{y}-{m}-{d}"
    except Exception:
        return None


def _infer_sex_from_id(id_no: str) -> Optional[str]:
    """从 18 位身份证号推断性别：倒数第 2 位奇=男(1)偶=女(2)。"""
    if not id_no or len(id_no) < 17:
        return None
    try:
        digit = int(id_no[-2])
        return "1" if digit % 2 == 1 else "2"
    except Exception:
        return None


def build_memberbaseinfo_save_body(case: Dict[str, Any],
                                     base: Dict[str, Any],
                                     *, ent_type: str, name_id: str,
                                     busi_id: Optional[str] = None) -> Dict[str, Any]:
    """MemberBaseInfo save body — 基于 load 响应 base 模板（49 keys）+ case 数据填充。

    mitm 实录：dashboard/data/records/establish_save_samples/MemberBaseInfo__save.json

    关键：
    - body 就是 load 响应的 busiData，修 linkData.opeType 从 "load" → "save"
    - cerNo **RSA 加密**（和 MemberPost 的明文不同）
    - postCode 顺序："FR05,WTDLR,LLY,CWFZR"（和 MemberPost 的 CWFZR,LLY 顺序相反）
    - fieldList / busiComp 原样回传（不动）
    """
    person = case.get("person") or {}
    id_no = person.get("id_no") or person.get("id_card") or person.get("idCard") or ""
    address = case.get("address_full") or person.get("home_address") or person.get("homeAddress") or ""

    body = copy.deepcopy(base) if base else {}

    # ★ 过滤 load 响应里的元数据字段（mitm 样本 save body 里没有）
    # load 返回 49 keys，sample save body 48 keys，差的是 currentLocationVo
    body.pop("currentLocationVo", None)

    # flowData 覆盖核心字段（保持 load 返回的其他字段）
    fd = body.setdefault("flowData", {})
    fd["busiId"] = busi_id
    fd["nameId"] = name_id
    fd["entType"] = ent_type
    fd["busiType"] = "02"
    fd["currCompUrl"] = "MemberBaseInfo"
    fd["status"] = "10"

    # ★ linkData 5-key 干净版（mitm 样本顺序和字段）
    # load 返回的 linkData 含 busiCompComb/compCombArr/continueFlag 等 save 时不需要
    body["linkData"] = {
        "compUrl": "MemberBaseInfo",
        "opeType": "save",
        "compUrlPaths": ["MemberPost", "MemberBaseInfo"],
        "busiCompUrlPaths": urllib.parse.quote('[{"compUrl":"MemberPost","id":""}]'),
        "token": "",
    }

    # 业务字段填充（覆盖 load 返回的 null）
    body["naturalFlag"] = "1"
    body["name"] = person.get("name") or ""
    body["nationalityCode"] = "156"
    body["nationalityCodeName"] = "中国"
    body["cerType"] = "10"  # 居民身份证
    # ★ cerNo RSA 加密（和 MemberPost 的明文不同）
    body["cerNo"] = rsa_encrypt(id_no) if id_no else ""
    body["encryptedCerNo"] = None
    body["permitType"] = None
    body["permitCode"] = None
    body["encryptedPermitCode"] = None
    # ★ postCode 按 entType 区分
    # 1151: 去掉 JS01（监事不能兼任董事/法人/高管，MBI save 会校验）
    #   MemberPost save 才加回 JS01（该层不校验兼职冲突）
    if ent_type == "1151":
        body["postCode"] = "GD01,DS01,CWFZR,FR01,LLY,WTDLR"  # 6 角色，不含 JS01
    else:
        body["postCode"] = "FR05,WTDLR,LLY,CWFZR"  # 4540 MemberBaseInfo 顺序
    body["comeNameFlag"] = "0"
    body["fzSign"] = "N"
    body["homeAddress"] = address
    # personImgDto — 身份证照片 UUID
    # 优先从 case.person 读（如果 case 有配真实上传 UUID），否则用已知可用的 UUID
    # （2026-04-23 通过 CDP 上传黄永裕身份证 OCR 成功的 UUID）
    img_zm = person.get("id_front_uuid") or "38daaa84894646fa9ccdd1acf97eaba2"
    img_fm = person.get("id_back_uuid") or "a6df4e5ebd1f49ccabe0203eb6361c1d"
    body["personImgDto"] = {"uuidfm": img_fm, "uuidzm": img_zm}
    body["pkAndMem"] = None
    body["delPostCode"] = None
    body["id"] = None
    body["sexCode"] = _infer_sex_from_id(id_no) or "1"
    body["nation"] = None
    body["nationName"] = None
    body["birthday"] = _infer_birthday_from_id(id_no) or ""
    body["certificateGrantor"] = None
    body["signDateStart"] = None
    body["signDate"] = None
    body["effectiveFlagTim"] = None
    body["ocrFlag"] = None
    body["isLoginInfo"] = "1"
    body["invType"] = None  # ★ sample 是 null（不是自然人投资的"1"）

    # itemId 保持 load 返回的（首次为 ""，save 后服务端分配）
    if "itemId" not in body:
        body["itemId"] = ""

    # ★ signInfo 用硬编码 SIGN_INFO_ESTABLISH（mitm 样本是 -1607173598）
    # 不是 BasicInfo save 那种"回传 load signInfo"的模式
    body["signInfo"] = str(SIGN_INFO_ESTABLISH)

    return body


# ==== MemberPost ====

# MemberPost pkAndMem 里每个 member 对象的 16 个 null 元数据字段（mitm 实录）
_MEMBER_NULL_META = (
    "flowData", "processVo", "jurisdiction", "currentLocationVo",
    "producePdfVo", "returnModifyVo", "transferToOfflineVo",
    "preSubmitVo", "submitVo", "page", "list", "fieldList",
    "busiComp", "subBusiCompMap", "signInfo", "operationResultVo",
    "signRandomCode", "extraDto",
)

# MemberPost member 对象的 linkData 骨架（8 key 全 null）
_MEMBER_LINKDATA_NULL = {
    "token": None, "continueFlag": None, "compUrl": None,
    "compUrlPaths": None, "busiCompComb": None, "compCombArr": None,
    "opeType": None, "busiCompUrlPaths": None,
}


def _build_memberpost_member_obj(raw_member: Optional[Dict[str, Any]],
                                    case: Dict[str, Any],
                                    post_code: str) -> Dict[str, Any]:
    """构造 MemberPost.pkAndMem 里每个 role 槽位用的完整 43-key member 对象。

    基于 mitm 实录 `dashboard/data/records/establish_save_samples/MemberPost__save.json`：
    - 16 个 null 元数据字段（flowData/processVo/...）
    - linkData 对象（8 key 全 null）
    - itemId 从 raw_member 取
    - 27 个业务字段（name/cerNo/nationalityCode/postCode/...）
    """
    raw = raw_member or {}
    person = case.get("person") or {}
    m: Dict[str, Any] = {}
    # 16 个 null 元数据
    for fn in _MEMBER_NULL_META:
        m[fn] = None
    # linkData 对象（不能是 None）
    m["linkData"] = dict(_MEMBER_LINKDATA_NULL)
    # itemId — MemberPool/list 分配（step 17 捕获）
    m["itemId"] = str(raw.get("itemId") or "")
    # 27 个业务字段
    m["naturalFlag"] = raw.get("naturalFlag") or "1"
    m["name"] = raw.get("name") or person.get("name") or case.get("name") or ""
    m["nationalityCode"] = raw.get("nationalityCode") or "156"
    m["nationalityCodeName"] = raw.get("nationalityCodeName") or "中国"
    m["cerType"] = raw.get("cerType") or "10"
    # cerNo：MemberPost body 里是**明文**（不是 RSA 密文，和 MemberBaseInfo 不同）
    # 读取顺序：raw.cerNo > case.person.id_no > id_card > idCard
    m["cerNo"] = (raw.get("cerNo") or person.get("id_no") or
                    person.get("id_card") or person.get("idCard") or "")
    m["encryptedCerNo"] = None
    m["permitType"] = raw.get("permitType")
    m["permitCode"] = raw.get("permitCode")
    m["encryptedPermitCode"] = None
    m["postCode"] = post_code
    m["comeNameFlag"] = raw.get("comeNameFlag") or "0"
    m["fzSign"] = raw.get("fzSign")  # mitm: null
    # homeAddress: mitm 样本为 null（4540 个独不填地址）
    m["homeAddress"] = raw.get("homeAddress")
    # personImgDto: mitm 样本为 null（MemberPost 不需要照片，MemberInfo 才需要）
    m["personImgDto"] = raw.get("personImgDto")
    m["pkAndMem"] = None
    m["delPostCode"] = None
    m["sexCode"] = raw.get("sexCode")
    m["nation"] = raw.get("nation")
    m["nationName"] = raw.get("nationName")
    m["birthday"] = raw.get("birthday")
    m["certificateGrantor"] = raw.get("certificateGrantor")
    m["signDateStart"] = raw.get("signDateStart")
    m["signDate"] = raw.get("signDate")
    m["effectiveFlagTim"] = raw.get("effectiveFlagTim")
    m["ocrFlag"] = raw.get("ocrFlag")
    m["isLoginInfo"] = raw.get("isLoginInfo") or "1"
    m["invType"] = raw.get("invType")
    return m


def build_memberpost_save_body(case: Dict[str, Any],
                                  raw_member: Optional[Dict[str, Any]] = None,
                                  *,
                                  ent_type: str, name_id: str,
                                  busi_id: Optional[str] = None) -> Dict[str, Any]:
    """MemberPost save：设定组织架构（是否董事会/监事会 + 成员角色）。

    个人独资：board=0 / boardSup=0，pkAndMem 里 FR05（法定代表人，即投资人）, WTDLR（委托代理人）,
    CWFZR（财务负责人）, LLY（联络员）— 同一自然人兼多职。

    Args:
        raw_member: 从 MemberPool/list load 返回的 list[0]，提供完整成员字段（itemId/cerNo/name/...）
                   若为 None，用 case 数据构造 minimal 字段（可能 save 失败）。

    Body 结构（mitm 实录 MemberPost__save.json）：
    - 顶层 8 key：entName/board/boardSup/pkAndMem/flowData/linkData/signInfo/itemId
    - pkAndMem 每个 role 数组里是 43-key 完整 member 对象
    - postCode 顺序：FR05,WTDLR,CWFZR,LLY（★ 样本真实顺序）
    - 身份证号是**明文**（和 MemberBaseInfo save 的 RSA 密文不同）
    """
    ent_name = (case.get("phase1_check_name") or case.get("company_name_phase1_normalized")
                or case.get("entName") or case.get("name") or "")
    post_code = "FR05,WTDLR,CWFZR,LLY"  # ★ mitm 样本顺序

    # 4 个角色槽位，每个槽位放一个完整 43-key member 对象的独立副本
    pk_and_mem = {
        role: [copy.deepcopy(_build_memberpost_member_obj(raw_member, case, post_code))]
        for role in ("FR05", "WTDLR", "LLY", "CWFZR")
    }

    body = {
        "entName": ent_name,
        "board": "0",
        "boardSup": "0",
        "pkAndMem": pk_and_mem,
        "flowData": _base_flow_data(ent_type, name_id, "MemberPost", busi_id=busi_id),
        "linkData": _base_link_data("MemberPost"),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": "",
    }
    return body


# ==== MemberInfo（在 MemberPool 里）====

def build_memberinfo_save_body(case: Dict[str, Any], raw_member: Dict[str, Any], *,
                                  ent_type: str, name_id: str,
                                  busi_id: Optional[str] = None,
                                  item_id: str = "") -> Dict[str, Any]:
    """MemberInfo save：成员详情（池内）。

    输入：raw_member 是 MemberInfo/loadBusinessInfoList 返回的 list[0]（成员数据+meta）。

    三件套：politicsVisage="13"(群众) + agentMemPartDto.isOrgan="02"(否) + gdMemPartDto(投资信息)。
    来源：_phase2_mi_save_v7.py 昨天验证成功的 JS body。
    """
    # 过滤 meta
    skip = {"flowData", "linkData", "processVo", "jurisdiction", "currentLocationVo",
            "producePdfVo", "returnModifyVo", "transferToOfflineVo", "preSubmitVo",
            "submitVo", "page", "list", "fieldList", "busiComp", "subBusiCompMap",
            "signInfo", "operationResultVo", "signRandomCode", "extraDto",
            "xzPushGsDto", "itemId", "pkAndMem", "delPostCode", "realEntName"}
    member = {k: copy.deepcopy(v) for k, v in raw_member.items() if k not in skip}

    person = case.get("person") or {}
    member["politicsVisage"] = "13"  # 群众
    member["allInfoFull"] = True
    # ★ 移动电话（服务端校验 "移动电话不能为空"）
    if not member.get("mobilePhone"):
        member["mobilePhone"] = person.get("mobile") or ""

    # agentMemPartDto: 委托代理信息
    agent = member.get("agentMemPartDto") or {}
    if not isinstance(agent, dict):
        agent = {}
    agent["isOrgan"] = "0"  # 不是代理机构
    # ★ 委托有效日期（服务端校验 "指定或者委托的有效日期起/止不能为空"）
    # 注意：不能用 setdefault，因为 load 返回的 key 存在但值为 None
    if not agent.get("keepStartDate"):
        agent["keepStartDate"] = "2026-04-25"
    if not agent.get("keepEndDate"):
        agent["keepEndDate"] = "2030-04-25"
    # ★ 委托权限 5 个 flag（服务端校验 "委托权限未补充完整，请选择"）
    for fld in ("modifyMaterial", "modifyForm", "otherModifyItem", "license", "modifyWord"):
        if not agent.get(fld):
            agent[fld] = "1"
    member["agentMemPartDto"] = agent

    # docAccepterMemPartDto: 送达指定人（empower=人名, accepterType=20）
    dac = member.get("docAccepterMemPartDto") or {}
    if not isinstance(dac, dict):
        dac = {}
    if not dac.get("empower"):
        dac["empower"] = person.get("name") or ""
    if not dac.get("accepterType"):
        dac["accepterType"] = "20"
    member["docAccepterMemPartDto"] = dac

    # gdMemPartDto: 投资信息
    gd_defaults = {
        "shouldInvestMoney": str(case.get("subCapital") or "100000"),
        "shouldInvestWay": "01",
        "investDate": str(case.get("investDate") or "2028-12-31"),
        "moneyRatio": "100.0000",
        "joinDate": str(case.get("joinDate") or "2026-04-24"),
        "invType": "1",
        "invFormType": "1",
        "fromType": "1",
        "foreignOrChinese": "1",
    }
    gd = member.get("gdMemPartDto") or {}
    if not isinstance(gd, dict):
        gd = {}
    for k, v in gd_defaults.items():
        if not gd.get(k):  # 注意：不用 setdefault，因为 load 可能返回 key=None
            gd[k] = v
    member["gdMemPartDto"] = gd

    body = {
        **member,
        "flowData": _base_flow_data(ent_type, name_id, "MemberInfo", busi_id=busi_id),
        "linkData": _base_link_data("MemberInfo", parents=["MemberPool"]),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": item_id or raw_member.get("itemId") or "",
    }
    return body


# ==== 空体推进（BusinessLicenceWay / PreElectronicDoc / MemberPool）====
# ★ ComplementInfo / TaxInvoice 不在此列 — 都有专用 body builder

def build_empty_advance_save_body(comp_url: str, *,
                                     ent_type: str, name_id: str,
                                     busi_id: Optional[str] = None,
                                     parents: Optional[List[str]] = None) -> Dict[str, Any]:
    """空 body 推进：BusinessLicenceWay / PreElectronicDoc 等
    "不需要额外填写，点'保存并下一步'即可"的组件。
    """
    return {
        "flowData": _base_flow_data(ent_type, name_id, comp_url, busi_id=busi_id),
        "linkData": _base_link_data(comp_url, parents=parents),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": "",
    }


def build_pre_electronic_doc_save_body(*,
                                          base: Optional[Dict[str, Any]] = None,
                                          ent_type: str, name_id: str,
                                          busi_id: Optional[str] = None) -> Dict[str, Any]:
    base = base or {}
    flow_data = copy.deepcopy(base.get("flowData") or {})
    if not flow_data:
        flow_data = _base_flow_data(ent_type, name_id, "PreElectronicDoc", busi_id=busi_id)
    flow_data["busiId"] = flow_data.get("busiId") or busi_id
    flow_data["entType"] = flow_data.get("entType") or ent_type
    flow_data["busiType"] = flow_data.get("busiType") or "02"
    flow_data["ywlbSign"] = flow_data.get("ywlbSign") or "4"
    flow_data["nameId"] = flow_data.get("nameId") or name_id
    flow_data["currCompUrl"] = "PreElectronicDoc"
    flow_data["status"] = flow_data.get("status") or "10"

    link_data = copy.deepcopy(base.get("linkData") or {})
    if not link_data:
        link_data = _base_link_data("PreElectronicDoc")
    link_data["compUrl"] = "PreElectronicDoc"
    link_data["opeType"] = "save"
    link_data["compUrlPaths"] = ["PreElectronicDoc"]
    if link_data.get("busiCompUrlPaths") in (None, ""):
        link_data["busiCompUrlPaths"] = BUSI_COMP_URL_PATHS_EMPTY
    if link_data.get("token") is None:
        link_data["token"] = ""

    return {
        "flowData": flow_data,
        "linkData": link_data,
        "signInfo": str(base.get("signInfo") or SIGN_INFO_ESTABLISH),
        "itemId": base.get("itemId") or "",
    }


# ==== TaxInvoice ====

def build_taxinvoice_save_body(base: Dict[str, Any], *,
                                  ent_type: str, name_id: str,
                                  busi_id: Optional[str] = None) -> Dict[str, Any]:
    """TaxInvoice save（4540 广西个人独资）最小成功合同。

    2026-04-25 实网验证：TaxInvoice 不是空体推进。
    最小成功 body 仅需：
    - pageType = "GX"
    - agencyCode = "08"
    - isSsb = "N"
    - taxInvoiceGxVo.isSetUp = "N"
    再加 flowData/linkData/signInfo/itemId。
    """
    gx = (base.get("taxInvoiceGxVo") or {}) if isinstance(base, dict) else {}
    return {
        "pageType": (base.get("pageType") if isinstance(base, dict) else None) or "GX",
        "agencyCode": (base.get("agencyCode") if isinstance(base, dict) else None) or "08",
        "isSsb": (base.get("isSsb") if isinstance(base, dict) else None) or "N",
        "taxInvoiceGxVo": {
            "isSetUp": gx.get("isSetUp") or "N",
        },
        "flowData": _base_flow_data(ent_type, name_id, "TaxInvoice", busi_id=busi_id),
        "linkData": _base_link_data("TaxInvoice"),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": (base.get("itemId") if isinstance(base, dict) else None) or "",
    }


# ==== YbbSelect ====

def build_ybb_select_save_body(case: Dict[str, Any], *,
                                  base: Optional[Dict[str, Any]] = None,
                                  ent_type: str, name_id: str,
                                  busi_id: Optional[str] = None) -> Dict[str, Any]:
    """YbbSelect save：云帮办流程模式。

    2026-04-25 实测：仅传 isSelectYbb='0' 仍会报“请选择业务流程模式”。
    save 需带上 load 返回的 isOptional / preAuditSign / isSelectYbb。
    """
    base = base or {}
    flow_data = copy.deepcopy(base.get("flowData") or {})
    if not flow_data:
        flow_data = _base_flow_data(ent_type, name_id, "YbbSelect", busi_id=busi_id)
    flow_data["busiId"] = flow_data.get("busiId") or busi_id
    flow_data["entType"] = flow_data.get("entType") or ent_type
    flow_data["busiType"] = flow_data.get("busiType") or "02"
    flow_data["ywlbSign"] = flow_data.get("ywlbSign") or "4"
    flow_data["nameId"] = flow_data.get("nameId") or name_id
    flow_data["currCompUrl"] = "YbbSelect"
    flow_data["status"] = flow_data.get("status") or "10"

    server_link_data = copy.deepcopy(base.get("linkData") or {})
    link_data: Dict[str, Any] = {
        "compUrl": "YbbSelect",
        "opeType": "save",
        "compUrlPaths": copy.deepcopy(server_link_data.get("compUrlPaths") or ["YbbSelect"]),
        "busiCompUrlPaths": server_link_data.get("busiCompUrlPaths") or BUSI_COMP_URL_PATHS_EMPTY,
        "token": server_link_data.get("token") if server_link_data.get("token") is not None else "",
    }

    pre_audit_sign = base.get("preAuditSign")
    if pre_audit_sign in (None, ""):
        pre_audit_sign = case.get("preAuditSign")
    if pre_audit_sign in (None, ""):
        pre_audit_sign = "0"
    return {
        "isOptional": str(base.get("isOptional") or case.get("isOptional") or "1"),
        "preAuditSign": pre_audit_sign,
        "isSelectYbb": str(base.get("isSelectYbb") or case.get("isSelectYbb") or "0"),
        "flowData": flow_data,
        "linkData": link_data,
        "signInfo": str(base.get("signInfo") or SIGN_INFO_ESTABLISH),
        "itemId": base.get("itemId") or "",
    }


# ==== SlUploadMaterial ====

def build_sl_upload_special_body(*,
                                    file_id: str,
                                    mat_code: str,
                                    mat_name: str,
                                    id_card_zm_uuid: Optional[str] = None,
                                    id_card_fm_uuid: Optional[str] = None,
                                    ent_type: str, name_id: str,
                                    busi_id: Optional[str] = None) -> Dict[str, Any]:
    """SlUploadMaterial special API body（绑定 fileId 到材料条目）。

    ★ 关键：cerno 必须小写（docs/Phase2完整协议化通达_PreElectronicDoc_20260423.md cerno 教训）。
    """
    body = {
        "type": "upload_save",
        "code": mat_code,              # 如 "176" (租赁合同)、"175" (住所证明)
        "name": mat_name,
        "cerno": None,                 # ★ 小写 n（Jackson 严格匹配字段名）
        "uploadUuid": file_id,
        "zzlx": None,
        "deptCode": None,
        "flowData": _base_flow_data(ent_type, name_id, "SlUploadMaterial", busi_id=busi_id),
        "linkData": {
            "compUrl": "SlUploadMaterial",
            "opeType": "special",
            "compUrlPaths": ["SlUploadMaterial"],
            "continueFlag": "",
            "busiCompUrlPaths": BUSI_COMP_URL_PATHS_SLUPLOAD,
            "token": "",
        },
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": mat_code,             # itemId = code
    }
    if id_card_zm_uuid:
        body["idCardZmUuid"] = id_card_zm_uuid
    if id_card_fm_uuid:
        body["idCardFmUuid"] = id_card_fm_uuid
    return body


def build_sl_upload_save_body(*,
                                 sort_id: str,
                                 ent_type: str, name_id: str,
                                 busi_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "sortId": sort_id,
        "flowData": _base_flow_data(ent_type, name_id, "SlUploadMaterial", busi_id=busi_id),
        "linkData": _base_link_data("SlUploadMaterial"),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": "",
    }


def _split_region_parts(full_address: str) -> Dict[str, str]:
    text = str(full_address or "").strip()
    province = city = area = ""
    m = re.match(r"^(.*?(?:省|自治区|特别行政区|市))(.*?(?:市|州|地区|盟))(.*?(?:区|县|旗|市))", text)
    if m:
        province, city, area = m.groups()
    return {"province": province, "city": city, "area": area}


def build_business_licence_way_save_body(case: Dict[str, Any], base: Dict[str, Any], *,
                                            ent_type: str, name_id: str,
                                            busi_id: Optional[str] = None) -> Dict[str, Any]:
    person = case.get("person") or {}
    mobile = str(person.get("mobile") or "")
    full_address = str(case.get("address_full") or "")
    phase1_dist_codes = case.get("phase1_dist_codes") or []

    express = copy.deepcopy(base.get("expressInfoDto") or {})
    reservation = copy.deepcopy(base.get("reservationDto") or {})
    unify = copy.deepcopy(base.get("unifyReceiverDTO") or {})
    cabinet = copy.deepcopy(base.get("cabinetDto") or {})

    region = _split_region_parts(full_address)
    whole_address = express.get("wholeAddress") or full_address
    if full_address and region["province"] and region["city"] and region["area"]:
        prefix = f"{region['province']}{region['city']}{region['area']}"
        if full_address.startswith(prefix):
            whole_address = express.get("wholeAddress") or full_address[len(prefix):]

    reservation.update({
        "placeId": reservation.get("placeId") or "",
        "placeName": reservation.get("placeName") or "",
        "placeAddress": reservation.get("placeAddress") or "",
        "placeLinkmanPhone": reservation.get("placeLinkmanPhone") or "",
        "applicantName": person.get("name") or reservation.get("applicantName") or "",
        "applicantPhone": rsa_encrypt(mobile) if mobile else "",
        "reserveTime": reservation.get("reserveTime") or "",
        "fieldList": reservation.get("fieldList"),
        "encryptedApplicantPhone": reservation.get("encryptedApplicantPhone") or "",
    })

    unify.update({
        "tel": unify.get("tel") or "",
        "cerType": unify.get("cerType") or "",
        "cerNo": unify.get("cerNo") or "",
        "phone": unify.get("phone") or "",
        "receivedt": unify.get("receivedt"),
        "fieldList": unify.get("fieldList") or [],
        "receiver": unify.get("receiver") or "",
        "encryptedTel": unify.get("encryptedTel") or "",
        "encryptedCerNo": unify.get("encryptedCerNo") or "",
        "encryptedPhone": unify.get("encryptedPhone") or "",
        "organAddress": unify.get("organAddress") or "",
        "email": unify.get("email") or "",
    })

    express.update({
        "receiver": person.get("name") or express.get("receiver") or "",
        "phone": rsa_encrypt(mobile) if mobile else "",
        "tel": express.get("tel") or "",
        "email": express.get("email") or "",
        "cerType": express.get("cerType") or "",
        "cerNo": express.get("cerNo") or "",
        "fieldList": express.get("fieldList") or [],
        "encryptedTel": express.get("encryptedTel") or "",
        "encryptedCerNo": express.get("encryptedCerNo") or "",
        "encryptedPhone": mobile,
        "regionCode": express.get("regionCode") or (phase1_dist_codes[-1] if phase1_dist_codes else ""),
        "regionStreetCode": express.get("regionStreetCode") or "",
        "wholeAddress": whole_address,
        "postcode": express.get("postcode") or case.get("postcode") or "",
        "address": full_address or express.get("address") or whole_address,
        "havePostage": express.get("havePostage") if express.get("havePostage") is not None else False,
        "sendMoney": express.get("sendMoney") or "",
        "isPayType": express.get("isPayType") or "",
        "province": express.get("province") or region["province"],
        "city": express.get("city") or region["city"],
        "area": express.get("area") or region["area"],
        "detailedAddress": express.get("detailedAddress") or "",
    })

    cabinet.update({
        "receiveHallsHkId": cabinet.get("receiveHallsHkId") or "",
        "receiver": cabinet.get("receiver") or "",
        "phone": cabinet.get("phone") or "",
        "encryptedPhone": cabinet.get("encryptedPhone") or mobile,
        "postcode": cabinet.get("postcode") or "",
        "wholeAddress": cabinet.get("wholeAddress") or "",
        "detailedAddress": cabinet.get("detailedAddress") or "",
        "regionCode": cabinet.get("regionCode") or "",
        "province": cabinet.get("province") or "",
        "city": cabinet.get("city") or "",
        "area": cabinet.get("area") or "",
        "encryptedTel": cabinet.get("encryptedTel") or "",
        "encryptedCerNo": cabinet.get("encryptedCerNo") or "",
    })

    return {
        "mainSign": str(base.get("mainSign") or "0"),
        "businessLicenceFlag": str(base.get("businessLicenceFlag") or "1"),
        "oneThingTitleCode": base.get("oneThingTitleCode"),
        "oneThingTitleDesc": base.get("oneThingTitleDesc"),
        "mailingAddressTitleCode": base.get("mailingAddressTitleCode"),
        "mailingAddressTitleDesc": base.get("mailingAddressTitleDesc"),
        "oneThingResultSendWayDtoList": copy.deepcopy(base.get("oneThingResultSendWayDtoList")),
        "businessLicenceWayList": copy.deepcopy(base.get("businessLicenceWayList") or []),
        "needLicense": str(base.get("needLicense") or "0"),
        "copyCerNum": base.get("copyCerNum"),
        "reservationDto": reservation,
        "unifyReceiverDTO": unify,
        "expressInfoDto": express,
        "cabinetDto": cabinet,
        "flowData": _base_flow_data(ent_type, name_id, "BusinessLicenceWay", busi_id=busi_id),
        "linkData": _base_link_data("BusinessLicenceWay"),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": (base.get("itemId") if isinstance(base, dict) else None) or "",
    }


# ════════════════════════════════════════════════════════════════════
# ★ 1151 有限责任公司（自然人独资）专用 body 构造器
# ════════════════════════════════════════════════════════════════════
#
# 与 4540 个人独资的关键区别：
#   - MemberPost: 7 角色 vs 4 角色, cerNo RSA 加密, linkData 含 MemberBaseInfo 路径
#   - MemberInfo: 复杂 role-specific DTOs (dsMemPartDto/legalPersonMemPartDto/gdMemPartDto/...)
#   - ComplementInfo: 需 BenefitUsers（受益所有人）处理 + 非公党建
#   - Rules: 章程自动生成模式, 需填日期字段
#
# 数据源：
#   - dashboard/data/records/1151_monitor_op_MemberPost.json （真实成功 save body）
#   - dashboard/data/records/1151_memberinfo_full_req.json （MemberInfo 完整请求体）
#   - ComplementInfo/Rules: 从 CDP 调试 + SPA 行为逆向
# ════════════════════════════════════════════════════════════════════


def _build_memberpost_member_obj_1151(raw_member: Optional[Dict[str, Any]],
                                       case: Dict[str, Any],
                                       post_code: str,
                                       item_id: str = "") -> Dict[str, Any]:
    """构造 1151 MemberPost.pkAndMem 里每个 role 槽位的完整 member 对象。

    ★ 与 4540 的关键差异：
    - cerNo 必须 RSA 加密（encryptData["MemberPost"] = ["cerNo", "permitCode"]）
    - postCode 是 7 职合一："GD01,DS01,JS01,CWFZR,FR01,LLY,WTDLR"
    - invType = "20"（自然人投资人）
    - personImgDto 必须有真实 UUID（dummy UUID 会导致 A0002）
    """
    raw = raw_member or {}
    person = case.get("person") or {}
    id_no = person.get("id_no") or person.get("id_card") or ""
    m: Dict[str, Any] = {}
    for fn in _MEMBER_NULL_META:
        m[fn] = None
    m["linkData"] = dict(_MEMBER_LINKDATA_NULL)
    m["itemId"] = str(raw.get("itemId") or item_id)
    m["naturalFlag"] = raw.get("naturalFlag") or "1"
    m["name"] = raw.get("name") or person.get("name") or ""
    m["nationalityCode"] = raw.get("nationalityCode") or "156"
    m["nationalityCodeName"] = raw.get("nationalityCodeName") or "中国"
    m["cerType"] = raw.get("cerType") or "10"
    # ★ 临时测试：明文 cerNo（和 4540 一样），排查 RSA 加密是否导致 A0002
    m["cerNo"] = id_no
    m["encryptedCerNo"] = None
    m["permitType"] = raw.get("permitType")
    m["permitCode"] = raw.get("permitCode")
    m["encryptedPermitCode"] = None
    m["postCode"] = post_code
    m["comeNameFlag"] = raw.get("comeNameFlag") or "0"
    m["fzSign"] = raw.get("fzSign")
    m["homeAddress"] = raw.get("homeAddress")
    m["personImgDto"] = raw.get("personImgDto")
    m["pkAndMem"] = None
    m["delPostCode"] = None
    m["sexCode"] = raw.get("sexCode")
    m["nation"] = raw.get("nation")
    m["nationName"] = raw.get("nationName")
    m["birthday"] = raw.get("birthday")
    m["certificateGrantor"] = raw.get("certificateGrantor")
    m["signDateStart"] = raw.get("signDateStart")
    m["signDate"] = raw.get("signDate")
    m["effectiveFlagTim"] = raw.get("effectiveFlagTim")
    m["ocrFlag"] = raw.get("ocrFlag")
    m["isLoginInfo"] = raw.get("isLoginInfo") or "1"
    m["invType"] = raw.get("invType")
    return m


def build_memberpost_save_body_1151(case: Dict[str, Any],
                                      raw_member: Optional[Dict[str, Any]] = None,
                                      *,
                                      ent_type: str = "1151",
                                      name_id: str,
                                      busi_id: Optional[str] = None,
                                      item_id: str = "") -> Dict[str, Any]:
    """1151 MemberPost save：7 角色（GD01/DS01/JS01/CWFZR/FR01/LLY/WTDLR），同一自然人。

    基于 dashboard/data/records/1151_monitor_op_MemberPost.json 真实成功 body。

    ★ 关键差异 vs 4540:
    - 7 角色 vs 4 角色
    - cerNo RSA 加密 vs 明文
    - linkData.compUrlPaths: ["MemberPost", "MemberBaseInfo"]
    - busiCompUrlPaths: [{"compUrl":"MemberPost","id":""}]
    - board=0, boardSup=0 (无董事会/监事会)
    """
    ent_name = (case.get("company_name_phase1_normalized") or
                case.get("name") or case.get("entName") or "")

    pk_and_mem = {
        role: [copy.deepcopy(_build_memberpost_member_obj_1151(
            raw_member, case, MEMBERPOST_POSTCODE_1151, item_id=item_id))]
        for role in MEMBERPOST_ROLES_1151
    }

    body = {
        "entName": ent_name,
        "board": "0",
        "boardSup": "0",
        "pkAndMem": pk_and_mem,
        "flowData": _base_flow_data(ent_type, name_id, "MemberPost", busi_id=busi_id),
        "linkData": {
            "compUrl": "MemberPost",
            "opeType": "save",
            "compUrlPaths": ["MemberPost", "MemberBaseInfo"],
            "continueFlag": "continueFlag",
            "busiCompUrlPaths": BUSI_COMP_URL_PATHS_MEMBERPOST,
            "token": "",
        },
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": item_id,
    }
    return body


def build_memberinfo_save_body_1151(case: Dict[str, Any],
                                      raw_member: Dict[str, Any], *,
                                      ent_type: str = "1151",
                                      name_id: str,
                                      busi_id: Optional[str] = None,
                                      item_id: str = "") -> Dict[str, Any]:
    """1151 MemberInfo save：成员详情（池内），含多个 role-specific DTOs。

    基于 dashboard/data/records/1151_memberinfo_full_req.json 真实成功 body。

    ★ 关键差异 vs 4540:
    - 有 dsMemPartDto（董事）、legalPersonMemPartDto（法人）、financeMemPartDto（财务）
    - agentMemPartDto.isOrgan = "0"（不是代理机构, 4540 用 "02"）
    - gdMemPartDto 含完整投资信息（shouldInvestMoney/moneyRatio/investDate/forAmt/...）
    - dbryMemPartDto.mPosition = "491B"
    - allCapital / board / boardSup / invMany 顶层字段
    - postCode 顺序: "DS01,CWFZR,LLY,FR01,WTDLR,GD01"
    """
    skip = {"flowData", "linkData", "processVo", "jurisdiction", "currentLocationVo",
            "producePdfVo", "returnModifyVo", "transferToOfflineVo", "preSubmitVo",
            "submitVo", "page", "list", "fieldList", "busiComp", "subBusiCompMap",
            "signInfo", "operationResultVo", "signRandomCode", "extraDto",
            "xzPushGsDto", "itemId", "pkAndMem", "delPostCode", "realEntName"}
    member = {k: copy.deepcopy(v) for k, v in raw_member.items() if k not in skip}

    person = case.get("person") or {}

    member["politicsVisage"] = member.get("politicsVisage") or "13"
    member["allInfoFull"] = True

    # dsMemPartDto: 董事信息（不用 setdefault，load 可能返回 key=None）
    ds = member.get("dsMemPartDto")
    if ds and isinstance(ds, dict):
        if not ds.get("timeLimit"): ds["timeLimit"] = 3
        if not ds.get("positionBringMannerCode"): ds["positionBringMannerCode"] = "03"
        if not ds.get("useName"): ds["useName"] = person.get("name") or ""
        if not ds.get("appointOrg"): ds["appointOrg"] = "股东会"
    elif member.get("postCode") and "DS01" in str(member.get("postCode", "")):
        member["dsMemPartDto"] = {
            "timeLimit": 3,
            "positionBringMannerCode": "03",
            "useName": person.get("name") or "",
            "appointOrg": "股东会",
            "accdSide": None, "childPost": "",
            "audiCouncilFlag": None, "mproduceWayName": None,
        }

    # legalPersonMemPartDto: 法人信息
    lp = member.get("legalPersonMemPartDto")
    if lp and isinstance(lp, dict):
        if not lp.get("legalPositionBack"): lp["legalPositionBack"] = "DS01"
    elif member.get("postCode") and "FR01" in str(member.get("postCode", "")):
        member["legalPersonMemPartDto"] = {"legalPositionBack": "DS01"}

    # financeMemPartDto: 财务负责人
    fin = member.get("financeMemPartDto")
    if fin and isinstance(fin, dict):
        if not fin.get("positionBringMannerCode"): fin["positionBringMannerCode"] = "04"
    elif member.get("postCode") and "CWFZR" in str(member.get("postCode", "")):
        member["financeMemPartDto"] = {"positionBringMannerCode": "04"}

    # dbryMemPartDto: 代办人
    db = member.get("dbryMemPartDto")
    if db and isinstance(db, dict):
        if not db.get("mPosition"): db["mPosition"] = "491B"
    else:
        if not member.get("dbryMemPartDto"): member["dbryMemPartDto"] = {"mPosition": "491B"}

    # agentMemPartDto: 委托代理人（1151 用 isOrgan="0"）
    agent = member.get("agentMemPartDto") or {}
    if not isinstance(agent, dict):
        agent = {}
    if not agent.get("isOrgan"): agent["isOrgan"] = "0"
    if not agent.get("keepStartDate"): agent["keepStartDate"] = "2026-04-23"
    if not agent.get("keepEndDate"): agent["keepEndDate"] = "2026-07-22"
    for _af in ("modifyMaterial", "modifyForm", "modifyWord", "otherModifyItem", "license"):
        if not agent.get(_af): agent[_af] = "1"
    member["agentMemPartDto"] = agent

    # gdMemPartDto: 股东投资信息
    gd = member.get("gdMemPartDto") or {}
    if not isinstance(gd, dict):
        gd = {}
    capital = str(case.get("capital_wan") or 100)
    _gd_defaults_1151 = {
        "invFormType": "10", "fromType": "10", "invType": "20",
        "shouldInvestMoney": capital, "moneyRatio": "100",
        "shouldInvestWay": "1", "investDate": "2056-04-23",
        "shouldInvestMode": "01", "isForChi": "0",
        "forAmt": int(capital), "forAmtCur": "156",
        "forDate": "2056-04-23", "forPercent": 100, "amountDollar": "",
    }
    for _gk, _gv in _gd_defaults_1151.items():
        if not gd.get(_gk): gd[_gk] = _gv
    member["gdMemPartDto"] = gd

    # docAccepterMemPartDto: 文书接收人
    doc = member.get("docAccepterMemPartDto") or {}
    if not isinstance(doc, dict):
        doc = {}
    if not doc.get("empower"): doc["empower"] = person.get("name") or ""
    if not doc.get("accepterType"): doc["accepterType"] = "20"
    member["docAccepterMemPartDto"] = doc

    # realEntName / allCapital 等顶层字段
    if not member.get("realEntName"): member["realEntName"] = case.get("company_name_phase1_normalized") or ""
    if not member.get("allCapital"): member["allCapital"] = int(capital)
    if not member.get("moneyKindCode"): member["moneyKindCode"] = ""
    if not member.get("board"): member["board"] = "0"
    if not member.get("boardSup"): member["boardSup"] = "0"
    if not member.get("invMany"): member["invMany"] = "1"

    body = {
        **member,
        "flowData": _base_flow_data(ent_type, name_id, "MemberInfo", busi_id=busi_id),
        "linkData": _base_link_data("MemberInfo", parents=["MemberPool"]),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": item_id or raw_member.get("itemId") or "",
    }
    return body


def build_complement_info_save_body_1151(case: Dict[str, Any], *,
                                           ent_type: str = "1151",
                                           name_id: str,
                                           busi_id: Optional[str] = None,
                                           preloaded_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """1151 ComplementInfo save：非公党建 + 受益所有人已处理后的推进 body。

    ★ 1151 ComplementInfo 比 4540 复杂得多：
    - 非公党建: partyBuildFlag=6（全部选否）
    - 受益所有人: 必须先完成 BenefitUsers 流程（dataAdd.do → BenefitCallback），
      否则 save 返回 resultType=1 "受益所有人信息未填报"
    - save 时 flowData.currCompUrl 必须是 "ComplementInfo"（不能是 "BenefitUsers"）

    此 body 用于受益所有人已完成后的最终 save 推进。
    BenefitUsers 流程由驱动器的 step 函数单独处理。
    """
    body = {
        "flowData": _base_flow_data(ent_type, name_id, "ComplementInfo", busi_id=busi_id),
        "linkData": _base_link_data("ComplementInfo"),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": "",
    }
    # 如果有 preloaded_data（从 load 返回的 busiData），合并非公党建字段
    if preloaded_data:
        body["partyBuildFlag"] = preloaded_data.get("partyBuildFlag") or "6"
    else:
        body["partyBuildFlag"] = "6"
    return body


def build_rules_save_body_1151(case: Dict[str, Any], *,
                                 ent_type: str = "1151",
                                 name_id: str,
                                 busi_id: Optional[str] = None,
                                 preloaded_data: Optional[Dict[str, Any]] = None,
                                 today_str: Optional[str] = None) -> Dict[str, Any]:
    """1151 Rules save：决议及章程（自动生成模式）。

    基于 dashboard/data/records/1151_comp_Rules.json load 响应结构。

    ★ selectMode=2 → 自动生成章程
    ★ temSerial="09-02-rule_rec-111"（单股东不设董事会不设监事会章程）
    ★ 需填 5 个日期字段:
      - invDecideDate: 股东决定日期
      - invSignDate: 股东签字日期
      - boardDecideDate: 董事决定日期
      - boardSignDate: 董事签字日期
      - mainRuleSignTime: 主章程签字日期（格式 "YYYY年MM月DD日"）
    """
    import datetime
    if not today_str:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
    today_cn = datetime.date.today().strftime("%Y年%m月%d日")

    # ruleList: 章程类型列表，selectMode=2 → 系统自动生成
    rule_item = {
        "type": "rule_rec",
        "selectMode": "2",
        "temSerial": "09-02-rule_rec-111",
        "temUrl": "09-02-rule_rec-111.vue",
        "fields": {
            "invDecideDate": today_str,
            "invSignDate": today_str,
            "boardDecideDate": today_str,
            "boardSignDate": today_str,
            "mainRuleSignTime": today_cn,
        },
        "materials": [],
    }

    body = {
        "ruleList": [rule_item],
        "flowData": _base_flow_data(ent_type, name_id, "Rules", busi_id=busi_id),
        "linkData": _base_link_data("Rules"),
        "signInfo": str(SIGN_INFO_ESTABLISH),
        "itemId": "",
    }
    return body
