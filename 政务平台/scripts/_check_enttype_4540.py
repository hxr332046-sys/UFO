"""检查 entType 字典是否包含 4540（个人独资）。"""
import sys
import json

sys.path.insert(0, 'system')
from governance import OptionDict

od = OptionDict.load()
f = od.get_field("entType")
codes = sorted([o.code for o in f.options])
print(f"entType 字典共 {len(codes)} 项")
print(f"全部 codes: {codes}")
print()
hit = f.find_by_code("4540")
print(f"4540 是否存在: {bool(hit)}")

print()
print("看 data/ent_type_codes.json 里有没有 4540 或个人独资...")
d = json.load(open("data/ent_type_codes.json", "r", encoding="utf-8"))
found = []
def walk(node):
    if isinstance(node, dict):
        c = node.get("code")
        n = node.get("name")
        if (c and "454" in str(c)) or (n and ("个人独资" in n or "独资" in n)):
            found.append((c, n))
        for ch in node.get("children", []) or []:
            walk(ch)
for cat in d.get("categories", []):
    walk(cat)

print(f"找到 {len(found)}:")
for c, n in found:
    print(f"  {c}={n}")
