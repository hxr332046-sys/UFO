#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
普查「设立登记 -> 名称核查」可复用字典（优先走 icpsp-api），落盘到 records/dict_cache。

输出为“框架资产”，用于：
- UI 自动化选项全量化（不靠截图/人工）
- 名称可用性查询（distCode/entType/organize/industry 取值空间）

用法：
  cd G:\\UFO\\政务平台
  .\\.venv-portal\\Scripts\\python.exe system\\survey_namecheck_dictionaries.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from icpsp_api_client import ICPSPClient


OUT_DIR = Path("G:/UFO/政务平台/dashboard/data/records/dict_cache")


def _save(name: str, obj: Any) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    p = OUT_DIR / f"{name}_{ts}.json"
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = OUT_DIR / f"{name}_latest.json"
    latest.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def main() -> None:
    c = ICPSPClient()
    rec: Dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "artifacts": {}}

    # 1) 区划/街道树（通常较大，但这是“可选项全量”的基础）
    reg_tree = c.get_json("/icpsp-api/v4/pc/common/synchrdata/queryRegcodeAndStreet", {"fromPage": "qykbdb"})
    rec["artifacts"]["queryRegcodeAndStreet"] = {"saved": _save("queryRegcodeAndStreet", reg_tree)}

    # 2) 名称业务主体类型（页面 1：市场主体类型）
    ent_type_1 = c.get_json("/icpsp-api/v4/pc/common/synchrdata/queryNameEntType", {"type": "1"})
    ent_type_2 = c.get_json("/icpsp-api/v4/pc/common/synchrdata/queryNameEntType", {"type": "2"})
    rec["artifacts"]["queryNameEntType"] = {"saved": _save("queryNameEntType_type1", ent_type_1), "saved2": _save("queryNameEntType_type2", ent_type_2)}

    # 3) 行业字典（全量很大；先抓 range=1 的常用集合作为框架起点）
    # 这里不写死 entType：先用“有限责任公司”常见 1100 和 “个体/个人独资” 4540 做两份
    industries_1100 = c.get_json("/icpsp-api/v4/pc/common/configdata/getAllIndustryTypeCode", {"busiType": "01", "entType": "1100", "range": "1"})
    industries_4540 = c.get_json("/icpsp-api/v4/pc/common/configdata/getAllIndustryTypeCode", {"busiType": "01", "entType": "4540", "range": "1"})
    rec["artifacts"]["getAllIndustryTypeCode"] = {"saved_1100": _save("getAllIndustryTypeCode_entType1100_range1", industries_1100), "saved_4540": _save("getAllIndustryTypeCode_entType4540_range1", industries_4540)}

    # 4) 组织形式（组织形式候选网格来自该接口，依赖 entType + busType）
    org_1100 = c.get_json("/icpsp-api/v4/pc/common/configdata/getOrganizeTypeCodeByEntTypeCircle", {"entType": "1100", "busType": "01"})
    org_4540 = c.get_json("/icpsp-api/v4/pc/common/configdata/getOrganizeTypeCodeByEntTypeCircle", {"entType": "4540", "busType": "01"})
    rec["artifacts"]["getOrganizeTypeCodeByEntTypeCircle"] = {"saved_1100": _save("getOrganizeTypeCodeByEntTypeCircle_entType1100", org_1100), "saved_4540": _save("getOrganizeTypeCodeByEntTypeCircle_entType4540", org_4540)}

    # 5) 可选：名称核查页面的内部 entTypeCfg（例如 radio 值 10/20/30）
    ent_cfg_1100 = c.get_json("/icpsp-api/v4/pc/common/synchrdata/queryNameEntTypeCfgByEntType", {"entType": "1100"})
    ent_cfg_4540 = c.get_json("/icpsp-api/v4/pc/common/synchrdata/queryNameEntTypeCfgByEntType", {"entType": "4540"})
    rec["artifacts"]["queryNameEntTypeCfgByEntType"] = {"saved_1100": _save("queryNameEntTypeCfgByEntType_1100", ent_cfg_1100), "saved_4540": _save("queryNameEntTypeCfgByEntType_4540", ent_cfg_4540)}

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out = Path("G:/UFO/政务平台/dashboard/data/records/survey_namecheck_dictionaries_latest.json")
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", out)


if __name__ == "__main__":
    main()

