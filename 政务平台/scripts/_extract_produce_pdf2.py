import json
files = [
    '_archive/records/mitm_ufo_flows.jsonl',
    '_archive/records/mitm_ufo_flows_backup_20260421_231343.jsonl',
]
for f in files:
    print(f'\n=== {f} ===')
    count = 0
    for line in open(f, encoding='utf-8'):
        try:
            rec = json.loads(line)
        except:
            continue
        url = rec.get('url', '')
        if 'producePdf' not in url:
            continue
        count += 1
        body = rec.get('body') or rec.get('request_body') or ''
        resp = rec.get('response') or rec.get('resp') or ''
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
        resp_code = resp.get('code', '') if isinstance(resp, dict) else ''
        print(f'  #{count} resp_code={resp_code}')
        if isinstance(body, dict):
            fd = body.get('flowData', {})
            ld = body.get('linkData', {})
            bid = fd.get('busiId', '?')
            ccu = fd.get('currCompUrl', '?')
            st = fd.get('status', '?')
            si = body.get('signInfo', '?')
            iid = body.get('itemId', '?')
            print(f'    fd.busiId={bid} currCompUrl={ccu} status={st}')
            print(f'    ld: {json.dumps(ld, ensure_ascii=False)[:200]}')
            print(f'    signInfo={si} itemId={iid}')
        else:
            print(f'    body: {str(body)[:300]}')
