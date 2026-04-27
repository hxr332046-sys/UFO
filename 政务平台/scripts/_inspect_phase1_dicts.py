"""检查 phase1_service 下所有字典文件的真实结构。"""
import json
from pathlib import Path

base = Path("phase1_service/data/dictionaries")
all_files = list(base.rglob("*.json"))
print(f"找到 {len(all_files)} 个字典文件\n")

for fp in all_files:
    try:
        d = json.load(open(fp, "r", encoding="utf-8"))
    except Exception as e:
        print(f"❌ {fp}: {e}")
        continue
    rel = fp.relative_to("phase1_service/data/dictionaries")
    print(f"\n=== {rel} ===")
    meta = d.get("meta", {}) if isinstance(d, dict) else {}
    if meta:
        print(f"  meta: {json.dumps(meta, ensure_ascii=False)[:200]}")
    data = d.get("data", {}) if isinstance(d, dict) else d
    if isinstance(data, dict):
        print(f"  data keys: {list(data.keys())}")
        for k, v in data.items():
            tn = type(v).__name__
            sz = len(v) if isinstance(v, (list, dict, str)) else ""
            print(f"    {k}: {tn} sz={sz}")
            if isinstance(v, list) and v:
                print(f"      sample[0]: {json.dumps(v[0], ensure_ascii=False)[:200]}")
            elif isinstance(v, dict) and v:
                first_k = list(v.keys())[0]
                first_v = v[first_k]
                print(f"      first item key={first_k}, value={json.dumps(first_v, ensure_ascii=False)[:150]}")
