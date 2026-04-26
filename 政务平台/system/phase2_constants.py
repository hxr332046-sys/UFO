"""Phase 2 协议化常量中心。

单一事实源（Single Source of Truth）：
- 所有魔数（signInfo 固定值）
- 所有 API 路径
- 元数据字段过滤表（load 响应带但 save 不该回传的 meta keys）
- 错误码常量

来源：
- docs/突破D0022越权_协议层字段合同方法论_20260422.md
- docs/Phase2_阶段总结_20260423.md
- docs/Phase2完整协议化通达_PreElectronicDoc_20260423.md
- docs/Phase2第二日突破_MemberInfo至SlUploadMaterial_20260423.md
- system/_archive/_phase2_mi_save_v7.py 等实录
"""
from __future__ import annotations

# ==== signInfo 魔数 ====
#
# 固定值而非动态计算。服务端对 save 做 signInfo 校验：
# - Phase 1 域（name/NameCheckInfo/NameSupplement/NameShareholder）：-252238669
# - Phase 2 域（establish/BasicInfo/MemberPost/MemberInfo/SlUploadMaterial/...）：-1607173598
#
# 负数在 JSON 里原样输出（无前导 0）。字符串形式传给服务端（str 而非 int）。
SIGN_INFO_NAME = -252238669         # 别名：SIGN_INFO_MAGIC
SIGN_INFO_MAGIC = SIGN_INFO_NAME    # 向后兼容旧代码
SIGN_INFO_ESTABLISH = -1607173598

# ==== API 路径（Phase 1 名称登记）====
HOST = "zhjg.scjdglj.gxzf.gov.cn:9087"
BASE_PREFIX = "/icpsp-api/v4/pc"

# 名称登记 7 步
API_CHECK_ESTABLISH_NAME = f"{BASE_PREFIX}/register/guide/establishname/checkEstablishName"
API_NAME_LOAD_LOC = f"{BASE_PREFIX}/register/name/loadCurrentLocationInfo"
API_NC_LOAD = f"{BASE_PREFIX}/register/name/component/NameCheckInfo/loadBusinessDataInfo"
API_NC_OP = f"{BASE_PREFIX}/register/name/component/NameCheckInfo/operationBusinessDataInfo"
API_NC_BANNED = f"{BASE_PREFIX}/register/name/bannedLexiconCalibration"
API_NC_REPEAT = f"{BASE_PREFIX}/register/name/component/NameCheckInfo/nameCheckRepeat"

# ==== API 路径（Phase 2 名称补充 + 提交）====
API_NSUPP_LOAD = f"{BASE_PREFIX}/register/name/component/NameSupplement/loadBusinessDataInfo"
API_NSUPP_OP = f"{BASE_PREFIX}/register/name/component/NameSupplement/operationBusinessDataInfo"
API_NSH_LIST = f"{BASE_PREFIX}/register/name/component/NameShareholder/loadBusinessInfoList"
API_NSH_LOAD = f"{BASE_PREFIX}/register/name/component/NameShareholder/loadBusinessDataInfo"
API_NSH_OP = f"{BASE_PREFIX}/register/name/component/NameShareholder/operationBusinessDataInfo"
API_NAME_SUBMIT = f"{BASE_PREFIX}/register/name/submit"
API_NSUCC_LOAD = f"{BASE_PREFIX}/register/name/component/NameSuccess/loadBusinessDataInfo"

# ==== API 路径（Phase 2 设立登记激活 + 基础信息）====
API_MATTERS_OP = f"{BASE_PREFIX}/manager/mattermanager/matters/operate"
API_EST_LOAD_LOC = f"{BASE_PREFIX}/register/establish/loadCurrentLocationInfo"
API_YBB_LOAD = f"{BASE_PREFIX}/register/establish/component/YbbSelect/loadBusinessDataInfo"
API_EST_BASICINFO_LOAD = f"{BASE_PREFIX}/register/establish/component/BasicInfo/loadBusinessDataInfo"
API_EST_BASICINFO_OP = f"{BASE_PREFIX}/register/establish/component/BasicInfo/operationBusinessDataInfo"

# ==== API 路径（Phase 2 成员/材料/提交 — 组件式 establish）====
def establish_comp_load(comp: str) -> str:
    """返回 establish 组件 load API 路径，如 MemberPost / MemberInfo / SlUploadMaterial。"""
    return f"{BASE_PREFIX}/register/establish/component/{comp}/loadBusinessDataInfo"


def establish_comp_op(comp: str) -> str:
    """返回 establish 组件 operation API 路径。"""
    return f"{BASE_PREFIX}/register/establish/component/{comp}/operationBusinessDataInfo"


def establish_comp_list(comp: str) -> str:
    """返回 establish 组件 list API 路径（如 MemberPool/loadBusinessInfoList）。"""
    return f"{BASE_PREFIX}/register/establish/component/{comp}/loadBusinessInfoList"


# ==== 组件名常量 ====
# 个人独资 4540 流程涉及的组件（按推进顺序）
COMP_NAME_CHECK = "NameCheckInfo"
COMP_NAME_SUPPLEMENT = "NameSupplement"
COMP_NAME_SHAREHOLDER = "NameShareholder"
COMP_NAME_SUCCESS = "NameSuccess"
COMP_YBB_SELECT = "YbbSelect"
COMP_BASIC_INFO = "BasicInfo"
COMP_MEMBER_POST = "MemberPost"
COMP_MEMBER_POOL = "MemberPool"
COMP_MEMBER_INFO = "MemberInfo"
COMP_COMPLEMENT = "ComplementInfo"
COMP_TAX_INVOICE = "TaxInvoice"
COMP_SL_UPLOAD = "SlUploadMaterial"
COMP_LICENCE_WAY = "BusinessLicenceWay"
COMP_PRE_DOC = "PreElectronicDoc"
COMP_PRE_SUCCESS = "PreSubmitSuccess"

# 1151 有限公司新增组件
COMP_RULES = "Rules"
COMP_BANK_OPEN = "BankOpenInfo"
COMP_MEDICAL = "MedicalInsured"
COMP_ENGRAVING = "Engraving"
COMP_SOCIAL = "SocialInsured"
COMP_GJJ = "GjjHandle"
COMP_YJS_PREPACK = "YjsRegPrePack"
COMP_BENEFIT_CALLBACK = "BenefitCallback"

# 4540 个人独资完整组件推进序列（从 BasicInfo 到预提交成功）
ESTABLISH_COMP_SEQUENCE_4540 = [
    COMP_BASIC_INFO,        # 基本信息
    COMP_MEMBER_POST,       # 成员职位
    COMP_MEMBER_POOL,       # 成员池（容器）
    COMP_MEMBER_INFO,       # 成员详情（池内）
    COMP_COMPLEMENT,        # 补充信息
    COMP_TAX_INVOICE,       # 税务发票
    COMP_SL_UPLOAD,         # 材料上传
    COMP_LICENCE_WAY,       # 营业执照领取方式
    COMP_YBB_SELECT,        # 云帮办选择
    COMP_PRE_DOC,           # 预电子文书
    COMP_PRE_SUCCESS,       # 预提交成功（终点）
]

# 1151 有限责任公司（自然人独资）完整组件推进序列
# 来源：已完成记录 busiId=824177927 的 SPA 侧栏 + busiId=2047225160991752194 实录
ESTABLISH_COMP_SEQUENCE_1151 = [
    COMP_BASIC_INFO,        # 基本信息
    COMP_MEMBER_POST,       # 成员架构（7 角色: GD01/DS01/JS01/CWFZR/FR01/LLY/WTDLR）
    COMP_MEMBER_POOL,       # 成员池（容器）
    COMP_MEMBER_INFO,       # 成员详情（池内，含 role-specific DTOs）
    COMP_COMPLEMENT,        # 补充信息（含受益所有人 BenefitUsers 处理）
    COMP_RULES,             # 决议及章程（自动生成模式，需日期字段）
    COMP_MEDICAL,           # 医保信息（空体推进）
    COMP_TAX_INVOICE,       # 税务登记（空体推进）
    COMP_YJS_PREPACK,       # 仅销售预包装食品备案（空体推进）
    COMP_SL_UPLOAD,         # 上传材料
    COMP_LICENCE_WAY,       # 营业执照领取方式
    COMP_YBB_SELECT,        # 云帮办流程模式选择
    COMP_PRE_DOC,           # 信息确认
    COMP_PRE_SUCCESS,       # 预提交成功（终点）
]


# ==== 元数据过滤表 ====
#
# load 响应的 busiData（或 list[0]）里除了业务字段，还带一批 meta 字段。
# save 时必须剥离，否则 meta.flowData / meta.linkData 会覆盖顶层 → 路径污染 → D0022 / A0002。
#
# 来源：docs/Phase2第二日突破_MemberInfo至SlUploadMaterial_20260423.md 坑6
BASICINFO_META_STRIP = frozenset({
    "flowData", "linkData", "processVo", "jurisdiction", "currentLocationVo",
    "producePdfVo", "returnModifyVo", "transferToOfflineVo", "preSubmitVo",
    "submitVo", "page", "list", "fieldList", "busiComp", "subBusiCompMap",
    "signInfo", "operationResultVo", "signRandomCode", "extraDto",
    "itemId",
})

MEMBERINFO_META_STRIP = BASICINFO_META_STRIP | frozenset({
    "xzPushGsDto", "pkAndMem", "delPostCode", "realEntName",
})


# ==== 错误码 ====
CODE_SUCCESS = "00000"
CODE_SESSION_GATE = "GS52010103E0302"    # Authorization 失效 / 未认证
CODE_PRIVILEGE_D0019 = "D0019"           # 越权（flow-control 路径状态与服务端不匹配）
CODE_PRIVILEGE_D0021 = "D0021"           # 越权（session 未激活到对应域）
CODE_PRIVILEGE_D0022 = "D0022"           # 越权（字段合同/header 不匹配）— 三层洋葱突破对应
CODE_RATE_LIMIT = "D0029"                # 操作频繁 / 短期内写操作过多
CODE_SERVER_EXCEPTION = "A0002"          # 服务端异常（常见于字段大小写/必填缺失/加密格式）
CODE_NAME_EXPIRED = "GS52010400B0017"    # 名称保留期限超期（需重跑 Phase 1）

# 服务端异常类可重试的错误码（不包含 session/权限这种需人工介入的）
RETRYABLE_CODES = frozenset({CODE_RATE_LIMIT})

# 业务级别致命（不可通过重试恢复）
FATAL_BUSINESS_CODES = frozenset({
    CODE_SESSION_GATE,
    CODE_PRIVILEGE_D0022,
    CODE_PRIVILEGE_D0019,
    CODE_NAME_EXPIRED,
})


# ==== URL 编码片段（linkData.busiCompUrlPaths）====
# busiCompUrlPaths 是 URL 编码的 JSON 数组：
#   顶层组件（无父）：%5B%5D = []
#   有父组件（如 MemberInfo 在 MemberPool 里）：
#     [{"compUrl":"MemberPool","id":""}] → 编码
BUSI_COMP_URL_PATHS_EMPTY = "%5B%5D"
BUSI_COMP_URL_PATHS_MEMBERPOOL = "%5B%7B%22compUrl%22%3A%22MemberPool%22%2C%22id%22%3A%22%22%7D%5D"
BUSI_COMP_URL_PATHS_MEMBERPOST = "%5B%7B%22compUrl%22%3A%22MemberPost%22%2C%22id%22%3A%22%22%7D%5D"
BUSI_COMP_URL_PATHS_SLUPLOAD = "%5B%7B%22compUrl%22%3A%22SlUploadMaterial%22%2C%22id%22%3A%22%22%7D%5D"

# 1151 MemberPost 角色列表（自然人独资有限公司，单人兼全部 7 职）
MEMBERPOST_ROLES_1151 = ["GD01", "DS01", "JS01", "CWFZR", "FR01", "LLY", "WTDLR"]
MEMBERPOST_POSTCODE_1151 = ",".join(MEMBERPOST_ROLES_1151)

# 4540 个人独资角色列表
MEMBERPOST_ROLES_4540 = ["FR05", "WTDLR", "LLY", "CWFZR"]
MEMBERPOST_POSTCODE_4540 = ",".join(MEMBERPOST_ROLES_4540)

# BenefitCallback API（受益所有人回调，ComplementInfo 1151 专用）
API_BENEFIT_CALLBACK = f"{BASE_PREFIX}/third/benefit/BenefitCallback/pcCallBackUrl"


def busi_comp_url_paths(parents: list[str] | None) -> str:
    """把父组件路径数组序列化为 busiCompUrlPaths 格式。"""
    if not parents:
        return BUSI_COMP_URL_PATHS_EMPTY
    import urllib.parse
    inner = [{"compUrl": p, "id": ""} for p in parents]
    import json as _json
    return urllib.parse.quote(_json.dumps(inner, separators=(",", ":")), safe="")


# ==== 通用 Referer（避免 D0022 中 header 层校验）====
REFERER_CORE = f"https://{HOST}/icpsp-web-pc/core.html"
REFERER_PORTAL = f"https://{HOST}/icpsp-web-pc/portal.html"
