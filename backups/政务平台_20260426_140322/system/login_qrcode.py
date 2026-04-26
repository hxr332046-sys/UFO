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


def step6_browser_token(s: requests.Session) -> tuple:
    """通过浏览器 CDP 完成 SSO redirect 链并获取 token + SESSION cookie。

    高可靠流程（v2 — 2026-04-25 重构）：
      a) 清除旧 auth 状态
      b) 注入 SESSIONFORTYRZ（QR 登录建立的 SSO session）
      c) ★ 直接导航 SSO authorize URL（服务端 302 驱动，不依赖 SPA 异步 JS）
         → tyrz 验证 SESSIONFORTYRZ → 302 到 6087 → 302 到 ssc → Fetch 拦截 → 9087 SPA
      d) 导航 entservice → 获取 9087 Authorization token
      e) 提取 SESSION cookie（API 需要）

    返回: (auth_token, session_cookie) 或 ("", "")
    """
    print("[6] 浏览器完成 SSO redirect + 获取 token...")

    ws, _ = _connect_browser()
    if ws is None:
        return "", ""

    _id = [0]
    _session_cookie = [None]  # 通过闭包捕获

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
                    print(f"    [Fetch] 拦截 ssc → 302 到 9087 SPA")
                    _id[0] += 1
                    ws.send(json.dumps({"id": _id[0], "method": "Fetch.fulfillRequest",
                        "params": {"requestId": rid, "responseCode": 302,
                            "responseHeaders": [{"name": "Location",
                                "value": f"{PORTAL_9087}/icpsp-web-pc/#/index/page"}],
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

    def _wait_navigation(label, timeout_s=15):
        """等待页面导航完成（frameStoppedLoading 或超时）。"""
        ws.settimeout(2)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                msg = json.loads(ws.recv())
                # 处理 Fetch 拦截
                if msg.get("method") == "Fetch.requestPaused":
                    req = msg.get("params", {})
                    url = req.get("request", {}).get("url", "")
                    rid = req.get("requestId", "")
                    if "ssc.mohrss" in url:
                        print(f"    [{label}] 拦截 ssc → 302")
                        _id[0] += 1
                        ws.send(json.dumps({"id": _id[0], "method": "Fetch.fulfillRequest",
                            "params": {"requestId": rid, "responseCode": 302,
                                "responseHeaders": [{"name": "Location",
                                    "value": f"{PORTAL_9087}/icpsp-web-pc/#/index/page"}],
                                "body": ""}}))
                        continue
                    else:
                        _id[0] += 1
                        ws.send(json.dumps({"id": _id[0], "method": "Fetch.continueRequest",
                            "params": {"requestId": rid}}))
                        continue
                if msg.get("method") in ("Page.frameStoppedLoading", "Page.loadEventFired"):
                    break
            except Exception:
                pass
        ws.settimeout(60)

    def _grab_session_cookie():
        """从浏览器 cookies 中提取 9087 的 SESSION cookie。"""
        try:
            all_c = send_cmd("Network.getAllCookies").get("cookies", [])
            for c in all_c:
                if c["name"] == "SESSION" and "scjdglj" in c.get("domain", ""):
                    _session_cookie[0] = c["value"]
                    print(f"    SESSION cookie: {c['value'][:20]}... domain={c['domain']}")
                    return
        except Exception:
            pass

    # ── a) 清除旧 auth 状态 ──
    print("    清除旧 auth 状态...")
    send_cmd("Network.enable")
    send_cmd("Page.enable")
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
        return "", ""
    send_cmd("Network.setCookie", {
        "name": "SESSIONFORTYRZ",
        "value": tyrz_cookie,
        "domain": ".zwfw.gxzf.gov.cn",
        "path": "/",
        "secure": True,
        "httpOnly": True,
    })
    print(f"    注入 SESSIONFORTYRZ: {tyrz_cookie[:16]}...")

    # ── c) ★ 直接导航 SSO authorize URL（核心改进） ──
    #    不走 SPA hash 路由（异步不可控），直接用服务端 302 驱动整条 SSO 链。
    send_cmd("Fetch.enable", {"patterns": [
        {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"},
    ]})

    print("    导航 SSO authorize URL（服务端 302 驱动）...")
    send_cmd("Page.navigate", {"url": "about:blank"})
    time.sleep(0.5)
    send_cmd("Page.navigate", {"url": GOTO_RAW})
    _wait_navigation("SSO", timeout_s=30)

    try:
        send_cmd("Fetch.disable")
    except Exception:
        pass

    # 检查落地页
    href = ev("location.href") or ""
    print(f"    SSO 落地: {href[:80]}")
    if "tyrz" in href and "auth/login" in href:
        print("    ❌ SESSIONFORTYRZ 无效，被重定向到登录页")
        ws.close()
        return "", ""

    # ── d) entservice 取 9087 token（含重试） ──
    auth = ""
    for attempt in range(3):
        print(f"    导航 entservice... (尝试 {attempt+1}/3)")
        send_cmd("Page.navigate", {"url": SSO_ENTSERVICE})
        _wait_navigation("entservice", timeout_s=15)
        time.sleep(3)

        # 检查是否到达 chrome-error
        href = ev("location.href") or ""
        if href.startswith("chrome-error"):
            print(f"    ⚠ chrome-error，等待 3s 后重试...")
            time.sleep(3)
            continue
        if "tyrz" in href:
            print("    ⚠ 被重定向到 tyrz，SESSIONFORTYRZ 可能过期")
            break

        # 尝试读取 auth
        for wait_i in range(6):
            auth = ev("localStorage.getItem('Authorization') || ''") or ""
            if auth and len(auth) >= 16:
                break
            time.sleep(2)

        if auth and len(auth) >= 16:
            break

    if not auth or len(auth) < 16:
        # fallback: 直接导航 9087 SPA，SPA JS 可能自行完成 SSO
        print("    entservice 未获取 token，尝试 9087 SPA fallback...")
        send_cmd("Page.navigate", {"url": f"{PORTAL_9087}/icpsp-web-pc/"})
        _wait_navigation("SPA-fallback", timeout_s=15)
        time.sleep(5)
        auth = ev("localStorage.getItem('Authorization') || ''") or ""

    if auth and len(auth) >= 16:
        print(f"    ✓ Authorization: {auth[:8]}... (len={len(auth)})")
    else:
        print(f"    ❌ 未获取到 token")
        ws.close()
        return "", ""

    # ── e) 提取 SESSION cookie（API 需要） ──
    _grab_session_cookie()

    ws.close()
    return auth, _session_cookie[0] or ""


def save_token(auth: str, session_cookie: str = "") -> None:
    """保存 token + SESSION cookie 到 runtime_auth_headers.json"""
    RUNTIME_AUTH.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "Authorization": auth,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": f"{PORTAL_9087}",
        "Referer": f"{PORTAL_9087}/icpsp-web-pc/",
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
    # ★ SESSION cookie（9087 API 需要）
    if session_cookie:
        headers["Cookie"] = f"lastAuthType=ENT_SERVICE; SESSION={session_cookie}"
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
    if session_cookie:
        print(f"[sync] SESSION cookie 已包含在 headers.Cookie 中")


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
    auth, session_cookie = step6_browser_token(s)
    if not auth:
        return 1

    # 保存
    save_token(auth, session_cookie)
    print(f"\n✓ 登录成功! token={auth[:8]}... (len={len(auth)})")
    if session_cookie:
        print(f"  SESSION={session_cookie[:20]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
