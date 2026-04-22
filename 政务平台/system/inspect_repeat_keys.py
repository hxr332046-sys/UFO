import json
from pathlib import Path

p = Path('dashboard/data/records/phase1_steps_5_7_dump.json')
raw = json.loads(p.read_text(encoding='utf-8'))
resp = json.loads(raw['6']['resp_body'])
busi = ((resp.get('data') or {}).get('busiData') or {}) if isinstance((resp.get('data') or {}).get('busiData'), dict) else {}
print('busi keys=', sorted(busi.keys()))
for k in ['afterNameCheckSign','freeBusinessAreaSign','interruptFlag','nameLikeState','needAudit','afterNeedAudit','bannedInfos','tipKeyWords','langStateCode','markInt','pinYinInt','fullNameInt','apprCodeStr','apprCode','tradeMark','modResult']:
    print(k, '=>', busi.get(k))
