"""
OptionsScout — 服务端组件 load 响应的枚举选项反向扫描器

工作流：
1. 给定一个已 load 过该组件的 busiData (load_resp.data.busiData)
2. 按字段名 / 值结构启发式提取枚举候选
3. 合并到 OptionDict，可持久化

启发式识别策略：
- 字段名以 List/Options/Arr/Enum/Dict/Items 结尾 → 检查 value 是否数组
- 数组元素是 dict 且含 (code/value/key/id) + (name/label/text/title) 双键 → 视为选项
- 字段名带 Code/Type/State/Status/Flag/Visage/Mode 后缀 → 候选为单值，需另收集

不会主动调网络。所有调用都由外部传入响应。
（独立调用入口：scripts/_run_options_scout.py 会先做完整扫描）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .option_dict import OptionDict

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════
# 启发式规则
# ════════════════════════════════════════════════

# 字段名以这些结尾 → 期望是选项数组
LIST_SUFFIXES = (
    "List", "Options", "Arr", "Enum",
    "Dict", "Items", "Array", "Set",
)

# code 候选键名
CODE_KEYS = ("code", "value", "key", "id", "itemValue", "dictCode",
             "dictValue", "optionValue", "tabId")
# name 候选键名
NAME_KEYS = ("name", "label", "text", "title", "displayName",
             "itemText", "dictName", "optionName", "tabName", "stateName")

# 一些字段单值上虽是 code，但语义为枚举（在选项 dict 里登记开放值）
SINGLE_FIELD_LIKELY_CODE = ("Code", "Type", "Status", "State", "Flag",
                            "Visage", "Mode", "Sex", "Country", "Degree")


# ════════════════════════════════════════════════
# 主类
# ════════════════════════════════════════════════

@dataclass
class ScoutFinding:
    """一次扫描的产物。"""
    component: str
    field_path: str
    options_count: int
    sample: List[Dict[str, Any]] = field(default_factory=list)


class OptionsScout:
    """从组件 busiData 中提取合法选项。

    使用方式：
        scout = OptionsScout(option_dict)
        scout.ingest_load_response(component="MemberInfo", load_resp=resp)
        scout.persist()    # 写到 options_dict.json
    """

    def __init__(self, option_dict: Optional[OptionDict] = None,
                 *, log: bool = True):
        self.opt = option_dict or OptionDict.load()
        self.log = log
        self.findings: List[ScoutFinding] = []

    # ─── 主入口 ─────────────────────────────────

    def ingest_load_response(self, *, component: str,
                             load_resp: Dict[str, Any]) -> List[ScoutFinding]:
        """从一次 component/loadBusinessDataInfo 响应里提取选项。

        Args:
            component: 组件名（如 "MemberInfo"）
            load_resp: client.post_json 的完整返回

        Returns:
            本次新增的 finding 列表
        """
        bd = (load_resp.get("data") or {}).get("busiData") or {}
        if not bd:
            return []
        new_findings = self._walk(bd, component, prefix="busiData")
        self.findings.extend(new_findings)
        return new_findings

    def ingest_busiData(self, *, component: str,
                        busi_data: Dict[str, Any]) -> List[ScoutFinding]:
        """直接传 busiData（如果你已经预先解析过）。"""
        if not busi_data:
            return []
        new_findings = self._walk(busi_data, component, prefix="busiData")
        self.findings.extend(new_findings)
        return new_findings

    # ─── 递归遍历 ───────────────────────────────

    def _walk(self, node: Any, component: str, prefix: str,
              depth: int = 0) -> List[ScoutFinding]:
        if depth > 6:
            return []
        out: List[ScoutFinding] = []
        if isinstance(node, dict):
            for k, v in node.items():
                path = f"{prefix}.{k}"
                # 1. List/Options 后缀 + 数组 → 候选枚举数组
                if isinstance(v, list) and v and self._is_list_suffix(k):
                    options = self._extract_options_from_list(v)
                    if options:
                        added = self.opt.upsert_options(
                            field_name=k,
                            options=options,
                            label=self._guess_label(k),
                            source=f"{component}.{path}",
                        )
                        out.append(ScoutFinding(
                            component=component,
                            field_path=path,
                            options_count=len(options),
                            sample=options[:3],
                        ))
                        if self.log:
                            print(f"[scout] {component}.{path}: +{added} options "
                                  f"(total candidates {len(options)})")
                # 2. dict → 递归
                elif isinstance(v, dict):
                    out.extend(self._walk(v, component, path, depth + 1))
                # 3. 数组的 dict 元素 → 递归（可能是 group）
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    # 这个可能不是枚举，但里面可能有嵌套枚举
                    out.extend(self._walk(v[0], component, path + "[0]", depth + 1))
        return out

    # ─── 启发式识别 ──────────────────────────────

    @staticmethod
    def _is_list_suffix(key: str) -> bool:
        return any(key.endswith(s) for s in LIST_SUFFIXES)

    @staticmethod
    def _extract_options_from_list(items: List[Any]) -> List[Dict[str, Any]]:
        """从数组里抽取符合 code+name 双键模式的元素。"""
        out: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            code = None
            name = None
            for k in CODE_KEYS:
                if k in it and it[k] not in (None, ""):
                    code = str(it[k])
                    break
            for k in NAME_KEYS:
                if k in it and it[k] not in (None, ""):
                    name = str(it[k])
                    break
            # 至少要有 name 才能算选项
            if name:
                out.append({"code": code or "", "name": name})
        return out

    @staticmethod
    def _guess_label(key: str) -> str:
        """从字段名猜中文 label（找不到就返回原 key）。"""
        # 简单 mapping，可后续扩展
        builtin = {
            "politicalStatusList": "政治面貌",
            "eduDegreeList": "学历",
            "cerTypeList": "证件类型",
            "sexList": "性别",
            "countryList": "国籍",
            "propertyUseModeList": "房产使用方式",
            "houseToBusList": "住改商",
            "yesOrNoList": "是否",
            "entTypeList": "企业类型",
        }
        return builtin.get(key, key)

    # ─── 持久化 ─────────────────────────────────

    def persist(self) -> Path:
        """把累积的 findings 写到 OptionDict 持久化路径。"""
        self.opt.save()
        return self.opt.path

    # ─── 作为 ICPSPClient 观察者 ───────────────────

    def as_observer(self):
        """返回可注册到 client.register_response_observer 的回调。

        只关心 loadBusinessDataInfo 类响应。从 path 提取组件名。
        """
        import re
        comp_re = re.compile(r"/component/([A-Za-z]+)/load")

        def _ob(path: str, body: dict, resp: dict) -> None:
            if "loadBusinessDataInfo" not in path:
                return
            m = comp_re.search(path)
            comp = m.group(1) if m else "Unknown"
            self.ingest_load_response(component=comp, load_resp=resp)
        return _ob

    def report(self) -> Dict[str, Any]:
        return {
            "total_findings": len(self.findings),
            "components_seen": sorted(set(f.component for f in self.findings)),
            "fields": [
                {"component": f.component, "path": f.field_path,
                 "options_count": f.options_count, "sample": f.sample}
                for f in self.findings
            ],
        }
