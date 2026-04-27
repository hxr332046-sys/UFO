"""
IndustryMatcher — 经营范围/行业描述 → GB/T 4754-2017 行业代码模糊匹配

数据源：data/industry_gb4754_2017.json （门类→大类→中类→小类四层树）

匹配策略（三层）：
1. 精确匹配：name 完全相等 → 直接命中
2. 关键词包含：query 是 name 子串 / name 是 query 子串 → 收集
3. 字符级 score（fallback）：基于公共字符比例 + 子序列加权

返回：top-N 候选，按 score 降序；若 best score 远高于次优 → 标记为 "确定" 否则 "歧义"
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════
# 数据类
# ════════════════════════════════════════════════

@dataclass
class IndustryMatch:
    """单个匹配候选。"""
    code: str
    name: str          # 不含 [code] 前缀
    full_name: str     # 含 [code] 前缀（原始格式）
    level: int         # 1=门类, 2=大类, 3=中类, 4=小类
    parent_codes: List[str] = field(default_factory=list)  # 自上而下
    score: float = 0.0
    match_type: str = ""  # "exact" / "keyword" / "fuzzy"

    def as_label(self) -> str:
        return f"{self.code} {self.name}"


# ════════════════════════════════════════════════
# 主类
# ════════════════════════════════════════════════

DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "industry_gb4754_2017.json"

# 简单同义词词典（可外置成 JSON 后续扩展）
SYNONYM_GROUPS = [
    {"软件", "应用软件", "系统软件", "软件开发", "软件设计"},
    {"商贸", "贸易", "批发", "零售", "商品销售"},
    {"餐饮", "饭店", "餐厅", "小吃店"},
    {"咨询", "顾问", "咨询服务"},
    {"信息技术", "IT", "互联网", "计算机"},
    {"建筑", "建设", "施工", "土建"},
    {"运输", "物流", "货运"},
]


def _build_synonym_map() -> Dict[str, set]:
    m: Dict[str, set] = {}
    for grp in SYNONYM_GROUPS:
        for w in grp:
            m.setdefault(w, set()).update(grp)
    return m


SYNONYMS = _build_synonym_map()


def _strip_brackets(s: str) -> str:
    """去除 [4540] 前缀。"""
    return re.sub(r"^\[[^\]]+\]\s*", "", s or "")


def _char_overlap_score(a: str, b: str) -> float:
    """简单字符重叠 score：交集 / max(len)。"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = sa & sb
    return len(inter) / max(len(sa), len(sb))


def _subseq_score(query: str, target: str) -> float:
    """query 在 target 中的子序列覆盖度。

    例：'软件开发' vs '应用软件开发' → query 全部依序出现于 target → 1.0
    """
    if not query:
        return 0.0
    j = 0
    for ch in target:
        if j < len(query) and ch == query[j]:
            j += 1
    return j / len(query)


class IndustryMatcher:
    """行业匹配引擎。"""

    def __init__(self, tree: List[Dict[str, Any]]):
        self.tree = tree
        self._flat: List[Dict[str, Any]] = []      # [{code, name, level, parents}, ...]
        self._index_by_code: Dict[str, Dict[str, Any]] = {}
        self._flatten()

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "IndustryMatcher":
        p = Path(path) if path else DEFAULT_PATH
        if not p.exists():
            logger.warning("Industry tree file not found: %s; matcher will be empty.", p)
            return cls([])
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # 兼容两种格式：{data: [...]}  或  [...]
        tree = raw.get("data") if isinstance(raw, dict) else raw
        return cls(tree or [])

    def _flatten(self) -> None:
        """递归把树拉平。"""
        def walk(nodes: List[Dict[str, Any]], level: int, parents: List[str]) -> None:
            for n in nodes:
                code = str(n.get("code", "")).strip()
                full = str(n.get("name", "")).strip()
                name = _strip_brackets(full)
                rec = {
                    "code": code,
                    "name": name,
                    "full_name": full,
                    "level": level,
                    "parents": parents.copy(),
                }
                self._flat.append(rec)
                if code:
                    self._index_by_code[code] = rec
                children = n.get("children") or []
                if children:
                    walk(children, level + 1, parents + [code])

        walk(self.tree, 1, [])

    # ─── public API ────────────────────────────────

    def lookup_by_code(self, code: str) -> Optional[IndustryMatch]:
        """按代码精确查找。"""
        if not code:
            return None
        rec = self._index_by_code.get(str(code).strip())
        if not rec:
            return None
        return IndustryMatch(
            code=rec["code"],
            name=rec["name"],
            full_name=rec["full_name"],
            level=rec["level"],
            parent_codes=rec["parents"],
            score=1.0,
            match_type="exact",
        )

    def is_valid_code(self, code: str) -> bool:
        return self.lookup_by_code(code) is not None

    def search(self, query: str, *, top_n: int = 5,
               leaf_only: bool = True, min_score: float = 0.3) -> List[IndustryMatch]:
        """按文本搜索行业。

        Args:
            query: 经营范围 / 行业描述文本
            top_n: 返回候选数
            leaf_only: 仅返回小类（4 位代码），通常业务系统用小类
            min_score: 最低 score 阈值
        """
        if not query:
            return []
        q = query.strip()
        if not q:
            return []

        # 同义词扩展（query 包含的关键词关联词）
        expanded = {q}
        for w, syns in SYNONYMS.items():
            if w in q:
                expanded.update(syns)

        candidates: Dict[str, IndustryMatch] = {}

        for rec in self._flat:
            if leaf_only and rec["level"] < 4:
                continue
            name = rec["name"]
            full = rec["full_name"]

            best_score = 0.0
            mtype = ""

            # 1. 精确匹配
            if name == q or full == q:
                best_score = 1.0
                mtype = "exact"
            else:
                # 2. 关键词包含（任一扩展词命中）
                hit_keyword = False
                for w in expanded:
                    if w and (w in name or name in w):
                        hit_keyword = True
                        # 长度比作为 score（越接近 1 越好）
                        ratio = min(len(w), len(name)) / max(len(w), len(name))
                        score = 0.65 + 0.3 * ratio
                        if score > best_score:
                            best_score = score
                            mtype = "keyword"
                if not hit_keyword:
                    # 3. 字符 + 子序列混合 score
                    s_char = _char_overlap_score(q, name)
                    s_subseq = _subseq_score(q, name)
                    score = 0.4 * s_char + 0.6 * s_subseq
                    if score >= min_score:
                        best_score = score
                        mtype = "fuzzy"

            if best_score >= min_score:
                m = IndustryMatch(
                    code=rec["code"],
                    name=name,
                    full_name=full,
                    level=rec["level"],
                    parent_codes=rec["parents"],
                    score=round(best_score, 4),
                    match_type=mtype,
                )
                candidates[rec["code"]] = m

        sorted_list = sorted(candidates.values(), key=lambda x: -x.score)
        return sorted_list[:top_n]

    def is_decisive(self, matches: List[IndustryMatch],
                    *, gap_threshold: float = 0.15) -> bool:
        """判断 top1 是否压倒性优于 top2（不歧义）。"""
        if not matches:
            return False
        if len(matches) == 1:
            return matches[0].score >= 0.85
        return matches[0].score - matches[1].score >= gap_threshold and matches[0].score >= 0.7

    def explain(self, query: str, top_n: int = 5) -> Dict[str, Any]:
        """诊断输出（含同义词扩展记录）。"""
        results = self.search(query, top_n=top_n)
        return {
            "query": query,
            "expanded_keywords": sorted(set(
                w for grp_w, grp in SYNONYMS.items()
                for w in grp if grp_w in query
            )),
            "decisive": self.is_decisive(results),
            "candidates": [
                {
                    "code": m.code, "name": m.name,
                    "level": m.level, "score": m.score,
                    "match_type": m.match_type,
                }
                for m in results
            ],
        }
