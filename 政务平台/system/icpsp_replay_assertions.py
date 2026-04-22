#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对 mitm 重放结果做轻量断言（回归 / 面板验收）。"""
from __future__ import annotations

from typing import Any, Dict, List


def _get_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if part == "":
            continue
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def apply_replay_assertions(replay_result: Dict[str, Any], assertions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    assertions 示例：
      {"type": "http_status", "equals": 200}
      {"type": "json_field_equals", "path": "code", "value": "00000"}
      {"type": "json_field_in", "path": "code", "values": ["00000", "0"]}
    """
    failures: List[Dict[str, Any]] = []
    if replay_result.get("error"):
        failures.append({"assertion": "_replay", "detail": replay_result.get("error")})

    for i, a in enumerate(assertions or []):
        t = (a.get("type") or "").strip()
        try:
            if t == "http_status":
                exp = a.get("equals")
                got = replay_result.get("http_status")
                if got != exp:
                    failures.append({"i": i, "type": t, "expected": exp, "got": got})
            elif t == "json_field_equals":
                path = str(a.get("path") or "")
                exp = a.get("value")
                j = replay_result.get("resp_json")
                got = _get_path(j, path) if path else None
                if got != exp:
                    failures.append({"i": i, "type": t, "path": path, "expected": exp, "got": got})
            elif t == "json_field_in":
                path = str(a.get("path") or "")
                vals = a.get("values") or []
                j = replay_result.get("resp_json")
                got = _get_path(j, path) if path else None
                if got not in vals:
                    failures.append({"i": i, "type": t, "path": path, "expected_one_of": vals, "got": got})
            elif t == "no_replay_error":
                if replay_result.get("error"):
                    failures.append({"i": i, "type": t, "detail": replay_result.get("error")})
            else:
                if t:
                    failures.append({"i": i, "type": t, "detail": "unknown_assertion_type"})
        except Exception as e:
            failures.append({"i": i, "type": t, "detail": repr(e)})

    return {"ok": len(failures) == 0, "failures": failures, "checked": len(assertions or [])}
