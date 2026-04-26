"""
mitmdump addon: 捕获多个 establish 组件的 operationBusinessDataInfo body
"""
import json
from pathlib import Path
from mitmproxy import http

OUT_DIR = Path(__file__).parent / "out" / "captured_bodies"
TARGETS = [
    "TaxInvoice/operationBusinessDataInfo",
    "SlUploadMaterial/operationBusinessDataInfo",
    "BusinessLicenceWay/operationBusinessDataInfo",
    "PreSubmit/operationBusinessDataInfo",
    "operationBusinessDataInfo",   # 兜底
]

class MultiCapture:
    def __init__(self):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"\n[监听] 捕获所有 establish 组件 save 请求")
        print(f"[输出] {OUT_DIR}\n")

    def request(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url
        if "operationBusinessDataInfo" not in url:
            return
        if flow.request.method != "POST":
            return
        body_bytes = flow.request.content
        if not body_bytes:
            return

        # 提取组件名
        comp = "unknown"
        for part in url.split("/"):
            if part in ("TaxInvoice","SlUploadMaterial","BusinessLicenceWay",
                        "PreSubmit","ComplementInfo","BasicInfo","Rules"):
                comp = part
                break

        print(f"\n✅ [{comp}] {url[-60:]}")
        print(f"   大小: {len(body_bytes)} bytes")
        try:
            body = json.loads(body_bytes.decode("utf-8"))
            out_f = OUT_DIR / f"{comp}_save_body.json"
            with open(out_f, "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False, indent=2)
            print(f"   → {out_f.name}")
            print(f"   keys: {list(body.keys())}")
            fd = body.get("flowData") or {}
            ld = body.get("linkData") or {}
            print(f"   flowData.currCompUrl={fd.get('currCompUrl')} busiType={fd.get('busiType')}")
            print(f"   linkData.opeType={ld.get('opeType')}")
            # 打印各组件特有字段
            for k in ("partyBuildDto","taxDto","taxInfoDto","materialList","licenceWayDto"):
                if k in body and body[k] is not None:
                    print(f"   {k}: {json.dumps(body[k], ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"   解析失败: {e}")
            (OUT_DIR / f"{comp}_raw.bin").write_bytes(body_bytes)

addons = [MultiCapture()]
