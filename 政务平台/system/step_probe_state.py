#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
单步协同 - 页面状态探测器
探测当前CDP页面的类型、按钮、弹窗、表单摘要
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from cdp_helper import create_helper
from page_action_framework import SURVEY_JS

STATE_PROBE_JS = SURVEY_JS

def probe():
    cdp = create_helper(9225)
    try:
        state = cdp.eval(STATE_PROBE_JS)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return state
    finally:
        cdp.close()

if __name__ == "__main__":
    probe()
