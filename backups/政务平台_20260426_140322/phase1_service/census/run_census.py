"""第一阶段全量字典普查主脚本。

用法：
  python phase1_service/census/run_census.py --tier A
  python phase1_service/census/run_census.py --tier all --resume
  python phase1_service/census/run_census.py --tier D --limit_per_ent_type 20

注意：
  - 默认守护节奏（2-3.5s/请求），请勿调小。
  - D0029 连续 2 次即冷却 10 分钟并中止当前 tier。
  - 中断后加 --resume 可以从断点继续。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))           # 让 `phase1_service.*` 可以被 import
sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # type: ignore  # noqa: E402

from phase1_service.census.registry._common import CensusState, PaceConfig  # noqa: E402
from phase1_service.census.registry.tier_a import run_tier_a  # noqa: E402
from phase1_service.census.registry.tier_b import run_tier_b  # noqa: E402
from phase1_service.census.registry.tier_c import run_tier_c  # noqa: E402
from phase1_service.census.registry.tier_d import run_tier_d  # noqa: E402

PLAN_PATH = ROOT / "phase1_service/census/census_plan.json"
DATA_DIR = ROOT / "phase1_service/data"
STATE_PATH = DATA_DIR / "cache/census_state.json"


def _print_banner(tier: str) -> None:
    print("=" * 72)
    print(f"  Phase 1 字典全量普查  Tier={tier}")
    print("=" * 72)


def _print_summary(state: CensusState, dur_sec: float) -> None:
    print()
    print("-" * 72)
    print(f"  完成  {len(state.completed)}")
    print(f"  失败  {len(state.failed)}")
    print(f"  D0029 累计  {state.d0029_count}")
    print(f"  总请求  {state.total_requests}")
    print(f"  耗时  {dur_sec:.1f}s")
    print("-" * 72)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["A", "B", "C", "D", "all"], default="A")
    ap.add_argument("--resume", action="store_true", help="断点续跑（默认行为；显式标注即可）")
    ap.add_argument("--force", action="store_true", help="忽略 state.completed，重新抓")
    ap.add_argument("--limit_per_ent_type", type=int, default=None, help="Tier D 每个 entType 的 hyPecul 关键词上限")
    ap.add_argument("--only_ent_types", type=str, default="", help="逗号分隔，仅跑这些 entType（如 4540,1100）")
    ap.add_argument("--only_busi_types", type=str, default="", help="逗号分隔，Tier D 仅跑这些 busiType（如 01）")
    ap.add_argument("--only_dist_codes", type=str, default="", help="逗号分隔，Tier C 仅跑这些区划")
    ap.add_argument("--seeds_only", action="store_true", help="Tier D 只用 L1 种子关键词（不用 industry name 切片）")
    ap.add_argument("--dry_run", action="store_true", help="不发请求，只打印将要做的事")
    args = ap.parse_args()

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    pace = PaceConfig(**plan.get("pacing", {}))
    state = CensusState.load(STATE_PATH)

    only_ent_types = [s.strip() for s in args.only_ent_types.split(",") if s.strip()] or None
    only_busi_types = [s.strip() for s in args.only_busi_types.split(",") if s.strip()] or None
    only_dist_codes = [s.strip() for s in args.only_dist_codes.split(",") if s.strip()] or None

    client = ICPSPClient()

    t0 = time.time()

    try:
        if args.tier in ("A", "all"):
            _print_banner("A · 无参数字典")
            if args.dry_run:
                for item in plan["tier_a_no_param"]:
                    print(f"  would GET {item['path']}  params={item.get('params')}")
            else:
                run_tier_a(client, plan["tier_a_no_param"], DATA_DIR, state, pace, force=args.force)
                state.save(STATE_PATH)

        if args.tier in ("B", "all"):
            _print_banner("B · entType × busiType")
            if args.dry_run:
                tb = plan["tier_b_per_ent_type"]
                print(f"  ent_type_source={tb['ent_type_source']}  busi_types={tb['busi_types']}  templates={len(tb['templates'])}")
            else:
                run_tier_b(client, plan["tier_b_per_ent_type"], DATA_DIR, state, pace,
                           force=args.force, only_ent_types=only_ent_types)
                state.save(STATE_PATH)

        if args.tier in ("C", "all"):
            _print_banner("C · entType × 区划")
            if args.dry_run:
                tc = plan["tier_c_per_ent_region"]
                print(f"  templates={len(tc['templates'])}  max_level={tc.get('dist_level_max')}")
            else:
                run_tier_c(client, plan["tier_c_per_ent_region"], DATA_DIR, state, pace,
                           force=args.force, only_ent_types=only_ent_types, only_dist_codes=only_dist_codes)
                state.save(STATE_PATH)

        if args.tier in ("D", "all"):
            _print_banner("D · 经营范围  queryIndustryFeatAndDes")
            if args.dry_run:
                td = plan["tier_d_business_scope"]
                print(f"  path={td['path']}  busi_types={td.get('busi_types')}  hyPecul 来源: {'seeds only' if args.seeds_only else 'seeds ∪ industry names'}")
            else:
                run_tier_d(client, plan["tier_d_business_scope"], DATA_DIR, state, pace,
                           force=args.force,
                           only_ent_types=only_ent_types,
                           only_busi_types=only_busi_types,
                           limit_per_ent_type=args.limit_per_ent_type,
                           seeds_only=args.seeds_only)
                state.save(STATE_PATH)

    except KeyboardInterrupt:
        print("\n[中断] 保存状态到 census_state.json")
        state.save(STATE_PATH)
        return 130
    except RuntimeError as e:
        print(f"\n[中止] {e}")
        state.save(STATE_PATH)
        return 2

    dur = time.time() - t0
    _print_summary(state, dur)
    state.save(STATE_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
