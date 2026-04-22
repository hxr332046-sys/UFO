"""diff step5(完整) 与 step7(被mitm截断的50K body)顶层字段，定位 nameCheckDTO 回灌差异。"""
import json
import re
from pathlib import Path

p = Path('dashboard/data/records/phase1_steps_5_7_dump.json')
raw = json.loads(p.read_text(encoding='utf-8'))
step5 = json.loads(raw['5']['req_body'])

b7 = raw['7']['req_body']
# step7 被 mitm 截断；提取所有顶层键（"key": 出现的位置）
top_keys7 = set()
for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', b7):
    # 只收到首个 '{' 层级的键：按左括号深度过滤
    start = m.start()
    depth = 0
    for ch in b7[:start]:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
    if depth == 1:
        top_keys7.add(m.group(1))

keys5 = set(step5.keys())
print('step5 top keys (', len(keys5), '):', sorted(keys5))
print('step7 top keys (', len(top_keys7), '):', sorted(top_keys7))
print('only in step7:', sorted(top_keys7 - keys5))
print('only in step5:', sorted(keys5 - top_keys7))

# 能不能在 step7 里看到 nameCheckDTO?
print('\nstep7 has nameCheckDTO?', 'nameCheckDTO' in top_keys7)
print('step7 has afterNameCheckSign?', 'afterNameCheckSign' in top_keys7)
print('step7 has signInfo?', 'signInfo' in top_keys7)

# step5 的 signInfo/checkState
print('\nstep5 signInfo=', step5.get('signInfo'))
print('step5 checkState=', step5.get('checkState'))
print('step5 itemId=', step5.get('itemId'))
print('step5 flowData=', json.dumps(step5.get('flowData'), ensure_ascii=False))
print('step5 linkData=', json.dumps(step5.get('linkData'), ensure_ascii=False))
