"""禁用词库加载器：本地词库 + 从区划字典自动提取广西地名。

提供两种判定：
- check_banned(name_mark) → (is_banned, matched_words, category)
- 若 name_mark 含禁用词 → 短路拒绝，不进入 7 步 API 链
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
BANNED_WORDS_FILE = ROOT / "data" / "banned_words.json"
REGIONS_FILE = ROOT / "data" / "dictionaries" / "regions" / "root.json"


def _extract_all_region_names(node, out: set) -> None:
    """递归收集 regions 树里所有节点的 name（地名子串候选）。"""
    if not isinstance(node, dict):
        return
    nm = node.get("name") or node.get("regName")
    if isinstance(nm, str) and nm.strip():
        # 去掉行政区后缀，只保留裸词（"玉林市" → "玉林"）
        bare = nm.strip()
        for suffix in ["壮族自治区", "自治区", "省", "市", "区", "县", "旗"]:
            if bare.endswith(suffix) and len(bare) > len(suffix):
                bare = bare[: -len(suffix)]
                break
        if len(bare) >= 2:
            out.add(bare)
            out.add(nm.strip())
    for child in (node.get("children") or []):
        _extract_all_region_names(child, out)


@lru_cache(maxsize=1)
def load_banned_wordset() -> dict:
    """返回分类的禁用词集合：
    {
        "prohibited": set(禁止词),
        "restricted": set(限制词),
        "region_names": set(地名)
    }
    """
    prohibited: set = set()
    restricted: set = set()
    region_names: set = set()

    # 1) 手工词库 — 按分类名前缀自动归类
    if BANNED_WORDS_FILE.exists():
        try:
            data = json.loads(BANNED_WORDS_FILE.read_text(encoding="utf-8"))
            cats = data.get("categories", {})
            for cat_name, words in cats.items():
                if not isinstance(words, list):
                    continue
                low = cat_name.lower()
                if "禁止" in low or "禁用" in low or "地名" in low:
                    prohibited.update(words)
                elif "限制" in low:
                    restricted.update(words)
                else:
                    prohibited.update(words)
        except Exception:
            pass

    # 2) 从 regions 字典自动提取广西全区划名（覆盖县级 / 乡镇级）
    if REGIONS_FILE.exists():
        try:
            d = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))
            resp = d.get("data") or {}
            inner = resp.get("data") if isinstance(resp, dict) else None
            bd = inner.get("busiData") if isinstance(inner, dict) else resp.get("busiData")
            root = bd[0] if isinstance(bd, list) and bd else bd
            if isinstance(root, dict):
                tmp: set = set()
                _extract_all_region_names(root, tmp)
                region_names.update(tmp)
        except Exception:
            pass

    return {
        "prohibited": prohibited,
        "restricted": restricted,
        "region_names": region_names,
    }


def check_banned(name_mark: str) -> Tuple[bool, List[str], Optional[str]]:
    """检查 name_mark 是否含有禁用词。

    返回：(is_banned, matched_words, category)
        - category: "prohibited" | "restricted" | "region_name" | None
    """
    if not name_mark or not isinstance(name_mark, str):
        return False, [], None

    nm = name_mark.strip()
    wordset = load_banned_wordset()

    # 优先级：prohibited > region_name > restricted
    matched_prohibited = [w for w in wordset["prohibited"] if w and w in nm]
    if matched_prohibited:
        return True, matched_prohibited, "prohibited"

    # 地名：只有当 name_mark 里出现"其他省市地名"才算问题
    # 广西本地地名在前缀里是合法的（广西容县李陈梦），但 name_mark 本身含"桂林"就是问题
    # 为避免误杀，只命中"完整地名字符串"
    matched_region = [w for w in wordset["region_names"] if w and len(w) >= 2 and w in nm]
    # 排除 1 字地名（"北""南"等容易误伤）
    matched_region = [w for w in matched_region if len(w) >= 2]
    if matched_region:
        return True, matched_region, "region_name"

    matched_restricted = [w for w in wordset["restricted"] if w and w in nm]
    if matched_restricted:
        return False, matched_restricted, "restricted"  # 限制词不短路，但告知

    return False, [], None
