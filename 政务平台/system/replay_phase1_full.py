#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第一阶段（名称登记）完整 HTTP API 重放
从 guide/base 直达 -> 申报成功
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
BASE = 'https://zhjg.scjdglj.gxzf.gov.cn:9087'

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

def jitter(min_sec=2.0, max_sec=4.0):
    delay = random.uniform(min_sec, max_sec)
    print(f"  [delay {delay:.1f}s...]")
    time.sleep(delay)

def post(url_path, body, referer=None):
    t = str(int(time.time() * 1000))
    url = f"{BASE}{url_path}?t={t}"
    hdrs = base_headers.copy()
    if referer:
        hdrs['Referer'] = referer
    
    print(f"\n>>> POST {url_path.split('/')[-1][:40]}")
    print(f"    URL: {url[:90]}...")
    
    try:
        resp = requests.post(url, headers=hdrs, json=body, timeout=30)
        print(f"    STATUS: {resp.status_code}")
        data = resp.json()
        code = data.get('code', 'N/A')
        print(f"    code: {code}, msg: {data.get('msg', '')}")
        return code == "00000", data
    except Exception as e:
        print(f"    ERROR: {e}")
        return False, None

print("=" * 70)
print(" 第一阶段（名称登记）完整 API 重放")
print(f" Authorization: {base_headers['Authorization'][:20]}...")
print("=" * 70)

busi_id = None
name_id = None

# ===== STEP 1: checkEstablishName =====
print("\n[STEP 1] 检查企业名称（新办）")
jitter(1, 2)
ok1, data1 = post(
    '/icpsp-api/v4/pc/register/guide/establishname/checkEstablishName',
    {
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
)
if not ok1:
    print("FAILED at step 1")
    exit(1)

# ===== STEP 2: loadCurrentLocationInfo =====
print("\n[STEP 2] 加载流程信息")
jitter()
ok2, data2 = post(
    '/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo',
    {
        "flowData": {"busiType": "01_4", "entType": "4540", "busiId": "", "vipChannel": "null"},
        "linkData": {"continueFlag": "continueFlag", "token": ""},
        "extraDto": {
            "entType": "4540", "nameCode": "0", "distCode": "450921",
            "streetCode": None, "streetName": None,
            "address": "广西壮族自治区玉林市容县", "rcMoneyKindCode": "",
            "distCodeArr": ["450000", "450900", "450921"],
            "fzSign": "N", "parentEntRegno": "", "parentEntName": "", "regCapitalUSD": ""
        }
    },
    referer='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
)
if not ok2:
    print("FAILED at step 2")
    exit(1)

# ===== STEP 3: NameCheckInfo/operationBusinessDataInfo (保存) =====
print("\n[STEP 3] 保存名称检查信息")
jitter()
ok3, data3 = post(
    '/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo',
    {
        "areaCode": "450921",
        "namePre": "玉林市容县",
        "nameMark": "顺利得",
        "allIndKeyWord": "",
        "showKeyWord": "",
        "noShowKeyWord": "实业,发展,实业发展,发展实业",
        "industrySpecial": "五金批发",
        "industry": "5174",
        "industryName": "五金产品批发",
        "multiIndustry": "",
        "multiIndustryName": "",
        "organize": "市（个人独资）",
        "parentEntName": "",
        "dyElement": "",
        "isCheckGroupName": "0",
        "jtEntName": "",
        "jtUniscId": "",
        "jtShForm": "",
        "spellType": "20",
        "name": "顺利得（玉林市容县）五金批发市（个人独资）",
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
            "compUrlPaths": ["NameCheckInfo"],
            "busiCompUrlPaths": "%5B%5D", "token": ""
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
    },
    referer='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
)
if not ok3:
    print("FAILED at step 3")
    exit(1)

# 提取 busiId
if data3 and 'data' in data3:
    busi_id = data3.get('data',{}).get('busiData',{}).get('flowData',{}).get('busiId')
    print(f"    >>> busiId generated: {busi_id}")

# ===== STEP 4: nameCheckRepeat =====
print("\n[STEP 4] 名称重复检查")
jitter()
ok4, data4 = post(
    '/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat',
    {
        "condition": "1",
        "busiId": busi_id,
        "busiType": "01",
        "entType": "4540",
        "name": "顺利得（玉林市容县）五金批发市（个人独资）",
        "namePre": "玉林市容县",
        "nameMark": "顺利得",
        "distCode": "450921",
        "areaCode": "450921",
        "organize": "市（个人独资）",
        "industry": "5174",
        "indSpec": "五金批发",
        "hasParent": None,
        "jtParentEntName": ""
    },
    referer='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
)
if not ok4:
    print("FAILED at step 4")
    exit(1)

check_state = None
if data4 and 'data' in data4:
    busi_data = data4.get('data',{}).get('busiData',{})
    if isinstance(busi_data, dict):
        check_state = busi_data.get('checkState')
        print(f"    >>> checkState: {check_state} (4=可申报有相似)")

# ===== STEP 5: NameShareholder/operationBusinessDataInfo (保存股东) =====
print("\n[STEP 5] 保存股东/投资人信息")
jitter()
ok5, data5 = post(
    '/icpsp-api/v4/pc/register/name/component/NameShareholder/operationBusinessDataInfo',
    {
        "id": None,
        "name": "黄永裕",
        "type": "20",
        "certificateType": "10",
        "certificateNo": "dB6OVFevfx79As5Vv2KXz4DalvTsXd+ARv34FklYoZUspv8NbaP91qAOdMagB7DfpdKWGMLRparIHiTU79G8KoTwXS6fR8pH5/Wl+hCKZUmPvdNyt7q56gRFMO7BU5UTcnInIDJHyYkAgZ99e+cTZzGTnPVcVJxFOb/aImmQazU=",
        "encryptedCertificateNo": None,
        "blicTypes": "",
        "blicNO": "",
        "encryptedBLicNO": None,
        "memberType": "",
        "nationalityCode": "156",
        "realInvestMoney": None,
        "realInvestMoneyType": "156",
        "realInvestMoneyName": "人民币",
        "moneyRatio": None,
        "tel": None,
        "encryptedTel": None,
        "entRepName": None,
        "entRepType": None,
        "entRepCerNo": None,
        "encryptedEntRepCerNo": None,
        "cardType": None,
        "apprType": None,
        "apprReason": None,
        "rcMoneyKindCode": "156",
        "registerCapital": None,
        "mcInvestNeedSign": "N",
        "idCardZmUuid": "uploadPluginValue",
        "idCardFmUuid": "uploadPluginValue",
        "fileSize": "5120",
        "cutImgSize": "5120",
        "flowData": {
            "busiId": busi_id, "entType": "4540", "busiType": "01", "ywlbSign": "4",
            "busiMode": None, "nameId": None, "marPrId": None, "secondId": None,
            "vipChannel": "null", "currCompUrl": "NameShareholder", "status": "10",
            "matterCode": None, "interruptControl": None
        },
        "linkData": {
            "compUrl": "NameShareholder", "opeType": "save",
            "compUrlPaths": ["NameSupplement", "NameShareholder"],
            "busiCompUrlPaths": "%5B%7B%22compUrl%22%3A%22NameSupplement%22%2C%22id%22%3A%22%22%7D%5D",
            "token": ""
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
    },
    referer='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
)
if not ok5:
    print("FAILED at step 5")
    exit(1)

# ===== STEP 6: NameSupplement/operationBusinessDataInfo (保存补充信息) =====
print("\n[STEP 6] 保存补充信息（行业、经营范围等）")
jitter()
ok6, data6 = post(
    '/icpsp-api/v4/pc/register/name/component/NameSupplement/operationBusinessDataInfo',
    {
        "industry": "5174",
        "industryName": "五金产品批发",
        "indChaEntFlag": "0",
        "indRegNo": None,
        "rcMoneyKindCode": "",
        "rcMoneyKindName": "人民币",
        "regCapUSDRate": None,
        "regCapRMBRate": None,
        "investMoney": None,
        "investAmountUSD": None,
        "investAmountRMB": None,
        "busiAreaName": "398DCEAC3527B5271B31A0B9F802567D22B32B75195FAF220258CF82E9A1595F052EA867A85AA16FD706A504F96FED23B5EC38ED415DA88761AEE9693574D9D3551A8852C169F68814DFCAEFF0F228587E2AB24FBCC73DDE274E375EDDA42205",
        "busiAreaCode": "F1129|M3056|CL006|F3249",
        "genBusiArea": "",
        "businessArea": "E6A3ED691AA9B5729EA60727FCD1743B1F8AC814C4643F345D77DD19B8194B05DC94C22D82FB0DE2982ABB50F114671C5528FAF0EF53D195600C825F7DCD69525851658E18801FA82FF7D2F23962B3026073B28DF7D7ECEFDF664C975B812AAAE79D2A0F4F0CDCD989942A05C796880A4169225BDA95572A81F1E7F19B2763D019B8A757749B8C861E8EDEEBE016065E215D985036165EF3ECEEF8E1F1C7D605F96BAF2C8BA2061A93107BDDB66B1DCA81C0094F49A6D4528326A862E0F27078DFB597A5EA62E9BAD887AC8183F0F47A",
        "busiAreaData": "B45218B2F145766A4A120A253AB7762A8C208CA6767822DFDE67D9F0CE2C5BC862DC6B86623C3D1C3D2F7E08A4C02615D59A5C78ED55685FD905F922E4B5DCA33D2A61CED73BE330DD7897469A72E9F095195D33614CB4E82145520A22EC55A2571E678BAFDF03413A51E4A45ED76DFD3A3B6BACDC499FE6BD3779F31EE4AEFEA04814F72AEE780FA6F156883A592B7E390575AF76155A434237AEB2D6E0FFF81371FED7DEFE8822B4E2BD4FD9A4E27134DC05E623F2B06DFBA9196FD6CD1B25F9EF9C7CA1549C2C66FBAECA24A41E41970F5FD595D96ED477294F99C846E1659FD980EA7BEEA3F34653765CEC7C7830421D24308795FFCBD76B9B79F6243571906A2E2EFC6BE87E5E3CC7A77771C61923A23C09BA4F294CC8D9D74062C1F022340FAD80AFE19E3BB67691C1514096B14A6A4C568A2E34E54EB90D7DC21D8121735E55BA37145042F2E3C33FE63C09E69817A1B3985F4AB3D344E369C7C5DAC7AE865DBDA955A67782711949826D2B84506A72AF8EB9F5C6B181FB02DF5FAD33FC10F507FA1F1B519CDE00F5BA148499364287C9C887CCB0E37584CF5B8FC106E71BC80298A037F04E4F3025A7D8D8244A299D0A67F79190813F9D8831DD46BFEDB33FE8B9D085D082969DA93632D31BBA0AE351B61DFE8963DEAEB5E2EFD6B275D91...",
        "flowData": {
            "busiId": busi_id, "entType": "4540", "busiType": "01", "ywlbSign": "4",
            "busiMode": None, "nameId": None, "marPrId": None, "secondId": None,
            "vipChannel": "null", "currCompUrl": "NameShareholder", "status": "10",
            "matterCode": None, "interruptControl": None
        },
        "linkData": {
            "compUrl": "NameSupplement", "opeType": "save",
            "compUrlPaths": ["NameSupplement"],
            "busiCompUrlPaths": "%5B%5D",
            "token": ""
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
    },
    referer='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
)
if not ok6:
    print("FAILED at step 6")
    exit(1)

# ===== STEP 7: name/submit (最终提交) =====
print("\n[STEP 7] 最终提交（申报）")
jitter()
ok7, data7 = post(
    '/icpsp-api/v4/pc/register/name/submit',
    {
        "flowData": {
            "busiId": busi_id, "entType": "4540", "busiType": "01", "ywlbSign": "4",
            "busiMode": None, "nameId": None, "marPrId": None, "secondId": None,
            "vipChannel": "null", "currCompUrl": "NameShareholder", "status": "10",
            "matterCode": None, "interruptControl": None
        },
        "linkData": {
            "compUrl": "NameSupplement",
            "compUrlPaths": ["NameSupplement"],
            "continueFlag": "",
            "token": ""
        },
        "extraDto": {
            "entType": "4540", "nameCode": "0", "distCode": "450921",
            "streetCode": None, "streetName": None,
            "address": "广西壮族自治区玉林市容县", "rcMoneyKindCode": "",
            "distCodeArr": ["450000", "450900", "450921"],
            "fzSign": "N", "parentEntRegno": "", "parentEntName": "", "regCapitalUSD": ""
        }
    },
    referer='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'
)
if not ok7:
    print("FAILED at step 7")
    exit(1)

# 检查结果
if data7 and 'data' in data7:
    flow_data = data7.get('data',{}).get('busiData',{}).get('flowData',{})
    if flow_data:
        status = flow_data.get('status')
        name_id = flow_data.get('nameId')
        print(f"    >>> status: {status} (51=申报完成)")
        print(f"    >>> nameId: {name_id}")

print("\n" + "=" * 70)
all_ok = ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok7
print(f" 结果: {'全部通过 - 第一阶段完成' if all_ok else '部分失败'}")
if all_ok:
    print(f" busiId: {busi_id}")
    print(f" nameId: {name_id}")
print("=" * 70)
