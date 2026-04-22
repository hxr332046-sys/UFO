#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
复现 guide/base -> 下一步 的完整 HTTP 请求链
使用当前最新认证头，按顺序重放
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
# 移除浏览器特有的头，保留必要的
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
LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "replay_results.jsonl"

def _jitter():
    time.sleep(random.uniform(2.0, 4.0))

def _log(step, status, detail):
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "step": step, "status": status, "detail": detail}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{step}] {status}: {detail}")

# 准备请求体（从 MITM 抓取的手动操作数据）
# 步骤1: checkEstablishName
step1_body = {
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

# 步骤2: loadCurrentLocationInfo
step2_body = {
    "flowData": {"busiId": "", "busiType": "01_4", "entType": "4540"},
    "linkData": {"token": ""}
}

# 步骤3: operationBusinessDataInfo
# signInfo 需要动态生成，先尝试直接用旧值，如果失败再处理
step3_body = {
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
        "busiId": None,
        "entType": "4540",
        "busiType": "01",
        "ywlbSign": "4",
        "busiMode": None,
        "nameId": None,
        "marPrId": None,
        "secondId": None,
        "vipChannel": "null",
        "currCompUrl": "NameCheckInfo",
        "status": "10",
        "matterCode": None,
        "interruptControl": None
    },
    "linkData": {
        "compUrl": "NameCheckInfo",
        "opeType": "save",
        "compUrlPaths": ["NameCheckInfo"],
        "busiCompUrlPaths": "%5B%5D",
        "token": ""
    },
    "extraDto": {
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
    },
    "signInfo": "-252238669",
    "itemId": ""
}

# 步骤4: nameCheckRepeat
step4_body = {
    "condition": "1",
    "busiId": None,
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

print("=" * 60)
print("开始重放 guide/base -> 下一步 请求链")
print(f"Authorization: {base_headers['Authorization']}")
print("=" * 60)

# ========== STEP 1 ==========
print("\n--- STEP 1: checkEstablishName ---")
_jitter()
t1 = str(int(time.time() * 1000))
url1 = f"{BASE}/icpsp-api/v4/pc/register/guide/establishname/checkEstablishName?t={t1}"
resp1 = requests.post(url1, headers=base_headers, json=step1_body, timeout=30)
_log("checkEstablishName", "OK" if resp1.status_code == 200 else "FAIL", f"status={resp1.status_code}")
try:
    data1 = resp1.json()
    code1 = data1.get('code')
    _log("checkEstablishName", "BUSINESS_OK" if code1 == "00000" else "BUSINESS_FAIL", f"code={code1}")
    print(f"  Response: code={code1}, data={json.dumps(data1.get('data',{}), ensure_ascii=False)[:200]}")
except Exception as e:
    _log("checkEstablishName", "PARSE_FAIL", str(e))
    data1 = None

# ========== STEP 2 ==========
print("\n--- STEP 2: loadCurrentLocationInfo ---")
_jitter()
t2 = str(int(time.time() * 1000))
url2 = f"{BASE}/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo?t={t2}"
resp2 = requests.post(url2, headers=base_headers, json=step2_body, timeout=30)
_log("loadCurrentLocationInfo", "OK" if resp2.status_code == 200 else "FAIL", f"status={resp2.status_code}")
try:
    data2 = resp2.json()
    code2 = data2.get('code')
    _log("loadCurrentLocationInfo", "BUSINESS_OK" if code2 == "00000" else "BUSINESS_FAIL", f"code={code2}")
    print(f"  Response: code={code2}")
except Exception as e:
    _log("loadCurrentLocationInfo", "PARSE_FAIL", str(e))
    data2 = None

# ========== STEP 3 ==========
print("\n--- STEP 3: operationBusinessDataInfo ---")
_jitter()
# 更新 Referer 到 core.html（跳转后）
headers3 = base_headers.copy()
headers3['Referer'] = 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
t3 = str(int(time.time() * 1000))
url3 = f"{BASE}/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo?t={t3}"
resp3 = requests.post(url3, headers=headers3, json=step3_body, timeout=30)
_log("operationBusinessDataInfo", "OK" if resp3.status_code == 200 else "FAIL", f"status={resp3.status_code}")
try:
    data3 = resp3.json()
    code3 = data3.get('code')
    _log("operationBusinessDataInfo", "BUSINESS_OK" if code3 == "00000" else "BUSINESS_FAIL", f"code={code3}")
    print(f"  Response: code={code3}, data={json.dumps(data3.get('data',{}), ensure_ascii=False)[:300]}")
    # 提取 busiId
    busi_id = data3.get('data',{}).get('busiData',{}).get('flowData',{}).get('busiId')
    _log("operationBusinessDataInfo", "BUSI_ID", f"busiId={busi_id}")
except Exception as e:
    _log("operationBusinessDataInfo", "PARSE_FAIL", str(e))
    data3 = None
    busi_id = None

# ========== STEP 4 ==========
print("\n--- STEP 4: nameCheckRepeat ---")
_jitter()
# 如果有 busiId，更新请求体
if busi_id:
    step4_body['busiId'] = busi_id
    _log("nameCheckRepeat", "UPDATE_BUSIID", f"busiId={busi_id}")

t4 = str(int(time.time() * 1000))
url4 = f"{BASE}/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat?t={t4}"
resp4 = requests.post(url4, headers=headers3, json=step4_body, timeout=30)
_log("nameCheckRepeat", "OK" if resp4.status_code == 200 else "FAIL", f"status={resp4.status_code}")
try:
    data4 = resp4.json()
    code4 = data4.get('code')
    _log("nameCheckRepeat", "BUSINESS_OK" if code4 == "00000" else "BUSINESS_FAIL", f"code={code4}")
    busi_data4 = data4.get('data',{}).get('busiData',{}) if isinstance(data4.get('data',{}), dict) else {}
    if isinstance(busi_data4, dict):
        check_state = busi_data4.get('checkState')
        _log("nameCheckRepeat", "CHECK_STATE", f"checkState={check_state}")
    print(f"  Response: code={code4}")
except Exception as e:
    _log("nameCheckRepeat", "PARSE_FAIL", str(e))

print("\n" + "=" * 60)
print("重放完成")
print(f"日志: {LOG}")
