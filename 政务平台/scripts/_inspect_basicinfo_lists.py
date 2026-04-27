"""Inspect lists/options inside each component load response."""
import json
from pathlib import Path

src = Path("packet_lab/out/component_loads")
for f in sorted(src.glob("*_load.json")):
    print(f"\n{'='*60}\n{f.stem}")
    d = json.load(open(f, "r", encoding="utf-8"))
    bd = (d.get("data") or {}).get("busiData") or {}
    print(f"  total fields: {len(bd)}")
    # 找所有 list 字段
    list_fields = []
    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                if isinstance(v, list):
                    list_fields.append((p, len(v),
                        type(v[0]).__name__ if v else "empty",
                        list(v[0].keys())[:6] if v and isinstance(v[0], dict) else ""))
                if isinstance(v, (dict, list)):
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        walk(v[0], p + "[0]")
                    elif isinstance(v, dict):
                        walk(v, p)
    walk(bd)
    for p, sz, t, keys in list_fields[:30]:
        print(f"  {p:55s} list[{t}] ×{sz}  keys={keys}")
    if len(list_fields) > 30:
        print(f"  ... ({len(list_fields) - 30} more)")
