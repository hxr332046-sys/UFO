"""
mitmdump addon: 捕获 ComplementInfo/operationBusinessDataInfo POST body
用法: mitmdump -s packet_lab/mitm_capture_complement.py --ssl-insecure -p 8080
"""
import json
from pathlib import Path
from mitmproxy import http

OUT = Path(__file__).parent / "out" / "complement_info_save_body.json"
TARGET = "ComplementInfo/operationBusinessDataInfo"

class ComplementCapture:
    def __init__(self):
        print(f"\n[监听] 等待 {TARGET}...")
        print(f"[输出] {OUT}\n")
        self.captured = False

    def request(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url
        if TARGET in url and flow.request.method == "POST":
            body_bytes = flow.request.content
            print(f"\n✅ 捕获! URL: {url}")
            print(f"   大小: {len(body_bytes)} bytes")
            try:
                body = json.loads(body_bytes.decode("utf-8"))
                OUT.parent.mkdir(parents=True, exist_ok=True)
                with open(OUT, "w", encoding="utf-8") as f:
                    json.dump(body, f, ensure_ascii=False, indent=2)
                print(f"   保存到: {OUT}")
                print(f"   keys: {list(body.keys())}")
                pb = body.get("partyBuildDto","无")
                print(f"   partyBuildDto: {json.dumps(pb, ensure_ascii=False)[:400]}")
                print(f"   signInfo: {body.get('signInfo')}")
                print(f"   flowData.currCompUrl: {(body.get('flowData') or {}).get('currCompUrl')}")
                self.captured = True
            except Exception as e:
                print(f"   解析失败: {e}")
                with open(OUT.with_suffix(".raw.txt"), "wb") as f:
                    f.write(body_bytes)

addons = [ComplementCapture()]
