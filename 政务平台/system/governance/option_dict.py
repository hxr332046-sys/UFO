"""
OptionDict — 服务端合法选项字典的加载、查询、反哺

数据格式 (data/options_dict.json):
{
    "schema_version": "1.0",
    "last_updated": "2026-04-27T14:30:00",
    "fields": {
        "politicalStatus": {        # 字段名（与组件 busiData 字段对齐）
            "label": "政治面貌",
            "source": "MemberInfo.politicalStatus",
            "options": [
                {"code": "01", "name": "中共党员"},
                {"code": "13", "name": "群众"},
                ...
            ]
        },
        "propertyUseMode": { ... },
        "entType": [
            {"code": "4540", "name": "个人独资"},
            {"code": "1151", "name": "有限责任公司"},
            ...
        ]
    }
}
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════
# 数据类
# ════════════════════════════════════════════════

@dataclass
class OptionEntry:
    """一个合法选项。"""
    code: str
    name: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_label(self) -> str:
        """用于人类阅读的紧凑标签。"""
        if self.code and self.name:
            return f"{self.code}={self.name}"
        return self.code or self.name or "<unknown>"


@dataclass
class FieldOptions:
    """一个字段的合法选项集合。"""
    field_name: str
    label: str
    source: str                                # 来源组件路径，如 "MemberInfo.politicalStatus"
    options: List[OptionEntry] = field(default_factory=list)
    is_open: bool = False                      # True = 不限枚举（如 entName/cerNo 等自由文本）
    last_seen_iso: str = ""

    def find_by_code(self, code: str) -> Optional[OptionEntry]:
        if not code:
            return None
        for opt in self.options:
            if opt.code == code:
                return opt
        return None

    def find_by_name(self, name: str) -> Optional[OptionEntry]:
        if not name:
            return None
        for opt in self.options:
            if opt.name == name:
                return opt
        return None

    def search_by_keyword(self, keyword: str) -> List[OptionEntry]:
        """名称包含 keyword 的所有候选（不区分大小写）。"""
        if not keyword:
            return []
        kw = keyword.strip().lower()
        return [opt for opt in self.options
                if kw in (opt.name or "").lower()
                or kw in (opt.code or "").lower()]


# ════════════════════════════════════════════════
# 主类
# ════════════════════════════════════════════════

DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "options_dict.json"


class OptionDict:
    """全局服务端选项字典。

    使用方式：
        d = OptionDict.load()
        opt = d.get_field("politicalStatus")
        if opt and not opt.find_by_code("01"):
            print("01 不是合法政治面貌")

    反哺：
        d.upsert_options("politicalStatus", [{"code":"01","name":"中共党员"}], source="MemberInfo")
        d.save()
    """

    _instance: Optional["OptionDict"] = None
    _lock = threading.Lock()

    def __init__(self, fields: Dict[str, FieldOptions], path: Path):
        self.fields = fields
        self.path = path
        self.dirty = False

    # ─── load / save ───────────────────────────────

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "OptionDict":
        p = Path(path) if path else DEFAULT_PATH
        fields: Dict[str, FieldOptions] = {}
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for fname, fdata in (raw.get("fields") or {}).items():
                    opts = [
                        OptionEntry(
                            code=str(o.get("code", "")),
                            name=str(o.get("name", "")),
                            extra={k: v for k, v in o.items() if k not in ("code", "name")},
                        )
                        for o in (fdata.get("options") or [])
                    ]
                    fields[fname] = FieldOptions(
                        field_name=fname,
                        label=fdata.get("label", fname),
                        source=fdata.get("source", ""),
                        options=opts,
                        is_open=bool(fdata.get("is_open", False)),
                        last_seen_iso=fdata.get("last_seen", ""),
                    )
            except Exception as e:
                logger.warning("OptionDict.load failed: %s; fallback to empty.", e)
        return cls(fields, p)

    @classmethod
    def get(cls) -> "OptionDict":
        """单例懒加载（线程安全）。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls.load()
        return cls._instance

    def save(self) -> None:
        """持久化到 path。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "schema_version": "1.0",
            "last_updated": datetime.now().isoformat(timespec="seconds"),
            "fields": {
                f.field_name: {
                    "label": f.label,
                    "source": f.source,
                    "is_open": f.is_open,
                    "last_seen": f.last_seen_iso,
                    "options": [
                        {"code": o.code, "name": o.name, **o.extra}
                        for o in f.options
                    ],
                }
                for f in self.fields.values()
            },
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        self.dirty = False

    # ─── query ────────────────────────────────────

    def get_field(self, field_name: str) -> Optional[FieldOptions]:
        return self.fields.get(field_name)

    def has_field(self, field_name: str) -> bool:
        return field_name in self.fields and not self.fields[field_name].is_open

    def validate_value(self, field_name: str, value: Any) -> Tuple[str, Optional[OptionEntry], List[OptionEntry]]:
        """对单个字段值做合法性检查。

        返回：(status, matched, candidates)
            status: 'pass' | 'unknown_field' | 'open_field' | 'fail' | 'ambiguous'
            matched: 命中的合法选项（仅 pass 时非 None）
            candidates: 当 fail/ambiguous 时给出的候选
        """
        if value is None or value == "":
            return ("pass", None, [])
        f = self.fields.get(field_name)
        if f is None:
            return ("unknown_field", None, [])
        if f.is_open:
            return ("open_field", None, [])

        sval = str(value)

        # 1. 精确 code 命中
        opt = f.find_by_code(sval)
        if opt:
            return ("pass", opt, [])
        # 2. 精确 name 命中
        opt = f.find_by_name(sval)
        if opt:
            return ("pass", opt, [])
        # 3. 模糊关键词匹配
        candidates = f.search_by_keyword(sval)
        if len(candidates) == 1:
            return ("ambiguous", None, candidates)
        if candidates:
            return ("ambiguous", None, candidates[:5])
        return ("fail", None, [])

    # ─── upsert / 反哺 ────────────────────────────

    def upsert_options(self, field_name: str,
                       options: List[Dict[str, Any]],
                       *, label: str = "", source: str = "",
                       is_open: bool = False) -> int:
        """合并新选项到字段。返回新增数。

        - 已存在的 code 不会重复
        - is_open=True 的字段，即使有 options 也认为不限枚举
        """
        f = self.fields.get(field_name)
        if f is None:
            f = FieldOptions(
                field_name=field_name,
                label=label or field_name,
                source=source,
                options=[],
                is_open=is_open,
            )
            self.fields[field_name] = f

        if is_open:
            f.is_open = True

        existing_codes = {o.code for o in f.options}
        added = 0
        for o in options:
            code = str(o.get("code", "")).strip()
            name = str(o.get("name", "")).strip()
            if not code and not name:
                continue
            if code and code in existing_codes:
                continue
            f.options.append(OptionEntry(
                code=code,
                name=name,
                extra={k: v for k, v in o.items() if k not in ("code", "name")},
            ))
            existing_codes.add(code)
            added += 1

        f.last_seen_iso = datetime.now().isoformat(timespec="seconds")
        if source and not f.source:
            f.source = source
        if label and (not f.label or f.label == field_name):
            f.label = label

        if added > 0:
            self.dirty = True
        return added

    def mark_open(self, field_name: str, label: str = "", source: str = "") -> None:
        """显式声明字段为不限枚举（自由文本）。"""
        f = self.fields.get(field_name)
        if f is None:
            f = FieldOptions(
                field_name=field_name,
                label=label or field_name,
                source=source,
                options=[],
                is_open=True,
            )
            self.fields[field_name] = f
        else:
            f.is_open = True
            if label:
                f.label = label
            if source and not f.source:
                f.source = source
        self.dirty = True

    # ─── debug ───────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "field_count": len(self.fields),
            "fields": {
                k: {
                    "options_count": len(v.options),
                    "is_open": v.is_open,
                    "source": v.source,
                }
                for k, v in self.fields.items()
            },
        }
