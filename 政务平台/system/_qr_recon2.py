#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""纯 HTTP 侦察 tyrz 扫码登录接口"""
import requests, re, json
from urllib.parse import urlencode, quote

requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
})

# Step 1: 访问 SSO 登录页（带完整 goto 参数，模拟 9087 enterprise-zone SSO 入口）
goto_raw = "https://tyrz.zwfw.gxzf.gov.cn/sso/oauth2/authorize?response_type=code&client_id=6305e208-a105-47e4-8ad8-d02db25e6bfb&redirect_uri=https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/sso/oauth2&scope=all&state="
import base64
goto_b64 = base64.b64encode(goto_raw.encode()).decode()

LOGIN_URL = f"https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?service=initService&goto={goto_b64}"
print(f"[1] GET {LOGIN_URL[:80]}...")
r = s.get(LOGIN_URL, allow_redirects=True)
print(f"    status={r.status_code} url={r.url[:100]}")
print(f"    cookies: {dict(s.cookies)}")

# 保存 HTML 方便分析
html = r.text
with open("g:/UFO/政务平台/packet_lab/out/_tyrz_login_page.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"    HTML saved ({len(html)} chars)")

# Step 2: 查找扫码相关的 JS 文件
print("\n[2] 分析页面 JS...")
scripts = re.findall(r'<script[^>]*src="([^"]*)"', html)
for s_url in scripts:
    print(f"    script: {s_url}")

# 查找 QR 相关的内联 JS
qr_patterns = re.findall(r'(qr[Cc]ode|scanCode|getQr|scan_login|polling|qrLogin|ewm|二维码|扫码)[^"\'<>]{0,100}', html, re.IGNORECASE)
for p in qr_patterns[:20]:
    print(f"    QR ref: {p[:100]}")

# Step 3: 查找 API 端点
api_patterns = re.findall(r'(?:url|href|src|action)\s*[:=]\s*["\']([^"\']*(?:qr|scan|code|login|auth)[^"\']*)["\']', html, re.IGNORECASE)
for a in api_patterns[:20]:
    print(f"    API: {a}")

# Step 4: 下载关键 JS 文件分析
print("\n[3] 下载并分析关键 JS 文件...")
for s_url in scripts:
    if any(kw in s_url.lower() for kw in ["login", "auth", "scan", "qr", "code", "tab"]):
        full_url = s_url if s_url.startswith("http") else f"https://tyrz.zwfw.gxzf.gov.cn{s_url}"
        print(f"\n  Fetching: {full_url}")
        try:
            jr = s.get(full_url)
            js = jr.text
            # 搜索 QR 相关代码
            for pattern in [r'qr[Cc]ode', r'scan', r'polling', r'getQr', r'ewm', r'/am/', r'oauth2', r'authorize']:
                matches = [(m.start(), js[max(0,m.start()-50):m.end()+100]) for m in re.finditer(pattern, js, re.IGNORECASE)]
                for pos, ctx in matches[:3]:
                    print(f"    [{pos}] ...{ctx.strip()[:150]}...")
        except Exception as e:
            print(f"    Error: {e}")

# Step 5: 检查是否有独立的扫码 API
print("\n[4] 尝试直接请求扫码接口...")
# 常见的 QR 接口模式
qr_endpoints = [
    "/am/auth/qrcode/generate",
    "/am/auth/qrcode/create",
    "/am/auth/scan/qrcode",
    "/am/qrcode/login",
    "/sso/qrcode/generate",
    "/portal/gxWeb/api/qrcode",
    "/am/auth/scanLogin/getQrCode",
]
for ep in qr_endpoints:
    url = f"https://tyrz.zwfw.gxzf.gov.cn{ep}"
    try:
        r2 = s.get(url, timeout=5)
        print(f"    GET {ep} → {r2.status_code} ({len(r2.text)} chars) {r2.text[:100]}")
    except Exception as e:
        print(f"    GET {ep} → error: {e}")

print("\nDone.")
