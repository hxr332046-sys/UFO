"""检查 phase1_service ent_types_type1/2.json 是否含 4540。"""
import json
from pathlib import Path

for fname in ["ent_types_type1.json", "ent_types_type2.json"]:
    fp = Path(f"phase1_service/data/dictionaries/{fname}")
    d = json.load(open(fp, "r", encoding="utf-8"))
    print(f"\n=== {fname} ===")
    # 处理嵌套
    data = d.get("data", {})
    nested = data.get("data", {}) if isinstance(data, dict) and "code" in data else data
    busi = nested.get("busiData") if isinstance(nested, dict) else None

    if not isinstance(busi, list):
        print(f"  busiData type: {type(busi).__name__}")
        if isinstance(busi, dict):
            print(f"  keys[:5]: {list(busi.keys())[:5]}")
        continue

    print(f"  list[{len(busi)}]")
    if busi:
        print(f"  sample[0]: {json.dumps(busi[0], ensure_ascii=False)[:200]}")

    hit = [it for it in busi if str(it.get("code", "")) == "4540"]
    print(f"  4540 hit: {hit[:1] if hit else 'NONE'}")

    ind = [it for it in busi if "独资" in str(it.get("name", "")) or "独资" in str(it.get("entTypeName", ""))]
    print(f"  含'独资' 项: {len(ind)}")
    for it in ind[:8]:
        print(f"    {it.get('code')}={it.get('name') or it.get('entTypeName')}")
