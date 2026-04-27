"""检查 code_lists 内具体内容。"""
import json
from pathlib import Path

p = Path("phase1_service/data/dictionaries/code_lists")
for fp in sorted(p.glob("*.json")):
    d = json.load(open(fp, "r", encoding="utf-8"))
    print(f"\n{'='*60}\n{fp.name}")
    data = d.get("data", {})
    busi = data.get("busiData")
    if isinstance(busi, list):
        print(f"  busiData: list[{len(busi)}]")
        for it in busi[:5]:
            print(f"    {json.dumps(it, ensure_ascii=False)[:200]}")
    elif isinstance(busi, dict):
        print(f"  busiData keys ({len(busi)}): {list(busi.keys())[:10]}")
        for k, v in list(busi.items())[:5]:
            if isinstance(v, list):
                print(f"    {k}: list[{len(v)}] sample={json.dumps(v[0] if v else None, ensure_ascii=False)[:200]}")
            else:
                print(f"    {k}: {json.dumps(v, ensure_ascii=False)[:200]}")
    else:
        print(f"  busiData: {type(busi).__name__}={str(busi)[:100]}")
