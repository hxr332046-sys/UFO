#!/usr/bin/env python
"""Wave 2 经营范围普查：从行业名提取关键词，补充 Tier D。

策略：
  1) 从 industries 字典提取所有行业名
  2) 去掉常见后缀（业/服务/制造 等），提取 2-4 字核心词
  3) 去重已有 Wave 1 种子
  4) 按 entType × busiType 调 queryIndustryFeatAndDes
  5) 文件级断点续传（已有文件跳过）

默认跑 2-4 字短词（Wave 2A，约 500 关键词），
传 --full 跑全量（约 1900+ 关键词）。
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402

DATA_DIR = ROOT / "phase1_service" / "data" / "dictionaries"
SCOPE_DIR = DATA_DIR / "business_scopes"
SEEDS_FILE = ROOT / "phase1_service" / "data" / "hypecul_seeds.json"
IND_DIR = DATA_DIR / "industries"

API_SCOPE = "/icpsp-api/v4/pc/common/synchrdata/queryIndustryFeatAndDes"
ENT_TYPES = ["4540", "1100"]
BUSI_TYPES = ["01"]

RATE_LIMIT_CODE = "D0029"


def extract_keywords(full_mode=False):
    """从 industries 提取关键词。"""
    names = set()
    for f in IND_DIR.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        bd = d.get("data", {}).get("data", {}).get("busiData") or d.get("data", {}).get("busiData")
        if isinstance(bd, dict):
            bd = bd.get("pagetypes") or []
        for item in (bd if isinstance(bd, list) else []):
            nm = (item.get("name") or "").strip()
            if nm and len(nm) >= 2:
                names.add(nm)

    # 已有种子
    existing = set()
    if SEEDS_FILE.exists():
        seeds = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))
        for cat_list in seeds.get("categories", {}).values():
            existing.update(cat_list)
        existing.update(seeds.get("custom_appended", []))

    keywords = set()
    for nm in names:
        core = nm
        for suffix in ["业", "服务", "制造", "加工", "生产", "零售", "批发", "出租"]:
            if core.endswith(suffix) and len(core) > len(suffix) + 1:
                base = core[: -len(suffix)]
                if len(base) >= 2:
                    keywords.add(base)
        if len(core) >= 2 and len(core) <= 6:
            keywords.add(core)

    new_kw = keywords - existing

    if not full_mode:
        # Wave 2A: 只保留 2-4 字短词
        new_kw = {kw for kw in new_kw if 2 <= len(kw) <= 4}

    return sorted(new_kw)


def kw_hash(kw):
    return hashlib.md5(kw.encode()).hexdigest()[:8]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="跑全量关键词")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kws = extract_keywords(full_mode=args.full)
    total_requests = len(kws) * len(ENT_TYPES) * len(BUSI_TYPES)
    print(f"关键词: {len(kws)} 个 ({'全量' if args.full else '短词 2-4 字'})")
    print(f"预估请求: {total_requests} ({len(kws)} × {len(ENT_TYPES)} entType × {len(BUSI_TYPES)} busiType)")
    print(f"预估耗时: ~{total_requests * 2 / 60:.0f} 分钟\n")

    if args.dry_run:
        print("--dry-run, 不发请求")
        print(f"前 20 个关键词: {kws[:20]}")
        return

    client = ICPSPClient()
    ok = skip = fail = d0029 = 0
    total_items = 0

    for i, kw in enumerate(kws, 1):
        for ent in ENT_TYPES:
            for busi in BUSI_TYPES:
                h = kw_hash(kw)
                out_dir = SCOPE_DIR / f"entType_{ent}_busi_{busi}"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"{h}.json"

                if out_file.exists():
                    skip += 1
                    continue

                time.sleep(2)
                try:
                    resp = client.get_json(API_SCOPE, {
                        "busType": busi,
                        "hyPecul": kw,
                        "entType": ent,
                    })
                    code = str(resp.get("code") or "")

                    if code == RATE_LIMIT_CODE:
                        print(f"\n  [D0029] 限流！等待 10 分钟...")
                        d0029 += 1
                        time.sleep(600)
                        # 重试
                        resp = client.get_json(API_SCOPE, {
                            "busType": busi, "hyPecul": kw, "entType": ent
                        })
                        code = str(resp.get("code") or "")

                    # 写入文件（即使 code!=00000 也保存，供分析）
                    resp["_meta"] = {"hyPecul": kw, "entType": ent, "busiType": busi}
                    out_file.write_text(
                        json.dumps(resp, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                    if code == "00000":
                        ok += 1
                        bd = resp.get("data", {}).get("data", {}).get("busiData")
                        if isinstance(bd, list):
                            total_items += len(bd)
                    else:
                        fail += 1
                except Exception as e:
                    print(f"\n  [ERR] {kw}/{ent}/{busi}: {e}")
                    fail += 1

        if i % 50 == 0:
            print(f"  [{i}/{len(kws)}] ok={ok} skip={skip} fail={fail} items={total_items}")

    print(f"\n=== Wave 2 完成 ===")
    print(f"  OK={ok}  SKIP={skip}  FAIL={fail}  D0029={d0029}")
    print(f"  新增经营范围条目: {total_items}")


if __name__ == "__main__":
    main()
