"""把 dashboard/data/records/dict_cache/ 里已有的 industries/organizes 数据
移植到 phase1_service/data/dictionaries/ 下（按 Tier B 期望的 wrapper 格式）。
零上游消耗。仅用于 bootstrap。
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "dashboard/data/records/dict_cache"
DST = ROOT / "phase1_service/data/dictionaries"

# dict_cache 文件名 -> phase1_service 目标文件名模板
MAPPINGS = []

# getAllIndustryTypeCode -> industries/ (assume busiType=01)
for f in SRC.glob("getAllIndustryTypeCode_entType*_range1_latest.json"):
    ent_type = f.name.split("_entType")[1].split("_")[0]
    target = DST / "industries" / f"entType_{ent_type}_busi_01.json"
    MAPPINGS.append((f, target, {"job_id": "seeded_from_dict_cache", "entType": ent_type, "busiType": "01", "range": "1"}))

# getOrganizeTypeCodeByEntTypeCircle -> organizes/ (same)
for f in SRC.glob("getOrganizeTypeCodeByEntTypeCircle_entType*_latest.json"):
    ent_type = f.name.split("_entType")[1].split("_")[0]
    target = DST / "organizes" / f"entType_{ent_type}_busi_01.json"
    MAPPINGS.append((f, target, {"job_id": "seeded_from_dict_cache", "entType": ent_type, "busiType": "01"}))

# queryNameEntType type1/type2 -> ent_types_type{X}.json
for f in SRC.glob("queryNameEntType_type*_latest.json"):
    lvl = f.name.split("_type")[1].split("_")[0]
    target = DST / f"ent_types_type{lvl}.json"
    MAPPINGS.append((f, target, {"job_id": "seeded_from_dict_cache", "type": lvl}))

# queryNameEntTypeCfgByEntType -> ent_type_cfgs/
for f in SRC.glob("queryNameEntTypeCfgByEntType_*_latest.json"):
    # file name pattern: queryNameEntTypeCfgByEntType_1100_latest.json
    parts = f.stem.split("_")
    ent_type = parts[1] if len(parts) >= 2 else None
    if ent_type and ent_type.isdigit():
        target = DST / "ent_type_cfgs" / f"entType_{ent_type}.json"
        MAPPINGS.append((f, target, {"job_id": "seeded_from_dict_cache", "entType": ent_type}))

# queryRegcodeAndStreet -> regions/root.json
for f in SRC.glob("queryRegcodeAndStreet_latest.json"):
    target = DST / "regions" / "root.json"
    MAPPINGS.append((f, target, {"job_id": "seeded_from_dict_cache"}))


def wrap_payload(src_json: dict, meta: dict) -> dict:
    return {
        "schema": "phase1_service.census.payload.v1",
        "meta": {"job_id": meta.get("job_id"), "path": "/seeded", "params": meta, "dur_ms": 0, "ts": int(time.time())},
        "data": src_json,
    }


def main() -> int:
    done = 0
    for src, dst, meta in MAPPINGS:
        if not src.exists():
            continue
        try:
            raw = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  skip {src.name}: {e!r}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        wrapper = wrap_payload(raw, meta)
        dst.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")
        rel = dst.relative_to(DST.parent)
        print(f"  OK  {src.name}   ->  {rel}")
        done += 1
    print(f"\n== 移植完成：{done} 个文件 ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
