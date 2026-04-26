import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
import phase2_bodies as pb

client = ICPSPClient()
busi_id = '2047910256739598337'
name_id = '2047910192228147201'
ent_type = '4540'
hdrs = {'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'}

ckpt = json.loads(open('dashboard/data/checkpoints/checkpoint_phase2_establish__case_美的为_12c4329a75.json', encoding='utf-8').read())
snap = ckpt['context_state']['phase2_driver_snapshot']
prev_ld = snap['last_save_linkData']
sign_info = snap.get('last_sign_info', '874074588')

# fieldList val 填写: 读实时preload的fieldList, 填入val
def make_fieldlist_dto(vals_map):
    """从最新preload取fieldList, 并填入指定字段的val."""
    srv_ld, si = do_preload()
    # 需要再做一次preload取busiData
    load_ld = dict(prev_ld)
    load_ld['compUrl'] = 'ComplementInfo'; load_ld['opeType'] = 'load'; load_ld['compUrlPaths'] = ['ComplementInfo']
    load_fd = pb._base_flow_data(ent_type, name_id, 'ComplementInfo', busi_id=busi_id)
    preload2 = client.post_json('/icpsp-api/v4/pc/register/establish/component/ComplementInfo/loadBusinessDataInfo',
        {'flowData': load_fd, 'linkData': load_ld, 'itemId': ''}, extra_headers=hdrs)
    bd = (preload2.get('data') or {}).get('busiData') or {}
    pdto = bd.get('partyBuildDto') or {}
    fl = [dict(f) for f in (pdto.get('fieldList') or [])]
    for f in fl:
        fld = f.get('field')
        if fld in vals_map:
            f['val'] = vals_map[fld]
    return {'partyBuildFlag': '6', 'fieldList': fl}, bd.get('signInfo', sign_info)

FIELD_VAL_TESTS = [
    ('fl_est0_numM0',  {'estParSign': '0', 'numParM': '0'}),
    ('fl_est2_numM0',  {'estParSign': '2', 'numParM': '0'}),
    ('fl_est0_numMi0', {'estParSign': '0', 'numParM': 0}),
    ('fl_est_no',      {'estParSign': '否', 'numParM': '0'}),
    ('fl_numM_only',   {'numParM': '0'}),
    ('fl_all_0',       {'estParSign': '0', 'numParM': '0', 'parOrgw': '', 'parIns': '',
                        'anOrgParSign': '0', 'resParMSign': '0', 'resParSecSign': '0'}),
]

def do_preload():
    load_ld = dict(prev_ld)
    load_ld['compUrl'] = 'ComplementInfo'
    load_ld['opeType'] = 'load'
    load_ld['compUrlPaths'] = ['ComplementInfo']
    load_fd = pb._base_flow_data(ent_type, name_id, 'ComplementInfo', busi_id=busi_id)
    load_body = {'flowData': load_fd, 'linkData': load_ld, 'itemId': ''}
    preload = client.post_json(
        '/icpsp-api/v4/pc/register/establish/component/ComplementInfo/loadBusinessDataInfo',
        load_body, extra_headers=hdrs)
    bd = (preload.get('data') or {}).get('busiData') or {}
    return bd.get('linkData') or {}, bd.get('signInfo') or sign_info

def do_save(party_dto, extra_top_level=None):
    srv_ld, si = do_preload()
    save_body = pb.build_empty_advance_save_body('ComplementInfo', ent_type=ent_type,
                                                  name_id=name_id, busi_id=busi_id)
    if party_dto is not None:
        save_body['partyBuildDto'] = party_dto
    if extra_top_level:
        save_body.update(extra_top_level)
    save_body['signInfo'] = str(si)
    if srv_ld:
        for k in ('busiCompComb', 'compCombArr'):
            if srv_ld.get(k) is not None:
                save_body['linkData'][k] = srv_ld[k]
    resp = client.post_json(
        '/icpsp-api/v4/pc/register/establish/component/ComplementInfo/operationBusinessDataInfo',
        save_body, extra_headers=hdrs)
    rt = (resp.get('data') or {}).get('resultType', '?')
    msg = str((resp.get('data') or {}).get('msg') or '')[:80]
    return resp.get('code'), rt, msg

# Run fieldList val tests
for name, vals_map in FIELD_VAL_TESTS:
    dto, si = make_fieldlist_dto(vals_map)
    srv_ld, _ = do_preload()
    save_body = pb.build_empty_advance_save_body('ComplementInfo', ent_type=ent_type,
                                                  name_id=name_id, busi_id=busi_id)
    save_body['partyBuildDto'] = dto
    save_body['signInfo'] = str(si)
    if srv_ld:
        for k in ('busiCompComb', 'compCombArr'):
            if srv_ld.get(k) is not None:
                save_body['linkData'][k] = srv_ld[k]
    resp = client.post_json(
        '/icpsp-api/v4/pc/register/establish/component/ComplementInfo/operationBusinessDataInfo',
        save_body, extra_headers=hdrs)
    rt = (resp.get('data') or {}).get('resultType', '?')
    msg = str((resp.get('data') or {}).get('msg') or '')[:80]
    print('[%s] code=%s rt=%s msg=%s' % (name, resp.get('code'), rt, msg))
