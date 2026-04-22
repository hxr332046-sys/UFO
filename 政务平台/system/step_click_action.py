#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from cdp_helper import create_helper  # noqa: E402
from page_action_framework import SURVEY_JS, render_click_action_js  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="按页面普查索引执行单步点击")
    ap.add_argument("--index", required=True, type=int, help="step_probe_state 输出中的 actionables 索引")
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json")
    c = create_helper(9225)
    try:
        result = c.eval(render_click_action_js(args.index))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sleep_human(2.2)
        state = c.eval(SURVEY_JS)
        print(json.dumps(state, ensure_ascii=False, indent=2))
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
