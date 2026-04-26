import json
import sys
from pathlib import Path

sys.path.insert(0, 'system')

from icpsp_api_client import ICPSPClient
import phase2_bodies as pb

HDRS = {'Referer': 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html'}
CKPT = Path('dashboard/data/checkpoints/checkpoint_phase2_establish__case_美的为_12c4329a75.json')
OUT = Path('packet_lab/out/taxinvoice_probe_results.json')
SUCCESS_OUT = Path('packet_lab/out/taxinvoice_save_body_probe_success.json')


def strip_gx_vo(vo: dict) -> dict:
    if not isinstance(vo, dict):
        return {'isSetUp': 'N'}
    return {
        'isSetUp': vo.get('isSetUp') or 'N',
        'taxpayerType': vo.get('taxpayerType'),
        'gxSdnsr': vo.get('gxSdnsr'),
        'gxCshy': vo.get('gxCshy'),
        'invoiceType': vo.get('invoiceType'),
        'hasAccounting': vo.get('hasAccounting'),
        'businessTypeWH': vo.get('businessTypeWH'),
        'effectTimeWH': vo.get('effectTimeWH'),
        'gxhsdz': vo.get('gxhsdz'),
        'gxFplyrName': vo.get('gxFplyrName'),
        'gxFplyrCerType': vo.get('gxFplyrCerType'),
        'gxFplyrCerNo': vo.get('gxFplyrCerNo'),
        'encryptedGxFplyrCerNo': vo.get('encryptedGxFplyrCerNo'),
        'gxFplyrMobile': vo.get('gxFplyrMobile'),
        'encryptedGxFplyrMobile': vo.get('encryptedGxFplyrMobile'),
        'gxFplyrPhone': vo.get('gxFplyrPhone'),
        'encryptedGxFplyrPhone': vo.get('encryptedGxFplyrPhone'),
        'gxFplyrEmail': vo.get('gxFplyrEmail'),
        'zzsTicketInfoList': vo.get('zzsTicketInfoList'),
        'deTicketInfoList': vo.get('deTicketInfoList'),
        'gxDefpmyzglqje': vo.get('gxDefpmyzglqje'),
        'lqfs': vo.get('lqfs'),
        'gxReceiptDz': vo.get('gxReceiptDz'),
        'gxReceiptRlx': vo.get('gxReceiptRlx'),
        'gxReceiptBz': vo.get('gxReceiptBz'),
        'gxIsReadAgree': vo.get('gxIsReadAgree'),
        'gxCshyList': vo.get('gxCshyList'),
    }


def main():
    ckpt = json.loads(CKPT.read_text(encoding='utf-8'))
    ctx = ckpt['context_state']
    snap = ctx['phase2_driver_snapshot']
    busi_id = snap.get('establish_busiId') or ctx.get('establish_busi_id')
    name_id = ctx.get('name_id') or snap.get('phase2_driver_name_id') or '2047939021453729793'
    ent_type = '4540'

    client = ICPSPClient()

    prev_fd = snap.get('last_save_flowData') or {}
    prev_ld = snap.get('last_save_linkData') or {}

    load_fd = dict(prev_fd) if prev_fd else pb._base_flow_data(ent_type, name_id, 'TaxInvoice', busi_id=busi_id)
    load_fd['currCompUrl'] = 'TaxInvoice'

    if prev_ld and prev_ld.get('busiCompComb'):
        load_ld = dict(prev_ld)
        load_ld['compUrl'] = 'TaxInvoice'
        load_ld['opeType'] = 'load'
        load_ld['compUrlPaths'] = ['TaxInvoice']
    else:
        load_ld = pb._base_link_data('TaxInvoice', ope_type='load')

    load_body = {'flowData': load_fd, 'linkData': load_ld, 'itemId': ''}
    load_resp = client.post_json('/icpsp-api/v4/pc/register/establish/component/TaxInvoice/loadBusinessDataInfo', load_body, extra_headers=HDRS)
    bd = (load_resp.get('data') or {}).get('busiData') or {}
    sign = str(bd.get('signInfo') or snap.get('TaxInvoice_signInfo') or snap.get('last_sign_info'))

    gx_vo = bd.get('taxInvoiceGxVo') or {}

    candidates = [
        ('minimal_is_setup_only', {
            'pageType': bd.get('pageType') or 'GX',
            'agencyCode': bd.get('agencyCode') or '08',
            'isSsb': bd.get('isSsb') or 'N',
            'taxInvoiceGxVo': {'isSetUp': (gx_vo.get('isSetUp') or 'N')},
        }),
        ('minimal_with_autmode', {
            'pageType': bd.get('pageType') or 'GX',
            'agencyCode': bd.get('agencyCode') or '08',
            'isSsb': bd.get('isSsb') or 'N',
            'autMode': bd.get('autMode'),
            'taxInvoiceGxVo': {'isSetUp': (gx_vo.get('isSetUp') or 'N')},
        }),
        ('pruned_full_tax', {
            'pageType': bd.get('pageType') or 'GX',
            'agencyCode': bd.get('agencyCode') or '08',
            'isSsb': bd.get('isSsb') or 'N',
            'autMode': bd.get('autMode'),
            'taxInvoiceGzVo': bd.get('taxInvoiceGzVo'),
            'rzInfoGzVo': bd.get('rzInfoGzVo'),
            'taxInvoiceGzDto': bd.get('taxInvoiceGzDto'),
            'taxInvoiceHnVo': bd.get('taxInvoiceHnVo'),
            'taxInvoiceHljVo': bd.get('taxInvoiceHljVo'),
            'taxInvoiceHljScVo': bd.get('taxInvoiceHljScVo'),
            'taxInvoiceHenanVo': bd.get('taxInvoiceHenanVo'),
            'taxInvoiceAhVo': bd.get('taxInvoiceAhVo'),
            'taxInvoiceNxVo': bd.get('taxInvoiceNxVo'),
            'taxInvoiceXzVo': bd.get('taxInvoiceXzVo'),
            'taxInvoiceXjVo': bd.get('taxInvoiceXjVo'),
            'taxInvoiceQqheVo': bd.get('taxInvoiceQqheVo'),
            'taxInvoiceMdjVo': bd.get('taxInvoiceMdjVo'),
            'taxInvoiceHebgzqVo': bd.get('taxInvoiceHebgzqVo'),
            'taxInvoiceGsVo': bd.get('taxInvoiceGsVo'),
            'taxInvoiceWwxyVo': bd.get('taxInvoiceWwxyVo'),
            'taxInvoiceHljqyVo': bd.get('taxInvoiceHljqyVo'),
            'taxInvoiceXjqyVo': bd.get('taxInvoiceXjqyVo'),
            'taxInvoiceZjqyVo': bd.get('taxInvoiceZjqyVo'),
            'taxInvoiceHljbgVo': bd.get('taxInvoiceHljbgVo'),
            'taxInvoiceXzqyVo': bd.get('taxInvoiceXzqyVo'),
            'taxInvoiceGxVo': strip_gx_vo(gx_vo),
            'taxGxAuxiliaryVo': bd.get('taxGxAuxiliaryVo'),
            'taxInvoiceGzbgVo': bd.get('taxInvoiceGzbgVo'),
            'taxInvoiceHenanbgVo': bd.get('taxInvoiceHenanbgVo'),
            'taxInvoiceXzbgVo': bd.get('taxInvoiceXzbgVo'),
            'taxInvoiceLndlVo': bd.get('taxInvoiceLndlVo'),
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
            'flowData': pb._base_flow_data(ent_type, name_id, 'TaxInvoice', busi_id=busi_id),
            'linkData': pb._base_link_data('TaxInvoice'),
            'signInfo': sign,
            'itemId': bd.get('itemId') or '',
        }
        resp = client.post_json('/icpsp-api/v4/pc/register/establish/component/TaxInvoice/operationBusinessDataInfo', body, extra_headers=HDRS)
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
