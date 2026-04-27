"""
CaseValidator — case JSON 启动前质检

校验对象：
- 必填字段是否存在 / 非空
- 枚举字段（OptionDict 收录）是否合法
- 行业代码（itemIndustryTypeCode）是否在 GB/T 4754-2017 树内
- 经营范围文本与行业代码语义是否一致

输出：ValidationReport
- pass:        全部合法，可直接跑
- ambiguous:   存在歧义，需用户从候选中选择
- fail:        有非法值，需用户手动修正
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .industry_matcher import IndustryMatcher, IndustryMatch
from .option_dict import OptionDict, OptionEntry

logger = logging.getLogger(__name__)


class IssueLevel(str, Enum):
    PASS = "pass"
    AMBIGUOUS = "ambiguous"
    FAIL = "fail"
    WARN = "warn"


class IssueKind(str, Enum):
    MISSING_REQUIRED = "missing_required"
    INVALID_ENUM = "invalid_enum"
    AMBIGUOUS_VALUE = "ambiguous_value"
    INVALID_INDUSTRY_CODE = "invalid_industry_code"
    INDUSTRY_TEXT_MISMATCH = "industry_text_mismatch"
    SUSPICIOUS_FORMAT = "suspicious_format"


@dataclass
class ValidationIssue:
    """单个质检问题。"""
    field_path: str                    # case 中字段路径，如 "person.cerNo"
    case_value: Any
    level: IssueLevel
    kind: IssueKind
    message: str
    candidates: List[Dict[str, Any]] = field(default_factory=list)  # 候选合法值
    suggestion: Optional[Dict[str, Any]] = None                      # 最佳建议（如有）
    auto_fixable: bool = False                                       # 可自动用 suggestion 修

    def as_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "case_value": self.case_value,
            "level": self.level.value,
            "kind": self.kind.value,
            "message": self.message,
            "candidates": self.candidates,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class ValidationReport:
    """质检报告。"""
    case_id: str
    issues: List[ValidationIssue] = field(default_factory=list)
    checked_fields: int = 0

    @property
    def fails(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == IssueLevel.FAIL]

    @property
    def ambiguous(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == IssueLevel.AMBIGUOUS]

    @property
    def warns(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == IssueLevel.WARN]

    def is_pass(self) -> bool:
        return len(self.fails) == 0 and len(self.ambiguous) == 0

    def is_blocking(self) -> bool:
        """是否阻断执行（fail 一定阻断；ambiguous 视上层决策）。"""
        return bool(self.fails) or bool(self.ambiguous)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "checked_fields": self.checked_fields,
            "summary": {
                "pass": len(self.issues) == 0,
                "fail_count": len(self.fails),
                "ambiguous_count": len(self.ambiguous),
                "warn_count": len(self.warns),
            },
            "issues": [i.as_dict() for i in self.issues],
        }


# ════════════════════════════════════════════════
# 字段映射规则
# ════════════════════════════════════════════════

# case 字段路径 → OptionDict 字段名（用于枚举类校验）
CASE_FIELD_TO_OPTION_KEY: Dict[str, str] = {
    # 主表
    "entType_default": "entType",
    "areaCategory": "areaCategory",
    "busiAreaCode": "busiAreaCode",
    "itemIndustryTypeCode": "itemIndustryTypeCode",
    "domDistCode": "distCode",
    # 投资人/法定代表人
    "person.politicsVisage": "politicalStatus",
    "person.eduDegree": "eduDegree",
    "person.cerType": "cerType",
    "person.sex": "sex",
    "person.country": "country",
    # ComplementInfo
    "property_use_mode": "propertyUseMode",
    "house_to_bus": "houseToBus",
    "tax_invoice_is_setup": "yesOrNo",
    "tax_registration": "yesOrNo",
}

# case 必填字段（缺失即 fail）
# 每项 = (主路径, [备选路径...])，任一非空即视为命中
REQUIRED_FIELDS: List[tuple] = [
    ("case_id", []),
    ("company_name_full", []),
    ("name_mark", []),
    ("phase1_check_name", []),
    ("entType_default", []),
    ("phase1_industry_code", ["itemIndustryTypeCode"]),
    ("phase1_main_business_desc", ["business_area", "phase1_industry_special"]),
    ("phase1_dist_codes", []),
    ("address_full", ["dom", "domAddress"]),
    # 投资人/法定代表人 — 兼容多种字段名约定
    ("person.id_no", ["person.cerNo", "person.idNo", "person.idCard"]),
    ("person.name", ["person.memName", "person.fullName"]),
]

# 警告级字段（缺失只是 warn）
RECOMMENDED_FIELDS: List[tuple] = [
    ("person.mobile", ["person.phone", "person.tel"]),
    ("phase2_invest_money_yuan", []),
    ("phase2_invest_date", ["investDate"]),
]


def _get_path(case: Dict[str, Any], path: str) -> Any:
    """点分路径取值。"""
    cur: Any = case
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


# ════════════════════════════════════════════════
# 主类
# ════════════════════════════════════════════════

class CaseValidator:
    """case 质检器。

    使用方式：
        v = CaseValidator()
        report = v.validate(case)
        if report.is_blocking():
            # 调用 v.interactive_resolve(report, case) 让用户决断
            ...
    """

    def __init__(self,
                 option_dict: Optional[OptionDict] = None,
                 industry_matcher: Optional[IndustryMatcher] = None,
                 *,
                 prompt_fn: Optional[Callable[[str, List[str]], int]] = None):
        """
        Args:
            option_dict: 服务端选项字典（默认从默认路径加载）
            industry_matcher: 行业匹配引擎
            prompt_fn: 询问用户的函数 (question, options) -> selected_index
                       默认用 input() 终端交互
        """
        self.opt = option_dict or OptionDict.load()
        self.ind = industry_matcher or IndustryMatcher.load()
        self.prompt_fn = prompt_fn or self._default_prompt

    @staticmethod
    def _default_prompt(question: str, options: List[str]) -> int:
        print(f"\n[?] {question}")
        for i, o in enumerate(options):
            print(f"  [{i+1}] {o}")
        while True:
            ans = input(f"请输入 1-{len(options)}（0=放弃）: ").strip()
            if ans == "0":
                return -1
            if ans.isdigit() and 1 <= int(ans) <= len(options):
                return int(ans) - 1

    # ─── public API ────────────────────────────────

    def validate(self, case: Dict[str, Any]) -> ValidationReport:
        report = ValidationReport(case_id=str(case.get("case_id", "unknown")))

        def _first_non_empty(primary: str, aliases: List[str]):
            for p in [primary] + list(aliases):
                v = _get_path(case, p)
                if v not in (None, "", []):
                    return p, v
            return primary, None

        # 1. 必填检查（带别名）
        for primary, aliases in REQUIRED_FIELDS:
            hit_path, v = _first_non_empty(primary, aliases)
            report.checked_fields += 1
            if v is None or v == "" or v == []:
                all_paths = [primary] + list(aliases)
                report.issues.append(ValidationIssue(
                    field_path=primary, case_value=v,
                    level=IssueLevel.FAIL,
                    kind=IssueKind.MISSING_REQUIRED,
                    message=(f"必填字段缺失：尝试路径 {all_paths} 全部为空"),
                ))

        # 2. 推荐字段（带别名）
        for primary, aliases in RECOMMENDED_FIELDS:
            hit_path, v = _first_non_empty(primary, aliases)
            report.checked_fields += 1
            if v is None or v == "":
                all_paths = [primary] + list(aliases)
                report.issues.append(ValidationIssue(
                    field_path=primary, case_value=v,
                    level=IssueLevel.WARN,
                    kind=IssueKind.MISSING_REQUIRED,
                    message=f"建议字段未提供：尝试路径 {all_paths}",
                ))

        # 3. 枚举字段校验
        for case_path, opt_key in CASE_FIELD_TO_OPTION_KEY.items():
            v = _get_path(case, case_path)
            report.checked_fields += 1
            if v is None or v == "":
                continue
            if not self.opt.has_field(opt_key):
                # 字典里还没收录这个字段，不报错（scout 还没扫过）
                continue
            status, matched, candidates = self.opt.validate_value(opt_key, v)
            if status == "fail":
                f = self.opt.get_field(opt_key)
                cands_dump = [{"code": o.code, "name": o.name}
                              for o in (f.options if f else [])][:10]
                report.issues.append(ValidationIssue(
                    field_path=case_path, case_value=v,
                    level=IssueLevel.FAIL,
                    kind=IssueKind.INVALID_ENUM,
                    message=f"{case_path}={v!r} 不在合法选项内",
                    candidates=cands_dump,
                ))
            elif status == "ambiguous":
                cands_dump = [{"code": o.code, "name": o.name}
                              for o in candidates]
                suggestion = cands_dump[0] if len(cands_dump) == 1 else None
                report.issues.append(ValidationIssue(
                    field_path=case_path, case_value=v,
                    level=IssueLevel.AMBIGUOUS,
                    kind=IssueKind.AMBIGUOUS_VALUE,
                    message=f"{case_path}={v!r} 模糊匹配到 {len(cands_dump)} 个候选",
                    candidates=cands_dump,
                    suggestion=suggestion,
                    auto_fixable=(len(cands_dump) == 1),
                ))

        # 4. 行业代码 + 经营范围一致性
        ind_code = case.get("phase1_industry_code") or case.get("itemIndustryTypeCode")
        ind_text = (case.get("phase1_industry_special")
                    or case.get("phase1_main_business_desc")
                    or case.get("industryTypeName")
                    or "")
        if ind_code:
            if not self.ind.is_valid_code(str(ind_code)):
                report.issues.append(ValidationIssue(
                    field_path="phase1_industry_code", case_value=ind_code,
                    level=IssueLevel.FAIL,
                    kind=IssueKind.INVALID_INDUSTRY_CODE,
                    message=f"行业代码 {ind_code} 不在 GB/T 4754-2017 树内",
                ))
            elif ind_text:
                # 看代码对应名称是否与 ind_text 关键词重叠
                rec = self.ind.lookup_by_code(str(ind_code))
                if rec and rec.name and ind_text:
                    # 简单包含检查（双向）
                    matched_kw = any(kw in rec.name for kw in [ind_text]) \
                                 or any(kw in ind_text for kw in [rec.name])
                    if not matched_kw:
                        # 用 search 拿 top 候选
                        cand_list = self.ind.search(ind_text, top_n=5)
                        cands_dump = [
                            {"code": c.code, "name": c.name, "score": c.score}
                            for c in cand_list
                        ]
                        if cand_list and cand_list[0].code != str(ind_code):
                            report.issues.append(ValidationIssue(
                                field_path="phase1_industry_code", case_value=ind_code,
                                level=IssueLevel.WARN,
                                kind=IssueKind.INDUSTRY_TEXT_MISMATCH,
                                message=(f"经营描述 {ind_text!r} 与行业代码 {ind_code} "
                                         f"({rec.name}) 语义不一致"),
                                candidates=cands_dump,
                                suggestion=cands_dump[0] if cands_dump else None,
                            ))
        elif ind_text:
            # 没有 code，但有文本 → 模糊匹配
            cand_list = self.ind.search(ind_text, top_n=5)
            cands_dump = [{"code": c.code, "name": c.name, "score": c.score}
                          for c in cand_list]
            if not cand_list:
                report.issues.append(ValidationIssue(
                    field_path="phase1_industry_code", case_value=None,
                    level=IssueLevel.FAIL,
                    kind=IssueKind.INVALID_INDUSTRY_CODE,
                    message=f"行业代码缺失，且经营描述 {ind_text!r} 无法匹配到任何候选",
                ))
            else:
                level = IssueLevel.AMBIGUOUS
                if self.ind.is_decisive(cand_list):
                    level = IssueLevel.WARN
                report.issues.append(ValidationIssue(
                    field_path="phase1_industry_code", case_value=None,
                    level=level,
                    kind=IssueKind.INVALID_INDUSTRY_CODE,
                    message=f"行业代码缺失，根据 {ind_text!r} 找到 {len(cand_list)} 个候选",
                    candidates=cands_dump,
                    suggestion=cands_dump[0],
                    auto_fixable=self.ind.is_decisive(cand_list),
                ))

        return report

    # ─── interactive resolve ──────────────────────

    def interactive_resolve(self, report: ValidationReport,
                            case: Dict[str, Any]) -> Dict[str, Any]:
        """对 ambiguous + 可询问的 issue 与用户交互，返回修正后的 case。

        FAIL 不在此处理（必须人工编辑 case）。
        """
        if report.fails:
            print("\n[!] 存在 FAIL 级问题，必须先在 case 文件中修正：")
            for it in report.fails:
                print(f"  - {it.field_path}: {it.message}")
            return case

        amb = report.ambiguous + [it for it in report.warns
                                  if it.candidates]
        if not amb:
            return case

        new_case = json.loads(json.dumps(case))
        for it in amb:
            print(f"\n[?] {it.message}")
            print(f"    case 当前值: {it.case_value!r}")
            options = [f"{c.get('code','')} {c.get('name','')}"
                       + (f"  (score={c.get('score',0)})" if c.get('score') is not None else "")
                       for c in it.candidates]
            options.append("[保留原值，跳过]")
            idx = self.prompt_fn(f"请为 {it.field_path} 选择正确值", options)
            if idx < 0 or idx == len(options) - 1:
                continue
            chosen = it.candidates[idx]
            self._apply_path(new_case, it.field_path, chosen.get("code") or chosen.get("name"))
            # 行业代码额外同步 industryTypeName
            if it.field_path in ("phase1_industry_code", "itemIndustryTypeCode"):
                new_case["phase1_industry_code"] = chosen.get("code")
                new_case["itemIndustryTypeCode"] = chosen.get("code")
                new_case["phase1_industry_name"] = chosen.get("name")
                new_case["industryTypeName"] = chosen.get("name")
        return new_case

    @staticmethod
    def _apply_path(case: Dict[str, Any], path: str, value: Any) -> None:
        parts = path.split(".")
        cur = case
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = value

    def write_report(self, report: ValidationReport, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.as_dict(), f, ensure_ascii=False, indent=2)
