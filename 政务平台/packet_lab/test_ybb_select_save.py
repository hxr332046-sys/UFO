import json
import sys
from pathlib import Path

sys.path.insert(0, 'system')

from icpsp_api_client import ICPSPClient
import phase2_bodies as pb

HDRS = {'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'}
CKPT = Path('dashboard/data/checkpoints/checkpoint_phase2_establish__case_美的为_12c4329a75.json')
OUT = Path('packet_lab/out/ybb_probe_results.json')
SUCCESS_OUT = Path('packet_lab/out/ybb_save_body_probe_success.json')


def main():
    ckpt = json.loads(CKPT.read_text(encoding='utf-8'))
    ctx = ckpt['context_state']
    snap = ctx['phase2_driver_snapshot']
    busi_id = snap.get('establish_busiId') or ctx.get('establish_busi_id')
    name_id = ctx.get('name_id') or snap.get('phase2_driver_name_id')
    ent_type = '4540'

    client = ICPSPClient()
    prev_fd = snap.get('last_save_flowData') or {}
    prev_ld = snap.get('last_save_linkData') or {}

    load_fd = dict(prev_fd) if prev_fd else pb._base_flow_data(ent_type, name_id, 'YbbSelect', busi_id=busi_id)
    load_fd['currCompUrl'] = 'YbbSelect'

    if prev_ld and prev_ld.get('busiCompComb'):
        load_ld = dict(prev_ld)
        load_ld['compUrl'] = 'YbbSelect'
        load_ld['opeType'] = 'load'
        load_ld['compUrlPaths'] = ['YbbSelect']
    else:
        load_ld = pb._base_link_data('YbbSelect', ope_type='load')

    load_body = {'flowData': load_fd, 'linkData': load_ld, 'itemId': ''}
    load_resp = client.post_json('/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo', load_body, extra_headers=HDRS)
    bd = (load_resp.get('data') or {}).get('busiData') or {}
    sign = str(bd.get('signInfo') or snap.get('YbbSelect_signInfo') or snap.get('last_sign_info'))

    candidates = [
        ('minimal_isSelectYbb_only', {
            'isSelectYbb': str(bd.get('isSelectYbb') or '0'),
        }),
        ('with_optional_fields', {
            'isOptional': bd.get('isOptional'),
            'preAuditSign': bd.get('preAuditSign'),
            'isSelectYbb': str(bd.get('isSelectYbb') or '0'),
        }),
        ('stringified_full_visible_fields', {
            'isOptional': str(bd.get('isOptional') or '1'),
            'preAuditSign': bd.get('preAuditSign'),
            'isSelectYbb': str(bd.get('isSelectYbb') or '0'),
        }),
    ]

    results = {
        'busi_id': busi_id,
        'name_id': name_id,
        'load_code': load_resp.get('code'),
        'load_msg': load_resp.get('msg'),
        'signInfo': sign,
        'candidates': [],
    }

    for name, payload in candidates:
        body = {
            **payload,
            'flowData': pb._base_flow_data(ent_type, name_id, 'YbbSelect', busi_id=busi_id),
            'linkData': pb._base_link_data('YbbSelect'),
            'signInfo': sign,
            'itemId': bd.get('itemId') or '',
        }
        resp = client.post_json('/icpsp-api/v4/pc/register/establish/component/YbbSelect/operationBusinessDataInfo', body, extra_headers=HDRS)
        rt = (resp.get('data') or {}).get('resultType')
        msg = (resp.get('data') or {}).get('msg') or resp.get('msg') or ''
        row = {
            'candidate': name,
            'code': resp.get('code'),
            'resultType': rt,
            'msg': msg,
            'body': body,
        }
        results['candidates'].append(row)
        print(f"[{name}] code={resp.get('code')} rt={rt} msg={msg}")
        if resp.get('code') == '00000' and str(rt) in ('0', ''):
            SUCCESS_OUT.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'OK -> {SUCCESS_OUT}')
            break

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'RESULTS -> {OUT}')


if __name__ == '__main__':
    main()
