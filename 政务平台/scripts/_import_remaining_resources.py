"""把剩余的资源文件全部合并进 OptionDict：

1. regions/root.json - 行政区域树 → distCode 字段（展平）
2. schemas/basic_info_schema_v2.json - BasicInfo 字段 schema → _schema_BasicInfo
3. schemas/bdi_fields.json - bdi 字段
4. dashboard/data/ent_types.js - 企业类型 JS（需要解析）
5. sys_configs/*.json - 系统配置（保存为信息字段）
"""
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, 'system')
from governance import OptionDict


def import_regions(fp: Path, od: OptionDict):
    """regions/root.json - 行政区域树展平。"""
    d = json.load(open(fp, "r", encoding="utf-8"))
    busi = d.get("data", {}).get("data", {}).get("busiData", [])
    if not busi:
        return 0, 0

    options = []
    seen = set()
    def walk(node, depth=0):
        if not isinstance(node, dict):
            return
        code = node.get("id") or node.get("code")
        name = node.get("name") or ""
        full = node.get("allName") or name
        parent = node.get("parentId") or node.get("parent")
        if code and code not in seen:
            seen.add(code)
            options.append({
                "code": str(code),
                "name": full or name,
                "short_name": name,
                "parent": parent,
                "depth": depth,
            })
        for ch in node.get("children", []) or []:
            walk(ch, depth + 1)

    for root in busi:
        walk(root, 0)

    if not options:
        return 0, 0
    added = od.upsert_options(
        field_name="distCode",
        options=options,
        label="行政区域代码（树形展平）",
        source=f"phase1_service:regions/root.json",
    )
    return len(options), added


def import_basic_info_schema(fp: Path, od: OptionDict):
    """schemas/basic_info_schema_v2.json - BasicInfo UI 字段 schema。"""
    d = json.load(open(fp, "r", encoding="utf-8"))
    fields = d.get("fields", [])
    if not fields:
        return 0, 0
    options = []
    for f in fields:
        if not isinstance(f, dict):
            continue
        fid = f.get("id") or f.get("formModel") or ""
        label = f.get("label") or fid
        options.append({
            "code": str(fid),
            "name": str(label),
            "section": f.get("section"),
            "comp_type": f.get("compType"),
            "form_model": f.get("formModel"),
            "form_keys": f.get("formKeys"),
        })
    if not options:
        return 0, 0
    added = od.upsert_options(
        field_name="_schema_BasicInfo",
        options=options,
        label="BasicInfo UI 字段 schema (含 compType/formKeys)",
        source="schemas/basic_info_schema_v2.json",
    )
    return len(options), added


def import_bdi_fields(fp: Path, od: OptionDict):
    """schemas/bdi_fields.json - bdi 字段总表。"""
    d = json.load(open(fp, "r", encoding="utf-8"))
    sample = d.get("sample", [])
    if not sample:
        # 可能 totalKeys/filledKeys 是字段名列表
        keys = d.get("filledKeys", []) or d.get("totalKeys", [])
        if isinstance(keys, list):
            options = [{"code": str(k), "name": str(k)} for k in keys if k]
            if options:
                added = od.upsert_options(
                    field_name="_bdi_fields",
                    options=options,
                    label="bdi 业务接口字段总表",
                    source="schemas/bdi_fields.json",
                )
                return len(options), added
        return 0, 0
    # 如果 sample 是 list[dict]，提取
    if isinstance(sample, list):
        options = []
        for it in sample:
            if isinstance(it, dict):
                code = str(it.get("code") or it.get("key") or it.get("name") or "")
                name = str(it.get("name") or it.get("label") or it.get("desc") or code)
                if code:
                    options.append({"code": code, "name": name})
        if options:
            added = od.upsert_options(
                field_name="_bdi_fields",
                options=options,
                label="bdi 字段示例",
                source="schemas/bdi_fields.json",
            )
            return len(options), added
    return 0, 0


def import_ent_types_js(fp: Path, od: OptionDict):
    """dashboard/data/ent_types.js - JS 形式企业类型字典（提取 JSON 字面量）。"""
    text = fp.read_text(encoding="utf-8", errors="ignore")
    # 找 [...] 形式的 JSON 数组，且含 "code"/"name" 关键词
    m = re.search(r"=\s*(\[[\s\S]+?\])\s*[;\n]", text)
    if not m:
        return 0, 0
    try:
        arr = json.loads(m.group(1))
    except Exception:
        return 0, 0
    if not isinstance(arr, list):
        return 0, 0
    options = []
    seen = set()
    def walk(node):
        if isinstance(node, dict):
            code = node.get("code")
            name = node.get("name")
            if code and code not in seen:
                seen.add(code)
                options.append({"code": str(code), "name": str(name or "")})
            for ch in node.get("children", []) or []:
                walk(ch)
    for item in arr:
        walk(item)
    if not options:
        return 0, 0
    added = od.upsert_options(
        field_name="entType",
        options=options,
        label="企业类型（来自 ent_types.js 全树展平）",
        source="dashboard/data/ent_types.js",
    )
    return len(options), added


def main():
    od = OptionDict.load()
    print("=== 剩余资源整合 ===\n")
    total = 0

    # regions
    fp = Path("phase1_service/data/dictionaries/regions/root.json")
    if fp.exists():
        n, a = import_regions(fp, od)
        print(f"  regions/root.json              → distCode               +{a}/{n}")
        total += a

    # basic_info_schema_v2
    fp = Path("schemas/basic_info_schema_v2.json")
    if fp.exists():
        n, a = import_basic_info_schema(fp, od)
        print(f"  basic_info_schema_v2.json     → _schema_BasicInfo      +{a}/{n}")
        total += a

    # bdi_fields
    fp = Path("schemas/bdi_fields.json")
    if fp.exists():
        n, a = import_bdi_fields(fp, od)
        print(f"  bdi_fields.json               → _bdi_fields            +{a}/{n}")
        total += a

    # ent_types.js
    fp = Path("dashboard/data/ent_types.js")
    if fp.exists():
        n, a = import_ent_types_js(fp, od)
        print(f"  ent_types.js                  → entType                +{a}/{n}")
        total += a

    od.save()
    print(f"\n✅ 总新增 {total} 项 → {od.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
