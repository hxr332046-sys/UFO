import json
d = json.load(open(r'dashboard\data\records\smart_register__case_兴裕为.json', 'r', encoding='utf-8'))
print(json.dumps(list(d.keys()), indent=2))
# Check all keys for step data
for k in d.keys():
    v = d[k]
    if isinstance(v, dict) and 'steps' in v:
        print(f'\n{k}: has steps ({len(v["steps"])} items)')
    elif isinstance(v, list) and len(v) > 0:
        print(f'\n{k}: list ({len(v)} items)')
