import json

with open('dashboard/data/records/mitm_ufo_flows.jsonl','r',encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        url = d.get('url','')
        resp = d.get('resp_body','')
        if not resp or 'operationBusinessDataInfo' not in url:
            continue
        try:
            r = json.loads(resp)
            data = r.get('data',{})
            if not isinstance(data, dict):
                continue
            busi_data = data.get('busiData',{})
            if not isinstance(busi_data, dict):
                continue
            fd = busi_data.get('flowData',{})
            if not isinstance(fd, dict):
                continue
            busi_id = fd.get('busiId')
            if busi_id and busi_id != 'null' and busi_id != '':
                # 提取组件名
                parts = url.split('/')
                comp = 'unknown'
                for i,p in enumerate(parts):
                    if p == 'component':
                        comp = parts[i+1] if i+1 < len(parts) else 'unknown'
                        break
                print(f'{comp}: busiId={busi_id}')
                print(f'  URL: {url.split("?")[0].split("/")[-2:]},{""}')
                # 也打印请求中的 busiId
                req = d.get('req_body','')
                if req:
                    try:
                        rb = json.loads(req)
                        req_busi = rb.get('flowData',{}).get('busiId')
                        print(f'  req busiId: {req_busi}')
                    except:
                        pass
        except:
            pass
