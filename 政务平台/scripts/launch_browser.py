#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动 Chrome Dev（CDP），参数统一来自 config/browser.json。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG = _ROOT / "config" / "browser.json"


def _load_cfg() -> Dict[str, Any]:
    with _CONFIG.open(encoding="utf-8") as f:
        return json.load(f)


def is_browser_running(port: int) -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{port}/json", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def launch_browser(no_proxy: bool = False, ignore_cert_errors: bool = False) -> bool:
    cfg = _load_cfg()
    port = int(cfg["cdp_port"])
    if is_browser_running(port):
        print(f"CDP 已可用: http://127.0.0.1:{port}/json")
        if ignore_cert_errors:
            print(
                "WARN: 已存在 Chrome 实例时无法注入证书忽略参数；请先关闭本机所有使用该 User Data 的 Chrome Dev 后再启动。",
                file=sys.stderr,
            )
        return True

    exe = cfg["executable"]
    exe_path = Path(exe)
    if not exe_path.is_file():
        print(f"ERROR: 找不到浏览器: {exe}", file=sys.stderr)
        return False

    udd = Path(cfg["user_data_dir"])
    udd.mkdir(parents=True, exist_ok=True)

    launch_args: List[str] = list(cfg.get("launch_args") or [])
    extra: List[str] = list(cfg.get("extra_chrome_args") or [])
    if no_proxy:
        extra = [x for x in extra if "--proxy-server=" not in x]
    if ignore_cert_errors:
        # 仅逆开发自测：绕过证书校验（包括 ERR_CERT_DATE_INVALID）。勿用于日常上网。
        extra = [x for x in extra if not x.startswith("--ignore-certificate-errors")]
        extra.append("--ignore-certificate-errors")

    argv: List[str] = [str(exe_path)]
    argv.extend(launch_args)
    argv.extend(extra)

    start_url = (cfg.get("start_url") or "").strip()
    if start_url:
        argv.append(start_url)

    print("启动:", exe_path)
    print("argv:", " ".join(argv[1:]))
    subprocess.Popen(argv, cwd=str(_ROOT))

    for i in range(20):
        time.sleep(1)
        if is_browser_running(port):
            print(f"CDP 就绪: http://127.0.0.1:{port}/json")
            return True

    print("ERROR: 等待 CDP 端口超时", file=sys.stderr)
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-proxy", action="store_true", help="Launch browser without --proxy-server args")
    ap.add_argument(
        "--ignore-cert-errors",
        action="store_true",
        help="DEV ONLY: add --ignore-certificate-errors (insecure; for expired/wrong TLS during local RE)",
    )
    args = ap.parse_args()
    sys.exit(0 if launch_browser(no_proxy=args.no_proxy, ignore_cert_errors=args.ignore_cert_errors) else 1)
