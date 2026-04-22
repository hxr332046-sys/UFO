#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用 mitm 抓包中的登录态（Authorization / Cookie 等）按顺序重放一段请求，复现你在浏览器里的操作链。

仅用于自有环境、自有账号的协议逆向与自动化验证；勿对他人系统或未授权数据使用。

用法（示例：从第 309 行开始重放最多 60 条，即跳过前 308 行）：
  cd G:\\UFO\\政务平台
  .\\.venv-portal\\Scripts\\python.exe system\\replay_mitm_flow_slice.py --mitm dashboard/data/records/mitm_ufo_flows.jsonl --skip-lines 308 --max 60

登录态来源：每条 mitm 记录里的 req_headers（与当时浏览器一致）。Token 过期会 401，需重新抓包或改用 CDP 实时读 localStorage。

图形化：见 packet_lab/replay_lab_ui.py（不写死路径，界面里可改 mitm / skip / max）。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

from mitm_replay_core import load_icpsp_slice, replay_one_record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mitm", type=Path, default=Path("dashboard/data/records/mitm_ufo_flows.jsonl"))
    ap.add_argument("--skip-lines", type=int, default=0, help="Skip first N lines (e.g. 308 to start from line 309)")
    ap.add_argument("--max", type=int, default=80, help="Max records to replay")
    ap.add_argument("--pause-ms", type=int, default=0, help="Sleep between requests (ms)")
    ap.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("dashboard/data/records/replay_mitm_flow_slice.json"),
    )
    args = ap.parse_args()

    mitm: Path = args.mitm
    if not mitm.is_file():
        raise SystemExit(f"mitm file not found: {mitm.resolve()}")

    sess = requests.Session()
    steps: List[Dict[str, Any]] = []
    slice_rows = load_icpsp_slice(mitm, args.skip_lines, args.max)

    for line_no, rec in slice_rows:
        step = replay_one_record(sess, rec, line_no)
        steps.append(step)
        if args.pause_ms > 0:
            time.sleep(args.pause_ms / 1000.0)
        if step.get("error"):
            break

    out = {
        "mitm": str(mitm.resolve()),
        "skip_lines": args.skip_lines,
        "max": args.max,
        "replayed_count": len(steps),
        "steps": steps,
        "note": "Login state was taken from each mitm line req_headers (Authorization/Cookie). If 401, token expired — re-capture or use CDP localStorage.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", args.out.resolve(), "steps", len(steps))


if __name__ == "__main__":
    main()
