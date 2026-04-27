"""
政务平台治理子模块（governance）

提供四大能力：
- options_scout    : 反向扫描服务端组件 load 响应，沉淀合法选项字典
- industry_matcher : 经营范围文本 → GB/T 4754-2017 行业代码模糊匹配
- case_validator   : 启动前对 case JSON 做质检，不合法字段提前停下
- uncertainty_hook : 运行时遇未知 code/枚举关键词时主动 ask 用户

设计原则：
- 全部组件都可独立使用（不强依赖 SmartRegisterRunner）
- 字典/词典数据外置在 data/ 下，可热更新
- 任何不确定都不静默：ambiguous 必须停下询问用户
"""

from .option_dict import OptionDict, OptionEntry
from .industry_matcher import IndustryMatcher, IndustryMatch
from .case_validator import CaseValidator, ValidationReport, ValidationIssue
from .uncertainty_hook import UncertaintyHook
from .options_scout import OptionsScout, ScoutFinding

__all__ = [
    "OptionDict",
    "OptionEntry",
    "IndustryMatcher",
    "IndustryMatch",
    "CaseValidator",
    "ValidationReport",
    "ValidationIssue",
    "UncertaintyHook",
    "OptionsScout",
    "ScoutFinding",
]
