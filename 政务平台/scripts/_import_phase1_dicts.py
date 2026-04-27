"""把 phase1_service/data/dictionaries 下所有原有字典合并到 OptionDict。

发现的资源类型：
- code_lists/*.json: 服务端 queryCodeKV 接口响应快照
  * data.data.busiData = {<code>: {code, name, parent, enName}}
- organizes/entType_<X>_busi_01.json: 各企业类型对应的组织形式
  * data.busiData = [{name, code, entType, entPro, ...}, ...]
- regions/root.json: 行政区域树
- sys_configs/*.json: 系统配置（非枚举，跳过）
- industries/entType_<X>_busi_01.json: 行业树（IndustryMatcher 已用，跳过）

合并策略：upsert，已有 code 不覆盖（保护 Scout 实测优先），新 code 添加。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, 'system')
from governance import OptionDict


def _extract_busi_data(d):
    """从 phase1_service 字典文件抽 busiData（处理嵌套的 data.data.busiData / data.busiData）。"""
    if not isinstance(d, dict):
        return None
    data = d.get("data", {})
    if not isinstance(data, dict):
        return None
    # 形式 1: data.data.busiData （response 快照）
    if "code" in data and "data" in data:
        nested = data.get("data", {})
        if isinstance(nested, dict) and "busiData" in nested:
            return nested["busiData"]
    # 形式 2: data.busiData
    if "busiData" in data:
        return data["busiData"]
    return None


def import_code_list(fp, od, field_name=None, label=None):
    """code_lists/*.json — busiData 可能是 dict {code: {...}} 或 list [{...}]。"""
    d = json.load(open(fp, "r", encoding="utf-8"))
    busi = _extract_busi_data(d)
    options = []
    if isinstance(busi, dict) and busi:
        for k, v in busi.items():
            if isinstance(v, dict):
                options.append({
                    "code": str(v.get("code") or k),
                    "name": str(v.get("name") or ""),
                    **{kk: vv for kk, vv in v.items()
                       if kk not in ("code", "name") and vv is not None},
                })
    elif isinstance(busi, list) and busi:
        for v in busi:
            if isinstance(v, dict):
                code = str(v.get("code") or "")
                name = str(v.get("name") or "")
                if code or name:
                    options.append({
                        "code": code, "name": name,
                        **{kk: vv for kk, vv in v.items()
                           if kk not in ("code", "name") and vv is not None},
                    })
    if not options:
        return 0, 0
    fname = field_name or fp.stem.replace("CODE_", "").replace("_CODE", "").lower()
    added = od.upsert_options(
        field_name=fname,
        options=options,
        label=label or fname,
        source=f"phase1_service:{fp.name}",
    )
    return len(options), added


def import_organizes(p_dir, od):
    """organizes/entType_<X>_busi_01.json — 各企业类型组织形式。

    汇总到一个字段 `organize_form`，按 entType 分组（用 extra 标记）。
    """
    all_options = []
    seen = set()
    for fp in sorted(p_dir.glob("entType_*.json")):
        d = json.load(open(fp, "r", encoding="utf-8"))
        busi = _extract_busi_data(d)
        if not isinstance(busi, list):
            continue
        for it in busi:
            if not isinstance(it, dict):
                continue
            code = str(it.get("code") or "")
            ent_type = str(it.get("entType") or "")
            ent_pro = str(it.get("entPro") or "")
            name = str(it.get("name") or "")
            key = (ent_type, code)
            if key in seen:
                continue
            seen.add(key)
            if code and name:
                all_options.append({
                    "code": code,
                    "name": name,
                    "ent_type": ent_type,
                    "ent_pro": ent_pro,
                })
    if not all_options:
        return 0, 0
    added = od.upsert_options(
        field_name="organize_form",
        options=all_options,
        label="组织形式（按企业类型分组）",
        source=f"phase1_service:organizes/",
    )
    return len(all_options), added


def import_ent_type_codes(fp, od):
    """data/ent_type_codes.json — 企业类型树形字典。

    把树展平成一维（每个 code 一项）。
    """
    d = json.load(open(fp, "r", encoding="utf-8"))
    cats = d.get("categories", [])
    options = []
    def walk(node):
        if isinstance(node, dict):
            code = node.get("code")
            name = node.get("name")
            if code and name:
                options.append({"code": str(code), "name": str(name),
                                "parent": node.get("parent")})
            for ch in node.get("children", []) or []:
                walk(ch)
    for cat in cats:
        walk(cat)
    if not options:
        return 0, 0
    added = od.upsert_options(
        field_name="entType",
        options=options,
        label="企业类型代码",
        source=f"data/ent_type_codes.json",
    )
    return len(options), added


def main():
    od = OptionDict.load()
    print("=== phase1_service 字典统一导入 ===\n")
    total_added = 0

    # 1. code_lists
    cl_dir = Path("phase1_service/data/dictionaries/code_lists")
    field_map = {
        "CERTYPECODE": ("cerType", "证件类型（实测全集）"),
        "MOKINDCODE": ("currencyCode", "币种代码（含汇率）"),
    }
    for fp in sorted(cl_dir.glob("*.json")):
        stem = fp.stem
        fname, label = field_map.get(stem, (stem.lower(), stem))
        total, added = import_code_list(fp, od, field_name=fname, label=label)
        if total > 0:
            print(f"  [code_list] {fp.name:25s} → {fname:20s}  +{added}/{total}")
            total_added += added

    # 2. organizes
    org_dir = Path("phase1_service/data/dictionaries/organizes")
    if org_dir.exists():
        total, added = import_organizes(org_dir, od)
        if total > 0:
            print(f"  [organizes] (合并多文件)            → organize_form        +{added}/{total}")
            total_added += added

    # 3. ent_type_codes (data 目录)
    et_fp = Path("data/ent_type_codes.json")
    if et_fp.exists():
        total, added = import_ent_type_codes(et_fp, od)
        if total > 0:
            print(f"  [ent_types]  ent_type_codes.json    → entType              +{added}/{total}")
            total_added += added

    # 4. ent_types_typeN (phase1_service)
    for ext in ["ent_types_type1.json", "ent_types_type2.json"]:
        fp = Path("phase1_service/data/dictionaries") / ext
        if not fp.exists():
            continue
        d = json.load(open(fp, "r", encoding="utf-8"))
        busi = _extract_busi_data(d)
        if isinstance(busi, list):
            opts = [{"code": str(it.get("code") or ""), "name": str(it.get("name") or ""),
                     **{k: v for k, v in it.items() if k not in ("code", "name")}}
                    for it in busi if isinstance(it, dict) and it.get("code")]
            if opts:
                added = od.upsert_options(
                    field_name=f"entType_{ext.split('_')[2].split('.')[0]}",  # type1/type2
                    options=opts,
                    label=f"企业类型 {ext}",
                    source=f"phase1_service:{ext}",
                )
                print(f"  [ent_types]  {ext:25s} → entType_xxx          +{added}/{len(opts)}")
                total_added += added

    od.save()
    print(f"\n✅ 总新增 {total_added} 项 → {od.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
