import json
import sys

sys.path.insert(0, 'system')

from icpsp_api_client import ICPSPClient
import phase2_bodies as pb

ckpt = json.load(open('dashboard/data/checkpoints/checkpoint_phase2_establish__case_美的为_12c4329a75.json', encoding='utf-8'))
ctx = ckpt['context_state']
snap = ctx['phase2_driver_snapshot']
busi_id = snap.get('establish_busiId') or ctx.get('establish_busi_id')
name_id = ctx.get('name_id') or snap.get('phase2_driver_name_id')
ent_type = '4540'
client = ICPSPClient()
body = {
    'flowData': pb._base_flow_data(ent_type, name_id, 'PreSubmitSuccess', busi_id=busi_id),
    'linkData': pb._base_link_data('PreSubmitSuccess', ope_type='load'),
    'itemId': '',
}
resp = client.post_json('/icpsp-api/v4/pc/register/establish/component/PreSubmitSuccess/loadBusinessDataInfo', body, extra_headers={'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'})
print(json.dumps({
    'code': resp.get('code'),
    'msg': resp.get('msg'),
    'rt': (resp.get('data') or {}).get('resultType'),
    'keys': list(((resp.get('data') or {}).get('busiData') or {}).keys())[:40],
    'busiData': (resp.get('data') or {}).get('busiData'),
}, ensure_ascii=False, indent=2))
