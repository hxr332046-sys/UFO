"""
UncertaintyHook — 运行时不确定停下钩子

挂在 Pipeline 上，监听每步响应：
- 未知 code（不在 ERROR_DICT 内 + ok=False）
- msg 含关键词（"请选择"/"不在范围内"/"不存在"/"无效"/"未知" 等）
- result_type=2 但当前不是核名步

满足任一 → 抛 InterventionSignal，Pipeline 停下交给上层处理。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from orchestrator.core import (
    Hook, InterventionSignal, PipelineContext, StepResult, StepSpec,
)
try:
    from orchestrator.intelligence import _CODE_POLICIES as ERROR_DICT
except ImportError:
    ERROR_DICT = {}

logger = logging.getLogger(__name__)


# 默认提示关键词（中文）
DEFAULT_MSG_KEYWORDS: List[str] = [
    "请选择", "不在范围", "不存在", "无效", "未知",
    "不允许", "不被允许", "不支持", "请填写", "必填",
    "格式错误", "格式不正确", "应为", "未注册",
]

# 已知良性 code（即便 ok=False 也不触发）
BENIGN_CODES: Set[str] = {
    "00000",
    "D0010",  # 当前表单无需填写
    "D0018",  # 业务状态变化
    "D0021",  # 可选组件不可用
    "STEP_POSITION_GUARD",
    "SKIP",
}


class UncertaintyHook(Hook):
    """监测响应里的"不确定信号"。

    use cases:
    - 服务端返回了一个我们没在错误字典里登记的 code
    - msg 含明显的"枚举要求"关键词
    - 业务上不该出现的 result_type=2

    所有触发都通过 InterventionSignal 传递给上层。
    """

    priority = 45  # 在 ThrottleHook(40) 之后、StateExtractorHook 之前

    def __init__(self,
                 *,
                 msg_keywords: Optional[List[str]] = None,
                 known_codes: Optional[Set[str]] = None,
                 enable_unknown_code: bool = True,
                 enable_keyword: bool = True,
                 enable_rt2_outside_namecheck: bool = True):
        self.msg_keywords = list(msg_keywords) if msg_keywords else list(DEFAULT_MSG_KEYWORDS)
        self.known_codes = set(known_codes) if known_codes else set(ERROR_DICT.keys()) | BENIGN_CODES
        self.enable_unknown_code = enable_unknown_code
        self.enable_keyword = enable_keyword
        self.enable_rt2_outside_namecheck = enable_rt2_outside_namecheck

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        # 跳过良性步骤
        if result.ok and not result.message:
            return
        if result.code in BENIGN_CODES and result.ok:
            return

        # 检查 1: 未知 code
        if self.enable_unknown_code and not result.ok:
            code = result.code
            if code and code not in self.known_codes:
                self._raise_unknown_code(step, result)

        # 检查 2: 关键词匹配
        if self.enable_keyword and result.message:
            hit = self._match_keywords(result.message)
            if hit:
                self._raise_keyword(step, result, hit)

        # 检查 3: rt=2 出现在非核名步
        if self.enable_rt2_outside_namecheck:
            tag = (step.tag or "").lower()
            is_namecheck = "p1_core" in tag or "p1_query" in tag or "namecheck" in step.name.lower()
            if result.result_type == "2" and not is_namecheck:
                self._raise_rt2(step, result)

    # ─── raise helpers ─────────────────────────────

    def _match_keywords(self, message: str) -> Optional[str]:
        msg = message or ""
        for kw in self.msg_keywords:
            if kw in msg:
                return kw
        return None

    def _raise_unknown_code(self, step: StepSpec, result: StepResult) -> None:
        diag = {
            "trigger": "unknown_code",
            "step": step.name,
            "code": result.code,
            "message": result.message,
            "raw_response": result.raw_response,
        }
        raise InterventionSignal(
            kind="uncertain_unknown_code",
            diagnostics=diag,
            options=["abort", "continue", "retry"],
            message=(f"步骤 {step.name} 返回未知 code={result.code}，"
                     f"msg={result.message!r}，需要人工判断。"),
        )

    def _raise_keyword(self, step: StepSpec, result: StepResult, hit_kw: str) -> None:
        diag = {
            "trigger": "keyword_in_message",
            "step": step.name,
            "code": result.code,
            "message": result.message,
            "matched_keyword": hit_kw,
            "raw_response": result.raw_response,
        }
        raise InterventionSignal(
            kind="uncertain_keyword",
            diagnostics=diag,
            options=["abort", "continue", "retry"],
            message=(f"步骤 {step.name} 响应里含关键词 {hit_kw!r}，"
                     f"通常意味着字段值不合法或缺失，需要人工判断。"),
        )

    def _raise_rt2(self, step: StepSpec, result: StepResult) -> None:
        diag = {
            "trigger": "rt2_outside_namecheck",
            "step": step.name,
            "code": result.code,
            "rt": result.result_type,
            "message": result.message,
            "raw_response": result.raw_response,
        }
        raise InterventionSignal(
            kind="uncertain_rt2",
            diagnostics=diag,
            options=["abort", "continue"],
            message=(f"步骤 {step.name} 返回 result_type=2（非核名步骤通常不应出现），"
                     f"需要人工判断。"),
        )
