"""扫前端 SPA chunk JS 抽取硬编码枚举。

策略：
1. 用正则找紧凑对象字面量 {code/value/key/id: ".."  (+) name/label/text/title: ".."}
2. 把连续的对象字面量（间隔 < 5 字符）聚合为同一枚举组
3. 只保留含 ≥ 2 个中文字符 name 的组（过滤掉非业务数据）
4. 用规模启发：组内项数 ≥ 2 才登记
5. 命名：从前面找 const X = [...] 或 export const X 或 类似上下文猜字段名
"""
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'system')
from governance import OptionDict


# ── 正则 ────────────────────────────────────────
# 模式 1: {value/code/key/id: "X", name/label/text: "Y"}
PAT_CODE_FIRST = re.compile(
    r'''\{\s*
        (?P<k1>code|value|key|id|dictCode|dataCode)
        \s*:\s*['"`](?P<code>[^'"`\s]{1,40})['"`]
        \s*,\s*
        (?P<k2>name|label|text|title|dictName|cnName|chineseName)
        \s*:\s*['"`](?P<name>[^'"`]{1,80})['"`]
    ''', re.VERBOSE
)
# 模式 2: 反序 {name:"Y", code:"X"}
PAT_NAME_FIRST = re.compile(
    r'''\{\s*
        (?P<k1>name|label|text|title|dictName|cnName|chineseName)
        \s*:\s*['"`](?P<name>[^'"`]{1,80})['"`]
        \s*,\s*
        (?P<k2>code|value|key|id|dictCode|dataCode)
        \s*:\s*['"`](?P<code>[^'"`\s]{1,40})['"`]
    ''', re.VERBOSE
)

# 含至少一个中文字符的 name 才算业务数据
HAS_CN = re.compile(r'[\u4e00-\u9fff]')

# 名字推断：变量名上下文
VAR_NAME_CONTEXT = re.compile(
    r'''(?:const|let|var|return|=)\s*
        (?P<var>[a-zA-Z_][a-zA-Z0-9_]*?(List|Options|Arr|Enum|Dict))\s*[:=]
    ''', re.VERBOSE
)


def scan_file(path: Path):
    """扫描单个 JS 文件，返回 [{var_name?, items: [{code,name}], position}, ...]"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    matches = []
    for m in PAT_CODE_FIRST.finditer(text):
        if HAS_CN.search(m.group("name")):
            matches.append((m.start(), m.group("code"), m.group("name")))
    for m in PAT_NAME_FIRST.finditer(text):
        if HAS_CN.search(m.group("name")):
            matches.append((m.start(), m.group("code"), m.group("name")))

    if not matches:
        return []

    matches.sort()

    # 按相邻位置（< 50 chars 间隔）聚合为组
    groups = []
    cur = []
    for pos, code, name in matches:
        if cur and pos - cur[-1][0] > 200:  # 距离过远 → 切组
            if len(cur) >= 2:
                groups.append(cur)
            cur = []
        cur.append((pos, code, name))
    if len(cur) >= 2:
        groups.append(cur)

    # 每组尝试推断变量名
    out = []
    for grp in groups:
        first_pos = grp[0][0]
        # 往前找 200 字符内的变量赋值
        before = text[max(0, first_pos - 300):first_pos]
        var_name = None
        var_matches = list(VAR_NAME_CONTEXT.finditer(before))
        if var_matches:
            var_name = var_matches[-1].group("var")
        # 去重 items
        seen = set()
        items = []
        for _, c, n in grp:
            if (c, n) in seen:
                continue
            seen.add((c, n))
            items.append({"code": c, "name": n})
        out.append({
            "var_name": var_name,
            "items": items,
            "position": first_pos,
            "size": len(items),
        })
    return out


def main():
    js_dir = Path("dashboard/data/records/core_assets")
    js_files = sorted(js_dir.glob("*.js"))
    print(f"扫描 {len(js_files)} 个 chunk JS...\n")

    all_findings = defaultdict(list)  # var_name (or unnamed_X) → groups

    for f in js_files:
        groups = scan_file(f)
        if not groups:
            continue
        print(f"{f.name}: {len(groups)} 组枚举")
        for g in groups:
            key = g["var_name"] or f"unnamed@{f.name}:{g['position']}"
            all_findings[key].append({
                "file": f.name,
                "items": g["items"],
                "size": g["size"],
            })
            preview = ", ".join([f"{i['code']}={i['name'][:8]}" for i in g["items"][:3]])
            print(f"    [{key:35s}] ×{g['size']:3d}  {preview}")

    print(f"\n=== 汇总：{len(all_findings)} 个候选枚举字段 ===\n")

    # 持久化：所有命名的枚举（var_name != None）写入字典
    od = OptionDict.load()
    persisted = 0
    for var_name, groups in all_findings.items():
        if var_name.startswith("unnamed@"):
            continue
        # 取最大组（项数最多的那个）
        best = max(groups, key=lambda g: g["size"])
        added = od.upsert_options(
            field_name=var_name,
            options=best["items"],
            label=f"前端硬编码 ({best['file']})",
            source=f"chunk_js:{best['file']}",
        )
        if added > 0:
            persisted += 1
            print(f"  + {var_name}: 写入 {added} options（来源 {best['file']}）")

    od.save()
    print(f"\n持久化 {persisted} 个字段到 data/options_dict.json")
    print(f"未命名（unnamed@）的 {sum(1 for k in all_findings if k.startswith('unnamed@'))} 组未写入（无字段名）")


if __name__ == "__main__":
    main()
