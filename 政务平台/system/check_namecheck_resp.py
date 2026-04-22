import json

with open('dashboard/data/records/mitm_ufo_flows.jsonl','r',encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        url = d.get('url','')
        if 'NameCheckInfo/operationBusinessDataInfo' in url:
            resp = d.get('resp_body','')
            try:
                r = json.loads(resp)
                code = r.get('code')
                fd = r.get('data',{}).get('busiData',{}).get('flowData',{})
                busi_id = fd.get('busiId') if fd else None
                print('code=', code, 'busiId=', busi_id)
                bd = r.get('data',{}).get('busiData',{})
                if isinstance(bd, dict):
                    print('busiData keys:', list(bd.keys()))
                    orv = bd.get('operationResultVo')
                    if orv:
                        print('operationResultVo:', orv)
            except Exception as e:
                print('error:', e)
            break
