#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 2 establish 组件枚举字段字典（code ↔ 业务语义）。

**目的**：把 case 里的人话（"否"/"自有产权"/"男"）映射到服务端 HTTP 字段的真实编码值（"0"/"01"/"1"）。

**数据来源**：
- `dashboard/data/records/establish_save_samples/BasicInfo__save.json`（42 keys 真实 body）
- `dashboard/data/records/establish_save_samples/MemberBaseInfo__save.json`（含 fieldList 字段字典）
- `dashboard/data/records/establish_save_samples/MemberPost__save.json`
- `_archive/_phase2_mi_save_v7.py`（验证成功的 MemberInfo 字段值）
- 前端 SPA `/icpsp-web-pc/js/chunk-*.js` 的 option list（TODO：后续若需再补）

**约定**：
- 所有 helper 接受**业务语言字符串**（含别名/大小写不敏感），返回字符串编码
- 未命中时**返回默认值**并打印警告，永不抛异常（避免中断流程）
- 字段名不要动（由 mitm 实录决定）

**使用**：
    from phase2_enums import cer_type, house_to_bus, politics_visage
    body["cerType"] = cer_type("身份证")          # → "10"
    body["houseToBus"] = house_to_bus("否")       # → "0"
    body["politicsVisage"] = politics_visage("群众")  # → "13"
"""
from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# BasicInfo 企业基本信息
# ═══════════════════════════════════════════════════════════════════

ENT_TYPES = {
    "4540": "个人独资企业",
    "1151": "有限责任公司(自然人投资或控股)",
    "8000": "个体工商户",
    "4530": "合伙企业",
    "1100": "有限责任公司",
    "2100": "股份有限公司",
}

ACCOUNT_TYPE = {  # 企业账户类型
    "1": "公账(一般账户)",
    "2": "分支/特殊账户",
}

BUSINESS_MODE_GT = {  # 经营模式
    "10": "一般",
    "20": "其他",
}

SHOULD_INVEST_WAY = {  # 认缴方式 / 投资方式
    "01": "货币",
    "02": "实物",
    "03": "知识产权",
    "04": "土地使用权",
    "05": "其他",
}

LICENSE_RADIO = {  # 是否领营业执照副本
    "0": "否",
    "1": "是",
}

YES_NO_01 = {  # 通用"是/否"(0/1)
    "0": "否",
    "1": "是",
}

YES_NO_0102 = {  # 通用"是/否"(01/02)
    "01": "是",
    "02": "否",
}

XFZ = {  # 消防子项
    "close": "不需要",
    "open": "需要",
}

IS_SELECT_YBB = {  # 云帮办流程
    "0": "一般流程",
    "1": "云帮办",
}

SECRETARY_SERVICE = {  # 秘书服务企业
    "0": "否",
    "1": "是",
}


# ═══════════════════════════════════════════════════════════════════
# entDomicileDto 地址相关
# ═══════════════════════════════════════════════════════════════════

HOUSE_TO_BUS = {  # 是否住改商（住宅改商用）
    "0": "否",
    "1": "是",
}

NORM_ADD_FLAG = {  # 地址标准化标识
    "01": "标准地址(从地址库选择)",
    "02": "非标地址(自由输入)",
}

USE_MODE = {  # 房屋使用方式
    "01": "自有产权",
    "02": "租赁",
    "03": "借用/无偿使用",
    "04": "其他",
}

IS_SELECT_DIST_CODE = {  # 行政区划选择方式
    "0": "自动匹配",
    "1": "手动选",
}


# ═══════════════════════════════════════════════════════════════════
# MemberInfo / MemberBaseInfo 成员相关
# ═══════════════════════════════════════════════════════════════════

CER_TYPE = {  # 证件类型
    "10": "居民身份证",
    "11": "香港居民身份证",
    "12": "澳门居民身份证",
    "13": "台湾居民身份证",
    "14": "护照",
    "15": "军官证",
    "16": "士兵证",
    "17": "警官证",
    "18": "文职干部证",
    "19": "海员证",
    "20": "营业执照",       # 法人股东
    "21": "组织机构代码证",
    "22": "统一社会信用代码",
}

SEX_CODE = {
    "1": "男",
    "2": "女",
}

NATURAL_FLAG = {
    "0": "非自然人(法人股东)",
    "1": "自然人",
}

NATIONALITY = {
    "156": "中国",
    "344": "中国香港",
    "446": "中国澳门",
    "158": "中国台湾",
}

FZ_SIGN = {  # 分支机构负责人
    "Y": "是分支负责人",
    "N": "非分支负责人",
}

POLITICS_VISAGE = {  # 政治面貌
    "01": "中共党员",
    "02": "中共预备党员",
    "03": "共青团员",
    "04": "民革党员",
    "05": "民盟盟员",
    "06": "民建会员",
    "07": "民进会员",
    "08": "农工党党员",
    "09": "致公党党员",
    "10": "九三学社社员",
    "11": "台盟盟员",
    "12": "无党派人士",
    "13": "群众",
}

IS_ORGAN = {  # agentMemPartDto.isOrgan：代理人是否为机构
    "01": "是(机构代理)",
    "02": "否(自然人代理)",
}

INV_TYPE = {  # gdMemPartDto.invType：投资人类型
    "1": "自然人",
    "2": "企业法人",
    "3": "机关事业单位",
    "4": "外商独资企业",
    "5": "中外合资",
    "6": "中外合作",
}

INV_FORM_TYPE = {  # gdMemPartDto.invFormType：投资形式
    "1": "货币",
    "2": "实物",
    "3": "知识产权",
    "4": "土地使用权",
    "5": "债权转股权",
    "9": "其他",
}

FOREIGN_OR_CHINESE = {  # gdMemPartDto.foreignOrChinese
    "1": "内资",
    "2": "外资",
}

FROM_TYPE = {  # gdMemPartDto.fromType：成员来源
    "1": "新增",
    "2": "变更",
    "3": "承继",
}

COME_NAME_FLAG = {  # 是否从名称登记带过来
    "0": "否",
    "1": "是",
}

IS_LOGIN_INFO = {  # 是否登录人
    "0": "否",
    "1": "是",
}

# 成员职务角色（postCode）
POST_CODE = {
    # 个人独资 / 合伙企业
    "FR05": "投资人(经营者)",
    "WTDLR": "委托代理人",
    "LLY": "联络员",
    "CWFZR": "财务负责人",
    # 有限公司 / 股份公司
    "DSZ": "董事长",
    "DS": "董事",
    "JSZ": "监事长",
    "JS": "监事",
    "JL": "经理",
    "FR01": "法定代表人",
    # 其他
    "GDRY": "股东/成员",
}


# ═══════════════════════════════════════════════════════════════════
# MemberPost 组织架构
# ═══════════════════════════════════════════════════════════════════

BOARD = {  # 董事会
    "0": "无董事会",
    "1": "有董事会",
}

BOARD_SUP = {  # 监事会
    "0": "无监事会",
    "1": "有监事会",
}


# ═══════════════════════════════════════════════════════════════════
# SlUploadMaterial 材料代码
# ═══════════════════════════════════════════════════════════════════

MATERIAL_CODE = {
    "175": "住所(经营场所)使用证明_自有产权",
    "176": "住所(经营场所)使用证明_租赁合同",
    "177": "住所(经营场所)使用证明_借用",
    "178": "居委会/村委会开具的使用证明",
    "200": "投资人身份证复印件",
    "210": "委托代理人身份证复印件",
    "220": "财务负责人身份证复印件",
    "300": "章程/协议",
    "400": "其他",
}


# ═══════════════════════════════════════════════════════════════════
# 反向查询 helper（业务语言 → code）
# ═══════════════════════════════════════════════════════════════════

def _reverse_lookup(mapping: dict, value: str, default: str,
                      field_name: str = "") -> str:
    """把业务语言映射回 code。支持模糊匹配（包含关系/大小写不敏感）。"""
    if not value:
        return default
    v_str = str(value).strip()
    # 如果本身就是 code，直接返回
    if v_str in mapping:
        return v_str
    # 全字匹配（label → code）
    for code, label in mapping.items():
        if v_str == label:
            return code
    # 子串匹配
    v_low = v_str.lower()
    for code, label in mapping.items():
        if v_low in label.lower() or label.lower() in v_low:
            return code
    print(f"    [phase2_enums] WARN: '{value}' not found in {field_name}, using default '{default}'")
    return default


def ent_type(v: Optional[str], default: str = "4540") -> str:
    """'个人独资' → '4540', '有限公司' → '1151'."""
    return _reverse_lookup(ENT_TYPES, v or "", default, "ENT_TYPES")


def cer_type(v: Optional[str], default: str = "10") -> str:
    """'身份证' → '10', '护照' → '14'."""
    return _reverse_lookup(CER_TYPE, v or "", default, "CER_TYPE")


def sex_code(v: Optional[str], default: str = "1") -> str:
    """'男' → '1', '女' → '2'."""
    return _reverse_lookup(SEX_CODE, v or "", default, "SEX_CODE")


def house_to_bus(v: Optional[str], default: str = "0") -> str:
    """'否' → '0'（非住改商，通常推荐默认）。"""
    return _reverse_lookup(HOUSE_TO_BUS, v or "", default, "HOUSE_TO_BUS")


def use_mode(v: Optional[str], default: str = "02") -> str:
    """'自有产权' → '01', '租赁' → '02', '借用' → '03'."""
    return _reverse_lookup(USE_MODE, v or "", default, "USE_MODE")


def politics_visage(v: Optional[str], default: str = "13") -> str:
    """'群众' → '13', '党员' → '01'."""
    return _reverse_lookup(POLITICS_VISAGE, v or "", default, "POLITICS_VISAGE")


def is_organ(v: Optional[str], default: str = "02") -> str:
    """'否' → '02' (自然人代理, 默认)."""
    # is_organ 是 01/02 语义
    if v in (None, "", "否", "否(自然人代理)", "0", "02"):
        return "02"
    if v in ("是", "是(机构代理)", "1", "01"):
        return "01"
    return default


def inv_type(v: Optional[str], default: str = "1") -> str:
    """投资人类型：'自然人' → '1', '企业法人' → '2'."""
    return _reverse_lookup(INV_TYPE, v or "", default, "INV_TYPE")


def inv_form_type(v: Optional[str], default: str = "1") -> str:
    """投资形式：'货币' → '1'."""
    return _reverse_lookup(INV_FORM_TYPE, v or "", default, "INV_FORM_TYPE")


def should_invest_way(v: Optional[str], default: str = "01") -> str:
    """认缴方式：'货币' → '01'."""
    return _reverse_lookup(SHOULD_INVEST_WAY, v or "", default, "SHOULD_INVEST_WAY")


def business_mode_gt(v: Optional[str], default: str = "10") -> str:
    """经营模式：'一般' → '10'."""
    return _reverse_lookup(BUSINESS_MODE_GT, v or "", default, "BUSINESS_MODE_GT")


def norm_add_flag(v: Optional[str], default: str = "02") -> str:
    """地址标识：'标准' → '01', '非标' → '02'（容县案例为 02）."""
    return _reverse_lookup(NORM_ADD_FLAG, v or "", default, "NORM_ADD_FLAG")


def yes_no_01(v: Optional[str], default: str = "0") -> str:
    """通用 '是/否' → '1/0'."""
    return _reverse_lookup(YES_NO_01, v or "", default, "YES_NO_01")


def material_code_for_property(use_mode_value: str) -> str:
    """根据房屋使用方式推导材料代码：
    - 自有产权 (01) → 175
    - 租赁 (02) → 176
    - 借用 (03) → 177
    - 其他 → 178
    """
    m = {"01": "175", "02": "176", "03": "177", "04": "178"}
    return m.get(use_mode_value, "176")


# 自测
if __name__ == "__main__":
    print("=== phase2_enums 自测 ===")
    tests = [
        (ent_type, "个人独资", "4540"),
        (ent_type, "4540", "4540"),
        (cer_type, "身份证", "10"),
        (cer_type, "居民身份证", "10"),
        (sex_code, "男", "1"),
        (sex_code, "女", "2"),
        (house_to_bus, "否", "0"),
        (house_to_bus, "是", "1"),
        (use_mode, "自有产权", "01"),
        (use_mode, "租赁", "02"),
        (politics_visage, "群众", "13"),
        (politics_visage, "党员", "01"),
        (is_organ, "否", "02"),
        (inv_type, "自然人", "1"),
        (material_code_for_property, "02", "176"),  # 租赁 → 176
        (material_code_for_property, "01", "175"),  # 自有 → 175
    ]
    ok = 0
    for fn, inp, expected in tests:
        got = fn(inp)
        status = "✓" if got == expected else "✗"
        print(f"  {status} {fn.__name__}({inp!r}) = {got!r} (expected {expected!r})")
        if got == expected:
            ok += 1
    print(f"\n{ok}/{len(tests)} passed")
