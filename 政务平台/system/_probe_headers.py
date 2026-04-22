"""检查 9087 API 返回的完整 response headers"""
import requests, json
requests.packages.urllib3.disable_warnings()
px = {"https": None, "http": None}

h = json.load(open("packet_lab/out/runtime_auth_headers.json", "r", encoding="utf-8"))["headers"]

r = requests.get(
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/appinfo/getSysParam",
    headers=h, verify=False, timeout=10, proxies=px
)
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:200]}")
print("\nResponse Headers:")
for k, v in r.headers.items():
    print(f"  {k}: {v}")
