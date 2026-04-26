import json
import sys

sys.path.insert(0, 'system')

from icpsp_api_client import ICPSPClient

ckpt = json.load(open('dashboard/data/checkpoints/checkpoint_phase2_establish__case_美的为_12c4329a75.json', encoding='utf-8'))
ctx = ckpt['context_state']
snap = ctx['phase2_driver_snapshot']
busi_id = snap.get('establish_busiId') or ctx.get('establish_busi_id')
name_id = ctx.get('name_id') or snap.get('phase2_driver_name_id')
client = ICPSPClient()
body = {
    'flowData': {
        'busiId': busi_id,
        'entType': '4540',
        'busiType': '02',
        'ywlbSign': '4',
        'busiMode': None,
        'nameId': name_id,
        'marPrId': None,
        'secondId': None,
        'vipChannel': None,
    },
    'linkData': {'continueFlag': 'continueFlag', 'token': ''},
}
resp = client.post_json('/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo', body, extra_headers={'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'})
print(json.dumps(resp, ensure_ascii=False, indent=2))
