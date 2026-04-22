#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""快速测试 tyrz 扫码 API"""
import requests, re, json
requests.packages.urllib3.disable_warnings()

s = requests.Session()
s.verify = False
s.proxies = {"https": None, "http": None}  # 不走代理
s.timeout = 10

# 1. 拿 csrf + session cookie
print("[1] GET login page...")
r = s.get("https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?service=initService")
csrf = re.findall(r'var csrfToken\s*=\s*"([^"]*)', r.text)
print(f"  csrf: {csrf}")
print(f"  cookie: {s.cookies.get_dict()}")

# 2. 获取二维码
print("\n[2] POST getQrcode (userType=2 法人)...")
r2 = s.post("https://tyrz.zwfw.gxzf.gov.cn/am/qrCode/getQrcode", data={"userType": 2})
d = r2.json()
print(f"  response keys: {list(d.keys())}")
if "data" in d and isinstance(d["data"], dict):
    print(f"  data keys: {list(d['data'].keys())}")
    sid = d["data"].get("sessionId", "")
    qr = d["data"].get("qrCode", "")
    print(f"  sessionId: {sid}")
    print(f"  qrCode type: {'base64 img' if qr.startswith('data:') else 'url' if qr.startswith('http') else 'text'}")
    print(f"  qrCode length: {len(qr)}")
    print(f"  qrCode preview: {qr[:80]}...")
else:
    print(f"  raw: {json.dumps(d, ensure_ascii=False)[:200]}")

print("\nDone.")
