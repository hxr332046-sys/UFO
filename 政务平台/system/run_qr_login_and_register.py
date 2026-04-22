#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键流程：QR扫码登录 → 第一阶段名称登记

流程：
  1. 检查现有 token 是否有效
  2. 若无效 → QR 扫码登录获取新 token
  3. 执行 Phase1 名称登记（7步协议链）
  4. 输出 busiId

用法：
  python system/run_qr_login_and_register.py
  python system/run_qr_login_and_register.py --case docs/case_广西容县李陈梦.json
  python system/run_qr_login_and_register.py --skip-login   # 跳过登录，直接用现有token
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

requests.packages.urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
AUTH_FILE = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
DEFAULT_CASE = ROOT / "docs" / "case_广西容县李陈梦.json"
BASE_9087 = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
PX = {"https": None, "http": None}


def check_token() -> str | None:
    """检查现有 token 是否有效，返回 token 或 None"""
    if not AUTH_FILE.exists():
        return None
    try:
        h = json.loads(AUTH_FILE.read_text(encoding="utf-8"))["headers"]
    except Exception:
        return None
    auth = h.get("Authorization", "")
    if len(auth) < 16:
        return None

    # 用 getSysParam 验证（轻量级接口）
    try:
        r = requests.get(
            f"{BASE_9087}/icpsp-api/appinfo/getSysParam",
            headers=h, verify=False, timeout=10, proxies=PX,
        )
        d = r.json()
        if d.get("success") or d.get("code") == "00000":
            return auth
    except Exception:
        pass
    return None


def check_server_health() -> bool:
    """检查 9087 后端是否健康"""
    try:
        r = requests.get(
            f"{BASE_9087}/icpsp-api/",
            verify=False, timeout=5, proxies=PX,
        )
        d = r.json()
        # 无 auth 时应返回 "用户认证失败" 而非 500
        if r.status_code == 200 and "认证" in d.get("msg", ""):
            return True
        if r.status_code == 500:
            return False
        return r.status_code < 500
    except Exception:
        return False


def qr_login() -> str | None:
    """执行 QR 扫码登录，返回 token 或 None"""
    print("\n" + "=" * 60)
    print("  QR 扫码登录")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(ROOT / "system" / "login_qrcode.py"), "--timeout", "180"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("QR 登录失败")
        return None
    # 重新读取 token
    try:
        h = json.loads(AUTH_FILE.read_text(encoding="utf-8"))["headers"]
        return h.get("Authorization", "")
    except Exception:
        return None


def run_phase1(case_path: Path) -> int:
    """执行 Phase1 名称登记"""
    print("\n" + "=" * 60)
    print("  Phase 1 名称登记")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(ROOT / "system" / "phase1_protocol_driver.py"),
         "--case", str(case_path), "--verbose"],
        cwd=str(ROOT),
    )
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="QR登录 + Phase1 名称登记")
    parser.add_argument("--case", type=str, default=str(DEFAULT_CASE),
                        help="Case JSON 文件路径")
    parser.add_argument("--skip-login", action="store_true",
                        help="跳过登录，直接用现有 token")
    parser.add_argument("--wait-server", action="store_true",
                        help="服务不可用时等待而非退出")
    args = parser.parse_args()

    case_path = Path(args.case)
    if not case_path.exists():
        print(f"ERROR: case 文件不存在: {case_path}")
        return 2

    # 1. 检查服务器健康
    print("[0] 检查 9087 后端服务...")
    if not check_server_health():
        if args.wait_server:
            print("    服务不可用，等待恢复...")
            for i in range(30):  # 最多等 15 分钟
                time.sleep(30)
                if check_server_health():
                    print(f"    服务已恢复! (等了 {(i+1)*30}s)")
                    break
                print(f"    [{i+1}/30] 仍不可用...")
            else:
                print("    服务持续不可用，退出")
                return 5
        else:
            print("    9087 后端不可用（500），可能在维护")
            print("    加 --wait-server 可等待恢复")
            return 5

    print("    9087 后端正常 ✓")

    # 2. 检查 token
    if not args.skip_login:
        print("\n[1] 检查现有 token...")
        token = check_token()
        if token:
            print(f"    Token 有效: {token[:8]}... ✓")
        else:
            print("    Token 无效或不存在，需要 QR 登录")
            token = qr_login()
            if not token:
                return 1
            print(f"    新 Token: {token[:8]}... ✓")
    else:
        print("\n[1] 跳过登录检查")

    # 3. Phase1 名称登记
    print(f"\n[2] 执行名称登记: {case_path.name}")
    rc = run_phase1(case_path)

    if rc == 0:
        print("\n" + "=" * 60)
        print("  ✓ 第一阶段完成!")
        print("=" * 60)
    else:
        print(f"\n第一阶段返回码: {rc}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
