"""检查当前 token 是否有效 — 多接口探测"""
import requests, json
requests.packages.urllib3.disable_warnings()

h = json.load(open("packet_lab/out/runtime_auth_headers.json", "r", encoding="utf-8"))["headers"]
auth = h.get("Authorization", "")
print(f"Token: {auth[:8]}... (len={len(auth)})")

BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api"
PX = {"https": None, "http": None}

tests = [
    ("getUserInfo", f"{BASE}/appinfo/getUserInfo"),
    ("checkEstablishName", f"{BASE}/icpspsupervise/EstablishInfo/checkEstablishName?entType=4540&distCode=450921&distCodeArr=450000,450900,450921"),
    ("getSysParam", f"{BASE}/appinfo/getSysParam"),
    ("loadCurrentLocation", f"{BASE}/icpspsupervise/EstablishInfo/loadCurrentLocationInfo"),
]

for name, url in tests:
    try:
        r = requests.get(url, headers=h, verify=False, timeout=10, proxies=PX)
        body = r.text[:150]
        print(f"\n[{name}] status={r.status_code}")
        print(f"  body: {body}")
    except Exception as e:
        print(f"\n[{name}] ERROR: {e}")
