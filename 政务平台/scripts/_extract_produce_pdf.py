"""Extract producePdf requests from mitm flows to understand correct body"""
import json, sys
from pathlib import Path

for f in Path("dashboard/data/records").glob("mitm_*.jsonl"):
    print(f"\n=== {f.name} ===")
    for i, line in enumerate(f.open(encoding="utf-8"), 1):
        try:
            rec = json.loads(line)
        except:
            continue
        url = rec.get("url", "")
        if "producePdf" not in url:
            continue
        body = rec.get("body") or rec.get("request_body") or ""
        resp = rec.get("response") or rec.get("resp") or ""
        method = rec.get("method", "")
        status = rec.get("status") or rec.get("response_status") or ""
        
        # Parse body if string
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except:
                pass
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except:
                pass
        
        resp_code = ""
        if isinstance(resp, dict):
            resp_code = resp.get("code", "")
        
        print(f"\n  Line {i}: method={method} status={status} resp_code={resp_code}")
        if isinstance(body, dict):
            fd = body.get("flowData", {})
            ld = body.get("linkData", {})
            print(f"    flowData keys: {list(fd.keys())[:15]}")
            print(f"    flowData.busiId: {fd.get('busiId')}")
            print(f"    flowData.currCompUrl: {fd.get('currCompUrl')}")
            print(f"    flowData.status: {fd.get('status')}")
            print(f"    linkData: {json.dumps(ld, ensure_ascii=False)[:200]}")
            print(f"    signInfo: {body.get('signInfo')}")
            print(f"    itemId: {body.get('itemId')}")
        else:
            print(f"    body (raw): {str(body)[:300]}")
