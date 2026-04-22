#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
扫码登录 — QR 扫码部分纯 HTTP，token 获取通过浏览器 CDP。

流程：
  1) [HTTP] 访问 tyrz SSO 登录页，获取 csrf_token + session cookie
  2) [HTTP] 请求智桂通 QR 码（个人/法人扫码）
  3) [本地] 弹出 QR 码图片，等用户用智桂通APP扫码
  4) [HTTP] 轮询扫码结果
  5) [HTTP] 扫码成功后提交登录，建立 SESSIONFORTYRZ
  6) [CDP]  启动浏览器，注入 SSO cookie，导航 enterprise-zone 触发 SSO 链
  7) [CDP]  等待 SSO 完成，通过 entservice 获取 Authorization token
  8) 保存 token 到 runtime_auth_headers.json

注意：
  - tyrz 的 /sso/oauth2/authorize 路径在 nginx 层 404，纯 HTTP 无法完成
    OAuth2 redirect 链，必须通过浏览器页面导航完成。
  - SSO 链中 ssc.mohrss.gov.cn 二次验证通过 Fetch 拦截绕过。
  - 登录只执行一次，后续通过探测 session 状态获取 token。

用法：
  python system/login_qrcode.py
  python system/login_qrcode.py --user-type 2   # 法人扫码

退出码：
  0 — 登录成功，token 已保存
  1 — 登录失败
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

requests.packages.urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_AUTH = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"

# ── 常量 ──
TYRZ_BASE = "https://tyrz.zwfw.gxzf.gov.cn"
PORTAL_6087 = "https://zhjg.scjdglj.gxzf.gov.cn:6087"
PORTAL_9087 = "https://zhjg.scjdglj.gxzf.gov.cn:9087"

# SSO 入口（enterprise-zone 的 goto 参数，base64 编码）
GOTO_RAW = (
    f"{TYRZ_BASE}/sso/oauth2/authorize?"
    f"response_type=code&client_id=6305e208-a105-47e4-8ad8-d02db25e6bfb"
    f"&redirect_uri={PORTAL_6087}/TopIP/sso/oauth2&scope=all&state="
)
GOTO_B64 = base64.b64encode(GOTO_RAW.encode()).decode()
LOGIN_PAGE = f"{TYRZ_BASE}/am/auth/login?service=initService&goto={GOTO_B64}"

# QR 接口
QR_GET = f"{TYRZ_BASE}/am/qrCode/getQrcode"
QR_CHECK = f"{TYRZ_BASE}/am/qrCode/checkQrCode"
QR_SUBMIT = f"{TYRZ_BASE}/am/auth/submitLogin"
QR_RANDOM = f"{TYRZ_BASE}/am/veryCode/getSessionRandom"

# entservice
SSO_ENTSERVICE = f"{PORTAL_9087}/icpsp-api/sso/entservice?targetUrlKey=02_0002"


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _create_session() -> requests.Session:
    """创建不走代理的 HTTP Session"""
    s = requests.Session()
    s.verify = False
    s.proxies = {"https": None, "http": None}
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    return s


def step1_get_login_page(s: requests.Session) -> str:
    """访问登录页，拿 csrf_token + SESSIONFORTYRZ cookie"""
    print("[1] 获取登录页...")
    r = s.get(LOGIN_PAGE, timeout=15)
    r.raise_for_status()

    # 从 HTML 解析 csrfToken
    m = re.search(r"var\s+csrfToken\s*=\s*'([^']*)'", r.text)
    if not m:
        m = re.search(r'var\s+csrfToken\s*=\s*"([^"]*)"', r.text)
    csrf = m.group(1) if m else ""

    session_cookie = s.cookies.get("SESSIONFORTYRZ", "")
    print(f"    csrf_token: {csrf[:16]}...")
    print(f"    SESSIONFORTYRZ: {session_cookie[:16]}...")
    return csrf


def step2_get_qrcode(s: requests.Session, user_type: int = 2) -> tuple:
    """请求 QR 码，返回 (sessionId, qr_image_bytes)"""
    type_name = "法人" if user_type == 2 else "个人"
    print(f"[2] 获取{type_name}扫码二维码...")

    # getQrcode 前需要先 getRandom
    try:
        s.get(QR_RANDOM, timeout=5)
    except Exception:
        pass

    r = s.post(QR_GET, data={"userType": user_type}, timeout=15)
    r.raise_for_status()
    d = r.json()

    data = d.get("data", {})
    session_id = data.get("sessionId", "")
    qr_b64 = data.get("qrCode", "")

    if not session_id or not qr_b64:
        print(f"    ERROR: 无法获取二维码 — {json.dumps(d, ensure_ascii=False)[:100]}")
        return "", b""

    # 解码 base64 图片
    if qr_b64.startswith("data:"):
        _, encoded = qr_b64.split(",", 1)
        qr_bytes = base64.b64decode(encoded)
    else:
        qr_bytes = base64.b64decode(qr_b64)

    print(f"    sessionId: {session_id}")
    print(f"    QR 图片: {len(qr_bytes)} bytes")
    return session_id, qr_bytes


def step3_show_qrcode(qr_bytes: bytes) -> str:
    """保存并打开 QR 码图片"""
    qr_path = ROOT / "packet_lab" / "out" / "login_qrcode.png"
    qr_path.parent.mkdir(parents=True, exist_ok=True)
    qr_path.write_bytes(qr_bytes)
    print(f"[3] 二维码已保存: {qr_path}")

    # Windows 下用默认图片查看器打开
    try:
        if sys.platform == "win32":
            os.startfile(str(qr_path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(qr_path)])
        else:
            subprocess.Popen(["xdg-open", str(qr_path)])
        print("    已打开二维码图片，请用智桂通APP扫码...")
    except Exception as e:
        print(f"    无法自动打开图片: {e}")
        print(f"    请手动打开: {qr_path}")

    return str(qr_path)


def step4_poll_scan(s: requests.Session, session_id: str, timeout_sec: int = 120) -> bool:
    """轮询扫码结果"""
    print(f"[4] 等待扫码... (最长 {timeout_sec} 秒)")
    deadline = time.time() + timeout_sec
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        time.sleep(5)
        try:
            r = s.post(QR_CHECK, data={"random": session_id}, timeout=10)
            d = r.json()
        except Exception as e:
            print(f"    [{attempt}] 轮询异常: {e}")
            continue

        status = d.get("status", "")
        data = d.get("data", "")
        if status == "success":
            if data == "1":
                print(f"    [{attempt}] 扫码成功!")
                return True
            elif data == "3":
                print(f"    [{attempt}] 用户信息不存在，请注册后再登录")
                return False
            else:
                print(f"    [{attempt}] 扫码失败: data={data}")
                return False
        else:
            remaining = int(deadline - time.time())
            print(f"    [{attempt}] 等待中... (剩余 {remaining}s)", end="\r")

    print("\n    超时，未收到扫码确认")
    return False


def step5_submit_login(s: requests.Session, csrf: str, session_id: str) -> str:
    """提交扫码登录，返回 redirect URL"""
    print("[5] 提交登录...")

    # submitLogin 前需要 getRandom
    try:
        s.get(QR_RANDOM, timeout=5)
    except Exception:
        pass

    r = s.post(QR_SUBMIT, data={
        "csrf_token": csrf,
        "qrCode": session_id,
    }, timeout=15)
    d = r.json()

    if d.get("result"):
        redirect_url = d.get("data", "")
        user_type_resp = d.get("userType", "")
        print(f"    登录成功! userType={user_type_resp}")
        print(f"    redirect: {redirect_url}")
        print(f"    cookies after login: {[f'{c.name}={c.value[:20]}... domain={c.domain}' for c in s.cookies]}")
        return redirect_url
    else:
        print(f"    登录失败: {d.get('msg', json.dumps(d, ensure_ascii=False)[:100])}")
        return ""


def _connect_browser() -> tuple:
    """连接或启动浏览器，返回 (ws, cdp_port) 或 (None, 0)"""
    import websocket as ws_lib

    browser_cfg = ROOT / "config" / "browser.json"
    cdp_port = 9225
    if browser_cfg.exists():
        cfg = json.loads(browser_cfg.read_text(encoding="utf-8"))
        cdp_port = cfg.get("cdp_port", 9225)

    # 尝试连接已有浏览器
    target = None
    try:
        tabs = requests.get(f"http://127.0.0.1:{cdp_port}/json",
                            timeout=3, proxies={"https": None, "http": None}).json()
        for t in tabs:
            if t.get("type") == "page" and not t.get("url", "").startswith("devtools"):
                target = t
                break
    except Exception:
        pass

    if not target:
        # 启动浏览器
        launch_script = ROOT / "scripts" / "launch_browser.py"
        if launch_script.exists():
            subprocess.Popen([sys.executable, str(launch_script)],
                             cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("    浏览器启动中...")
            time.sleep(6)
        for _ in range(10):
            try:
                tabs = requests.get(f"http://127.0.0.1:{cdp_port}/json",
                                    timeout=3, proxies={"https": None, "http": None}).json()
                for t in tabs:
                    if t.get("type") == "page" and not t.get("url", "").startswith("devtools"):
                        target = t
                        break
                if target:
                    break
            except Exception:
                time.sleep(1)

    if not target:
        print("    ERROR: 无法连接浏览器 CDP")
        return None, 0

    ws = ws_lib.create_connection(target["webSocketDebuggerUrl"], timeout=60)
    return ws, cdp_port


def step6_browser_token(s: requests.Session) -> str:
    """通过浏览器 CDP 完成 SSO redirect 链并获取 token。

    正确流程（基于实测探路）：
      a) 清除旧 auth 状态
      b) 注入 SESSIONFORTYRZ（QR 登录建立的 SSO session）
      c) 导航 enterprise-zone → 触发 SSO → Fetch 拦截 ssc → 到 6087 portal
      d) 导航 6087 portal 确认 session
      e) 导航 entservice → 获取 9087 Authorization token

    注意：整个过程只导航不登录，保持类人节奏。
    """
    print("[6] 浏览器完成 SSO redirect + 获取 token...")

    ws, _ = _connect_browser()
    if ws is None:
        return ""

    _id = [0]

    def send_cmd(method, params=None):
        _id[0] += 1
        mid = _id[0]
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            # 内联处理 Fetch 事件
            if msg.get("method") == "Fetch.requestPaused":
                req = msg.get("params", {})
                url = req.get("request", {}).get("url", "")
                rid = req.get("requestId", "")
                if "ssc.mohrss" in url:
                    print(f"    [Fetch] 拦截 ssc → 302 到 6087 portal")
                    _id[0] += 1
                    ws.send(json.dumps({"id": _id[0], "method": "Fetch.fulfillRequest",
                        "params": {"requestId": rid, "responseCode": 302,
                            "responseHeaders": [{"name": "Location",
                                "value": f"{PORTAL_6087}/TopIP/web/web-portal.html#/index/page"}],
                            "body": ""}}))
                else:
                    _id[0] += 1
                    ws.send(json.dumps({"id": _id[0], "method": "Fetch.continueRequest",
                        "params": {"requestId": rid}}))
                continue
            if msg.get("id") == mid:
                return msg.get("result", {})

    def ev(expr):
        r = send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
        return r.get("result", {}).get("value")

    # ── a) 清除旧 auth 状态 ──
    print("    清除旧 auth 状态...")
    send_cmd("Network.enable")
    try:
        all_cookies = send_cmd("Network.getAllCookies").get("cookies", [])
        for c in all_cookies:
            d = c.get("domain", "")
            if any(k in d for k in ["scjdglj", "zwfw", "mohrss", "tyrz"]):
                send_cmd("Network.deleteCookies", {
                    "name": c["name"], "domain": d, "path": c.get("path", "/")})
    except Exception:
        pass
    for origin in [f"{PORTAL_9087}", f"{PORTAL_6087}"]:
        try:
            send_cmd("Storage.clearDataForOrigin", {
                "origin": origin, "storageTypes": "local_storage,session_storage"})
        except Exception:
            pass
    time.sleep(0.5)

    # ── b) 注入 SESSIONFORTYRZ cookie ──
    tyrz_cookie = s.cookies.get("SESSIONFORTYRZ", "")
    if not tyrz_cookie:
        print("    ERROR: 无 SESSIONFORTYRZ cookie")
        ws.close()
        return ""
    send_cmd("Network.setCookie", {
        "name": "SESSIONFORTYRZ",
        "value": tyrz_cookie,
        "domain": ".zwfw.gxzf.gov.cn",
        "path": "/",
        "secure": True,
        "httpOnly": True,
    })
    print(f"    注入 SESSIONFORTYRZ: {tyrz_cookie[:16]}...")

    # ── c) 启用 Fetch + 导航 enterprise-zone ──
    send_cmd("Fetch.enable", {"patterns": [
        {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"},
    ]})

    EZ_URL = f"{PORTAL_9087}/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"
    send_cmd("Page.navigate", {"url": "about:blank"})
    time.sleep(1)
    print("    导航 enterprise-zone...")
    send_cmd("Page.navigate", {"url": EZ_URL})

    # 主动读 WS 消息以处理 Fetch 事件（最多 40s）
    deadline = time.time() + 40
    ws.settimeout(3)
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except Exception:
            # 超时 → 检查页面状态
            href = ev("location.href") or ""
            if "6087" in href or "enterprise" in href:
                break  # SSO 完成或不需要 SSO
            if "tyrz" in href and "auth/login" in href:
                print("    SSO session 过期，tyrz 登录页")
                send_cmd("Fetch.disable")
                ws.close()
                return ""
            continue
        if msg.get("method") == "Fetch.requestPaused":
            req = msg.get("params", {})
            url = req.get("request", {}).get("url", "")
            rid = req.get("requestId", "")
            if "ssc.mohrss" in url:
                print(f"    拦截 ssc: {url[:50]}")
                _id[0] += 1
                ws.send(json.dumps({"id": _id[0], "method": "Fetch.fulfillRequest",
                    "params": {"requestId": rid, "responseCode": 302,
                        "responseHeaders": [{"name": "Location",
                            "value": f"{PORTAL_6087}/TopIP/web/web-portal.html#/index/page"}],
                        "body": ""}}))
                break
            else:
                _id[0] += 1
                ws.send(json.dumps({"id": _id[0], "method": "Fetch.continueRequest",
                    "params": {"requestId": rid}}))

    ws.settimeout(60)
    try:
        send_cmd("Fetch.disable")
    except Exception:
        pass

    # ── d) 到 6087 portal 确认 session ──
    time.sleep(3)
    PORTAL_URL = f"{PORTAL_6087}/TopIP/web/web-portal.html#/index/page"
    print("    导航 6087 portal 确认 session...")
    send_cmd("Page.navigate", {"url": PORTAL_URL})
    time.sleep(5)
    top = ev("localStorage.getItem('top-token') || ''") or ""
    print(f"    6087 top-token: {top[:25]}{'...' if top else '<empty>'}")

    # ── e) entservice 取 9087 token ──
    print("    导航 entservice...")
    send_cmd("Page.navigate", {"url": SSO_ENTSERVICE})
    time.sleep(8)

    auth = ev("localStorage.getItem('Authorization') || ''") or ""
    if auth and len(auth) >= 16:
        print(f"    Authorization: {auth[:8]}... (len={len(auth)})")
        ws.close()
        return auth

    # 等待几轮
    for i in range(8):
        time.sleep(2)
        auth = ev("localStorage.getItem('Authorization') || ''") or ""
        if auth and len(auth) >= 16:
            print(f"    Authorization: {auth[:8]}... (len={len(auth)})")
            ws.close()
            return auth
        href = ev("location.href") or ""
        if "tyrz" in href:
            print("    被重定向到 tyrz，SSO session 无效")
            ws.close()
            return ""
        print(f"    等待... ({i+1}/8) {href[:60]}")

    ws.close()
    print(f"    未获取到 token")
    return ""


def save_token(auth: str) -> None:
    """保存 token 到 runtime_auth_headers.json"""
    RUNTIME_AUTH.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "Authorization": auth,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": f"{PORTAL_9087}",
        "Referer": f"{PORTAL_9087}/icpsp-web-pc/portal.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "sec-ch-ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    RUNTIME_AUTH.write_text(
        json.dumps({
            "headers": headers,
            "ts": int(time.time()),
            "created_at": _now(),
            "method": "qrcode_login",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[sync] Token 已保存: {RUNTIME_AUTH}")


def main():
    parser = argparse.ArgumentParser(description="智桂通扫码登录（纯HTTP）")
    parser.add_argument("--user-type", type=int, default=1, choices=[1, 2],
                        help="1=个人扫码（默认）, 2=法人扫码")
    parser.add_argument("--timeout", type=int, default=120,
                        help="扫码等待超时秒数（默认120）")
    args = parser.parse_args()

    s = _create_session()

    # Step 1: 登录页
    csrf = step1_get_login_page(s)
    if not csrf:
        print("ERROR: 无法获取 csrf_token")
        return 1

    # Step 2: 获取二维码
    session_id, qr_bytes = step2_get_qrcode(s, args.user_type)
    if not session_id:
        return 1

    # Step 3: 显示二维码
    step3_show_qrcode(qr_bytes)

    # Step 4: 等待扫码
    if not step4_poll_scan(s, session_id, args.timeout):
        return 1

    # Step 5: 提交登录
    redirect_url = step5_submit_login(s, csrf, session_id)
    if not redirect_url:
        return 1

    # Step 6: 浏览器完成 SSO redirect + 获取 token
    auth = step6_browser_token(s)
    if not auth:
        return 1

    # 保存
    save_token(auth)
    print(f"\n✓ 登录成功! token={auth[:8]}... (len={len(auth)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
