"""
mitmdump addon: 捕获 producePdf 请求和响应，以及 YbbSelect save 请求和响应。
用于对比真实浏览器请求 vs Python 框架请求。
"""
import json
from pathlib import Path
from mitmproxy import http

OUT_DIR = Path(__file__).parent / "out" / "captured_producepdf"
TARGETS = [
    "producePdf",
    "YbbSelect/operationBusinessDataInfo",
    "YbbSelect/loadBusinessDataInfo",
    "loadCurrentLocationInfo",
    "PreElectronicDoc/loadBusinessDataInfo",
    "PreElectronicDoc/operationBusinessDataInfo",
    "preSubmit",
]

class ProducePdfCapture:
    def __init__(self):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.count = 0
        print(f"\n[监听] 捕获 producePdf 及相关请求")
        print(f"[目标] {TARGETS}")
        print(f"[输出] {OUT_DIR}\n")

    def request(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url
        matched = None
        for t in TARGETS:
            if t in url:
                matched = t
                break
        if not matched:
            return
        if flow.request.method != "POST":
            return
        body_bytes = flow.request.content
        if not body_bytes:
            return
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return
        
        self.count += 1
        fname = f"{self.count:03d}_req_{matched.replace('/', '_')}.json"
        with open(OUT_DIR / fname, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        print(f"[捕获请求] {fname}")
        
        # Store flow for response capture
        flow.metadata["capture_target"] = matched
        flow.metadata["capture_count"] = self.count

    def response(self, flow: http.HTTPFlow) -> None:
        target = flow.metadata.get("capture_target")
        count = flow.metadata.get("capture_count")
        if not target or not count:
            return
        
        resp_bytes = flow.response.content
        if not resp_bytes:
            return
        try:
            resp = json.loads(resp_bytes.decode("utf-8"))
        except Exception:
            return
        
        fname = f"{count:03d}_resp_{target.replace('/', '_')}.json"
        with open(OUT_DIR / fname, "w", encoding="utf-8") as f:
            json.dump(resp, f, ensure_ascii=False, indent=2)
        print(f"[捕获响应] {fname} code={resp.get('code')}")

addons = [ProducePdfCapture()]
