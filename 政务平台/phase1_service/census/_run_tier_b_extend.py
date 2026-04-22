#!/usr/bin/env python
"""扩展 Tier B 普查：为所有未覆盖的 entType 拉取 industries / organizes / entTypeCfg。

目标 entType（排除已有的 4540 和 1100）:
  9100 农民专业合作社
  9600 个体工商户
  1110 ~ 1190 有限公司子类型
  fzjg 分支机构（可能不支持，跳过即可）

每个 entType × busiType 调 2~3 个 API，步间 2s，总共 ~40 请求，约 2 分钟。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402

DATA_DIR = ROOT / "phase1_service" / "data" / "dictionaries"

EXISTING = {"4540", "1100"}
TARGET_TYPES = ["9100", "9600", "1110", "1120", "1130", "1140", "1150", "1190"]
BUSI_TYPE = "01"

API_INDUSTRY = "/icpsp-api/v4/pc/common/configdata/getAllIndustryTypeCode"
API_ORGANIZE = "/icpsp-api/v4/pc/common/configdata/getOrganizeTypeCodeByEntTypeCircle"
API_ENT_CFG = "/icpsp-api/v4/pc/common/synchrdata/queryNameEntTypeCfgByEntType"


def fetch_and_save(client, path, params, save_path):
    resp = client.get_json(path, params)
    code = str(resp.get("code") or "")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    size = save_path.stat().st_size
    return code, size


def main():
    client = ICPSPClient()
    ok_count = 0
    fail_count = 0
    skip_count = 0

    for ent in TARGET_TYPES:
        print(f"\n=== entType={ent} ===")

        # industries
        ind_path = DATA_DIR / "industries" / f"entType_{ent}_busi_{BUSI_TYPE}.json"
        if ind_path.exists():
            print(f"  [SKIP] industries already exists ({ind_path.stat().st_size} bytes)")
            skip_count += 1
        else:
            time.sleep(2)
            try:
                code, size = fetch_and_save(
                    client, API_INDUSTRY,
                    {"busiType": BUSI_TYPE, "entType": ent, "range": "1"},
                    ind_path,
                )
                print(f"  [{'OK' if code == '00000' else 'FAIL'}] industries  code={code}  {size} bytes")
                ok_count += (1 if code == "00000" else 0)
                fail_count += (0 if code == "00000" else 1)
            except Exception as e:
                print(f"  [ERR] industries: {e}")
                fail_count += 1

        # organizes
        org_path = DATA_DIR / "organizes" / f"entType_{ent}_busi_{BUSI_TYPE}.json"
        if org_path.exists():
            print(f"  [SKIP] organizes already exists ({org_path.stat().st_size} bytes)")
            skip_count += 1
        else:
            time.sleep(2)
            try:
                code, size = fetch_and_save(
                    client, API_ORGANIZE,
                    {"busType": BUSI_TYPE, "entType": ent},
                    org_path,
                )
                print(f"  [{'OK' if code == '00000' else 'FAIL'}] organizes  code={code}  {size} bytes")
                ok_count += (1 if code == "00000" else 0)
                fail_count += (0 if code == "00000" else 1)
            except Exception as e:
                print(f"  [ERR] organizes: {e}")
                fail_count += 1

        # entTypeCfg
        cfg_path = DATA_DIR / "ent_type_cfgs" / f"entType_{ent}.json"
        if cfg_path.exists():
            print(f"  [SKIP] entTypeCfg already exists ({cfg_path.stat().st_size} bytes)")
            skip_count += 1
        else:
            time.sleep(2)
            try:
                code, size = fetch_and_save(
                    client, API_ENT_CFG,
                    {"entType": ent},
                    cfg_path,
                )
                print(f"  [{'OK' if code == '00000' else 'FAIL'}] entTypeCfg  code={code}  {size} bytes")
                ok_count += (1 if code == "00000" else 0)
                fail_count += (0 if code == "00000" else 1)
            except Exception as e:
                print(f"  [ERR] entTypeCfg: {e}")
                fail_count += 1

    print(f"\n=== 完成 === OK={ok_count}  FAIL={fail_count}  SKIP={skip_count}")


if __name__ == "__main__":
    main()
