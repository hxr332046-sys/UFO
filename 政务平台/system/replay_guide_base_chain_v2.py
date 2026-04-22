#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
复现 guide/base -> 下一步 完整 HTTP 请求链 (v2 - 详细验证版)
"""

import json
import time
import random
import requests
from pathlib import Path

# 读取当前认证
AUTH_FILE = Path(__file__).resolve().parent.parent / "packet_lab" / "out" / "runtime_auth_headers.json"
with open(AUTH_FILE, 'r', encoding='utf-8') as f:
    auth_data = json.load(f)

headers = auth_data['headers'].copy()
base_headers = {
    'Authorization': headers['Authorization'],
    'language': headers.get('language', 'CH'),
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://zhjg.scjdglj.gxzf.gov.cn:9087',
    'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}
if 'top-token' in headers:
    base_headers['top-token'] = headers['top-token']

BASE = 'https://zhjg.scjdglj.gxzf.gov.cn:9087'

def jitter():
    delay = random.uniform(2.0, 4.0)
    print(f"  [delay {delay:.1f}s...]")
    time.sleep(delay)

def req_post(url, body, hdrs):
    print(f"\n  REQUEST:")
    print(f"    URL: {url}")
    print(f"    BODY: {json.dumps(body, ensure_ascii=False)[:300]}")
    resp = requests.post(url, headers=hdrs, json=body, timeout=30)
    print(f"  RESPONSE:")
    print(f"    STATUS: {resp.status_code}")
    try:
        data = resp.json()
        code = data.get('code', 'N/A')
        msg = data.get('msg', 'N/A')
        print(f"    code: {code}")
        print(f"    msg: {msg}")
        return resp.status_code == 200 and code == "00000", data
    except Exception as e:
        print(f"    PARSE ERROR: {e}")
        print(f"    TEXT: {resp.text[:200]}")
        return False, None

print("=" * 60)
print(" 重新验证: guide/base -> 下一步 HTTP API 重放")
print(f" Authorization: {base_headers['Authorization']}")
print("=" * 60)

# ===== STEP 1: checkEstablishName =====
print("\n[STEP 1] POST checkEstablishName")
jitter()
t1 = str(int(time.time() * 1000))
url1 = f"{BASE}/icpsp-api/v4/pc/register/guide/establishname/checkEstablishName?t={t1}"
body1 = {
    "entType": "4540",
    "nameCode": "0",
    "distCode": "450921",
    "streetCode": None,
    "streetName": None,
    "address": "广西壮族自治区玉林市容县",
    "rcMoneyKindCode": "",
    "distCodeArr": ["450000", "450900", "450921"],
    "fzSign": "N",
    "parentEntRegno": "",
    "parentEntName": "",
    "regCapitalUSD": ""
}
ok1, data1 = req_post(url1, body1, base_headers)
print(f"  RESULT: {'PASS' if ok1 else 'FAIL'}")

# ===== STEP 2: loadCurrentLocationInfo =====
print("\n[STEP 2] POST loadCurrentLocationInfo")
jitter()
t2 = str(int(time.time() * 1000))
url2 = f"{BASE}/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo?t={t2}"
body2 = {
    "flowData": {"busiId": "", "busiType": "01_4", "entType": "4540"},
    "linkData": {"token": ""}
}
ok2, data2 = req_post(url2, body2, base_headers)
print(f"  RESULT: {'PASS' if ok2 else 'FAIL'}")

# ===== STEP 3: operationBusinessDataInfo =====
print("\n[STEP 3] POST operationBusinessDataInfo (保存)")
jitter()
headers3 = base_headers.copy()
headers3['Referer'] = 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
t3 = str(int(time.time() * 1000))
url3 = f"{BASE}/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo?t={t3}"
body3 = {
    "areaCode": "450921",
    "namePre": "广西容县",
    "nameMark": "陈白",
    "allIndKeyWord": "",
    "showKeyWord": "",
    "noShowKeyWord": "实业,发展,实业发展,发展实业",
    "industrySpecial": "食品",
    "industry": "5225",
    "industryName": "营养和保健品零售",
    "multiIndustry": "",
    "multiIndustryName": "",
    "organize": "市（个人独资）",
    "parentEntName": "",
    "dyElement": "",
    "isCheckGroupName": "0",
    "jtEntName": "",
    "jtUniscId": "",
    "jtShForm": "",
    "spellType": "10",
    "name": "广西容县陈白食品市（个人独资）",
    "noIndSign": "N",
    "declarationMode": "N",
    "fisDistCode": "",
    "distCode": "450921",
    "streetCode": "",
    "entType": "4540",
    "fzSign": "N",
    "isCheckBox": "Y",
    "checkState": 1,
    "parentEntRegno": "",
    "bannedInfos": "",
    "hasParent": None,
    "needAudit": False,
    "tipKeyWords": "",
    "industryId": None,
    "flowData": {
        "busiId": None, "entType": "4540", "busiType": "01", "ywlbSign": "4",
        "busiMode": None, "nameId": None, "marPrId": None, "secondId": None,
        "vipChannel": "null", "currCompUrl": "NameCheckInfo", "status": "10",
        "matterCode": None, "interruptControl": None
    },
    "linkData": {
        "compUrl": "NameCheckInfo", "opeType": "save",
        "compUrlPaths": ["NameCheckInfo"], "busiCompUrlPaths": "%5B%5D", "token": ""
    },
    "extraDto": {
        "entType": "4540", "nameCode": "0", "distCode": "450921",
        "streetCode": None, "streetName": None,
        "address": "广西壮族自治区玉林市容县", "rcMoneyKindCode": "",
        "distCodeArr": ["450000", "450900", "450921"],
        "fzSign": "N", "parentEntRegno": "", "parentEntName": "", "regCapitalUSD": ""
    },
    "signInfo": "-252238669",
    "itemId": ""
}
ok3, data3 = req_post(url3, body3, headers3)
print(f"  RESULT: {'PASS' if ok3 else 'FAIL'}")
if data3:
    busi_id = data3.get('data',{}).get('busiData',{}).get('flowData',{}).get('busiId')
    print(f"  busiId: {busi_id}")

# ===== STEP 4: nameCheckRepeat =====
print("\n[STEP 4] POST nameCheckRepeat")
jitter()
body4 = {
    "condition": "1",
    "busiId": busi_id if busi_id else None,
    "busiType": "01",
    "entType": "4540",
    "name": "广西容县陈白食品市（个人独资）",
    "namePre": "广西容县",
    "nameMark": "陈白",
    "distCode": "450921",
    "areaCode": "450921",
    "organize": "市（个人独资）",
    "industry": "5225",
    "indSpec": "食品",
    "hasParent": None,
    "jtParentEntName": ""
}
t4 = str(int(time.time() * 1000))
url4 = f"{BASE}/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat?t={t4}"
ok4, data4 = req_post(url4, body4, headers3)
print(f"  RESULT: {'PASS' if ok4 else 'FAIL'}")
if data4:
    busi_data = data4.get('data',{}).get('busiData',{}) if isinstance(data4.get('data',{}), dict) else {}
    if isinstance(busi_data, dict):
        cs = busi_data.get('checkState')
        print(f"  checkState: {cs} (4=可申报有相似)")

print("\n" + "=" * 60)
all_ok = ok1 and ok2 and ok3 and ok4
print(f" 总体结果: {'全部通过' if all_ok else '部分失败'}")
print("=" * 60)
