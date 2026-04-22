import json

with open('dashboard/data/records/mitm_ufo_flows.jsonl','r',encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        url = d.get('url','')
        resp = d.get('resp_body','')
        if not resp:
            continue
        try:
            r = json.loads(resp)
            busi_id = None
            data = r.get('data',{})
            if isinstance(data, dict):
                busi_data = data.get('busiData',{})
                if isinstance(busi_data, dict):
                    fd = busi_data.get('flowData',{})
                    if isinstance(fd, dict):
                        busi_id = fd.get('busiId')
            if busi_id and busi_id != 'null' and busi_id != '':
                path = url.split('?')[0].split('/')[-1]
                print(f'{path}: busiId={busi_id}')
        except:
            pass
