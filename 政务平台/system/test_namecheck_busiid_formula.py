import json
import time
from pathlib import Path

import requests

AUTH = Path('packet_lab/out/runtime_auth_headers.json')
auth = json.loads(AUTH.read_text(encoding='utf-8'))
headers = auth['headers'].copy()
headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://zhjg.scjdglj.gxzf.gov.cn:9087',
    'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html',
})
BASE = 'https://zhjg.scjdglj.gxzf.gov.cn:9087'

def post(path, body):
    url = f"{BASE}{path}?t={int(time.time()*1000)}"
    r = requests.post(url, headers=headers, json=body, timeout=60)
    print(path, 'status=', r.status_code)
    data = r.json()
    print('  code=', data.get('code'), 'resultType=', (data.get('data') or {}).get('resultType') if isinstance(data.get('data'), dict) else None)
    return data

step5 = {
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
repeat_body = {
    "condition": "1",
    "busiId": None,
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
}

print('STEP A: first save')
a = post('/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo', step5)
print('STEP B: repeat')
b = post('/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat', repeat_body)

busi = (b.get('data') or {}).get('busiData') if isinstance(b.get('data'), dict) else None
step7 = json.loads(json.dumps(step5))
step7['checkState'] = busi.get('checkState') if isinstance(busi, dict) else 4
step7['bannedInfos'] = busi.get('bannedInfos') if isinstance(busi, dict) else None
step7['tipKeyWords'] = busi.get('tipKeyWords') if isinstance(busi, dict) else None
step7['nameCheckDTO'] = busi
print('STEP C: second save with nameCheckDTO')
c = post('/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo', step7)
cf = ((c.get('data') or {}).get('busiData') or {}).get('flowData') if isinstance((c.get('data') or {}).get('busiData'), dict) else {}
print('FINAL busiId=', cf.get('busiId'))
print('FINAL status=', cf.get('status'))
