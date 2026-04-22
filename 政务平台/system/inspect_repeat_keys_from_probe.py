import json
from pathlib import Path

p = Path('dashboard/data/records/run_phase1_from_case_latest.json')
raw = json.loads(p.read_text(encoding='utf-8'))
resp = (((raw.get('protocol_probe') or {}).get('nameCheckRepeat') or {}).get('raw') or {})
busi = ((((resp.get('data') or {}).get('busiData')) or {})) if isinstance(((resp.get('data') or {}).get('busiData')), dict) else {}
print('busi keys=', sorted(busi.keys()))
for k in ['afterNameCheckSign','freeBusinessAreaSign','interruptFlag','nameLikeState','needAudit','afterNeedAudit','bannedInfos','tipKeyWords','langStateCode','markInt','pinYinInt','fullNameInt','apprCodeStr','apprCode','tradeMark','modResult','checkState']:
    print(k, '=>', busi.get(k))
