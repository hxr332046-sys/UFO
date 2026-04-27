"""深度检查所有成功拉取的组件，找出 Scout 启发式漏掉的字典/枚举模式。"""
import json
from pathlib import Path

src = Path("packet_lab/out/component_loads_full")
if not src.exists():
    src = Path("packet_lab/out/component_loads")

print(f"扫描目录: {src}\n")
files = sorted(src.glob("*_load.json"))

# 我们关注的"非 List 后缀" 但可能是字典的模式：
# 1. dict 的 key 形如 角色码（FR05/CWFZR/LLY/...）→ value 是子结构 → 这是分组枚举
# 2. value 是 [{...code/value..., ...name/label...}] 但 key 不是 List 后缀
# 3. 数字键的 dict（如 {"01":"中共党员",...}）

def is_role_like_key(k: str) -> bool:
    """大写字母+数字组合的 key（FR05/CWFZR/LLY/WTDLR）。"""
    return (k.isupper() and 2 <= len(k) <= 8 and any(c.isdigit() or c.isalpha() for c in k))

def has_code_name_pair(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    keys = set(item.keys())
    has_code = bool(keys & {"code", "value", "key", "id", "dictCode"})
    has_name = bool(keys & {"name", "label", "text", "title", "dictName"})
    return has_code and has_name

def deep_walk(node, path="", out=None):
    if out is None: out = []
    if isinstance(node, dict):
        # ① 检查是否所有 key 都形如角色码
        keys = list(node.keys())
        if len(keys) >= 2 and all(is_role_like_key(k) for k in keys):
            out.append({
                "path": path, "type": "role_dict",
                "keys": keys,
                "sample": {k: type(node[k]).__name__ for k in keys[:5]},
            })
        # ② 数字键 dict（{"01":"中共党员", "13":"群众"}）
        if len(keys) >= 2 and all(k.isdigit() and 1 <= len(k) <= 4 for k in keys if isinstance(k, str)):
            if all(isinstance(node[k], str) and node[k] for k in keys):
                out.append({
                    "path": path, "type": "code_value_dict",
                    "items": list(node.items())[:5],
                    "size": len(keys),
                })
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            # ③ 数组中是 code/name 双键，但 key 不在 List 后缀里
            if isinstance(v, list) and v and isinstance(v[0], dict) and has_code_name_pair(v[0]):
                if not any(k.endswith(s) for s in ["List","Options","Arr","Enum","Items"]):
                    out.append({
                        "path": p, "type": "hidden_enum_array",
                        "size": len(v),
                        "sample": v[0],
                    })
            deep_walk(v, p, out)
    elif isinstance(node, list) and node and isinstance(node[0], dict):
        deep_walk(node[0], path + "[0]", out)
    return out

for f in files:
    d = json.load(open(f, "r", encoding="utf-8"))
    code = d.get("code")
    if code != "00000":
        continue
    bd = (d.get("data") or {}).get("busiData") or {}
    if not bd:
        continue
    findings = deep_walk(bd, "")
    if not findings:
        continue
    print(f"\n{'='*60}\n{f.stem} ({len(findings)} 个隐藏发现)")
    for it in findings[:8]:
        print(f"  [{it['type']}] {it['path']}")
        if it["type"] == "role_dict":
            print(f"    keys: {it['keys']}")
        elif it["type"] == "code_value_dict":
            print(f"    items: {it['items']}, size={it['size']}")
        elif it["type"] == "hidden_enum_array":
            print(f"    size={it['size']} sample={it['sample']}")
