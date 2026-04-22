import json
from pathlib import Path
from collections import OrderedDict

MITM_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl"

with open(MITM_LOG, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"MITM total lines: {len(lines)}")
print("=" * 80)

# 提取所有 POST/GET 请求，按 URL 去重
seen_urls = set()
requests_list = []

for line in lines:
    d = json.loads(line)
    url = d.get('url', '')
    method = d.get('method', '')
    status = d.get('status_code', 0)
    
    # 只关注 icpsp-api 的请求
    if '/icpsp-api/' not in url:
        continue
    
    # 简化 URL（去掉时间戳参数）用于去重
    base_url = url.split('?')[0]
    key = f"{method}:{base_url}"
    
    if key not in seen_urls and status == 200:
        seen_urls.add(key)
        requests_list.append({
            'method': method,
            'url': url,
            'status': status,
            'has_req': bool(d.get('req_body')),
            'has_resp': bool(d.get('resp_body')),
            'req_preview': (d.get('req_body', '') or '')[:200],
            'resp_preview': (d.get('resp_body', '') or '')[:200],
        })

print(f"\n去重后关键请求 ({len(requests_list)} 个):\n")

for i, req in enumerate(requests_list, 1):
    # 提取接口名
    path = req['url'].split('/icpsp-api/')[1].split('?')[0] if '/icpsp-api/' in req['url'] else req['url']
    print(f"[{i:2d}] {req['method']:4s} {path[:70]}")
    if req['has_req'] and len(req['req_preview']) > 10:
        try:
            body = json.loads(req['req_preview'])
            # 打印关键字段
            important = {}
            for k in ['entType', 'busiType', 'busiId', 'name', 'distCode', 'areaCode', 'organize', 'opeType', 'checkState', 'flowData']:
                if k in body:
                    important[k] = body[k]
            if important:
                print(f"     REQ: {json.dumps(important, ensure_ascii=False)}")
        except:
            print(f"     REQ: {req['req_preview'][:100]}")
    if req['has_resp']:
        try:
            resp = json.loads(req['resp_preview'])
            code = resp.get('code', 'N/A')
            result_type = resp.get('data', {}).get('resultType', 'N/A') if isinstance(resp.get('data'), dict) else 'N/A'
            busi_data = resp.get('data', {}).get('busiData', '')
            busi_preview = str(busi_data)[:80] if busi_data else ''
            print(f"     RESP: code={code}, resultType={result_type}, busiData={busi_preview}")
        except:
            print(f"     RESP: {req['resp_preview'][:100]}")
    print()

# 特别关注 operationBusinessDataInfo 的所有变体
print("\n" + "=" * 80)
print("【重点】所有 operationBusinessDataInfo 请求:\n")
for line in lines:
    d = json.loads(line)
    url = d.get('url', '')
    if 'operationBusinessDataInfo' in url:
        req_body = d.get('req_body', '') or '{}'
        try:
            body = json.loads(req_body)
            # 找 opeType 和关键字段
            link = body.get('linkData', {})
            ope_type = link.get('opeType', 'N/A') if isinstance(link, dict) else 'N/A'
            flow = body.get('flowData', {})
            busi_id = flow.get('busiId', 'N/A') if isinstance(flow, dict) else 'N/A'
            comp_url = link.get('compUrl', 'N/A') if isinstance(link, dict) else 'N/A'
            
            print(f"URL: {url[:100]}")
            print(f"  opeType={ope_type}, busiId={busi_id}, compUrl={comp_url}")
            print(f"  has_name={bool(body.get('name', ''))}, has_certificateNo={bool(body.get('certificateNo', ''))}")
            print()
        except:
            print(f"URL: {url[:100]} (parse error)")
            print()

# 保存完整链路
out = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "phase1_all_requests.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(requests_list, f, ensure_ascii=False, indent=2)
print(f"Saved to: {out}")
