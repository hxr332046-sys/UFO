#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
类人节奏：在 CDP 动作之间加入乘子与轻微随机抖动，避免比真人快太多导致
Vue 未渲染完、接口未返回、或触发「请勿重复提交」、风控限流等。

**产品要求**：对政务类站点须默认保持类人行为；勿为跑通脚本而压到机器极限。
配置：config/human_pacing.json。命令行 --human-fast 仅用于本机调试，不用于对线上压测。
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

_cfg: Dict[str, Any] = {}


# 默认下限：每次「业务动作」间隔不低于 1s（与 config/human_pacing.json、框架文档一致）
_DEFAULT_MIN_DELAY_SEC = 1.0


def configure_human_pacing(path: Optional[Path] = None, *, fast: bool = False) -> None:
    global _cfg
    if fast:
        _cfg = {"multiplier": 1.0, "jitter_ratio": 0.0, "min_delay_sec": 0.06}
        return
    defaults: Dict[str, Any] = {
        "multiplier": 1.55,
        "jitter_ratio": 0.14,
        "min_delay_sec": _DEFAULT_MIN_DELAY_SEC,
    }
    _cfg = dict(defaults)
    if path and path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # 忽略仅说明用字段
                raw = {k: v for k, v in raw.items() if not str(k).startswith("_")}
                _cfg.update(raw)
        except Exception:
            pass
    # 非 fast：业务侧不允许低于 1s 下限（防风控；可被配置显式覆盖为更大，不得更小）
    try:
        mn = float(_cfg.get("min_delay_sec") or _DEFAULT_MIN_DELAY_SEC)
        if mn < _DEFAULT_MIN_DELAY_SEC:
            _cfg["min_delay_sec"] = _DEFAULT_MIN_DELAY_SEC
    except (TypeError, ValueError):
        _cfg["min_delay_sec"] = _DEFAULT_MIN_DELAY_SEC


def sleep_human(base_seconds: float) -> None:
    """在 base_seconds 上乘以 multiplier，并加 ±jitter_ratio 抖动；实际休眠不低于 min_delay_sec（默认 ≥1s）。"""
    if base_seconds <= 0:
        return
    m = float(_cfg.get("multiplier") or 1.55)
    j = float(_cfg.get("jitter_ratio") or 0.14)
    mn = float(_cfg.get("min_delay_sec") or _DEFAULT_MIN_DELAY_SEC)
    delay = max(mn, base_seconds * m * (1.0 + random.uniform(-j, j)))
    time.sleep(delay)
