import json, time
from pathlib import Path

auth = "8819996a478d4961820cbe1602d8d38d"
out = Path("g:/UFO/政务平台/packet_lab/out/runtime_auth_headers.json")

headers = {
    "Authorization": auth,
    "language": "CH",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "sec-ch-ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

out.write_text(json.dumps({
    "headers": headers,
    "ts": int(time.time()),
    "method": "qrcode_login",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Token saved to {out}")
