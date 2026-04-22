"""Tier D：经营范围（queryIndustryFeatAndDes），按 entType + 行业特征关键词(hyPecul)查询。

依赖：先跑 Tier B 的 getAllIndustryTypeCode，从其响应里提取所有可能的 hyPecul 关键词。

关键词来源策略（按优先级）：
1. getAllIndustryTypeCode 每个行业条目里的 industryCodeDet / industrySpecial / 特征字段
2. 若字段缺失，回退：从 industryName 中拆分关键词（简单分词）
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ._common import (
    CensusState,
    PaceConfig,
    check_rate_limit,
    do_get,
    extract_busi_data,
    pace_sleep,
    save_payload,
)
from icpsp_api_client import ICPSPClient  # type: ignore


HYPECUL_CANDIDATE_FIELDS = [
    "industryCodeDet",       # 最常见字段
    "industrySpecial",
    "hyPecul",
    "indSpecial",
    "industryFeat",
    "featDesc",
    "specialItem",
]

SEEDS_PATH = Path(__file__).resolve().parents[2] / "data/hypecul_seeds.json"


def _load_seed_keywords() -> Set[str]:
    """读 L1 高频词种子（+ custom_appended）。"""
    if not SEEDS_PATH.exists():
        return set()
    try:
        d = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
        kws: Set[str] = set()
        cats = d.get("categories") or {}
        if isinstance(cats, dict):
            for v in cats.values():
                if isinstance(v, list):
                    for k in v:
                        if isinstance(k, str) and k.strip():
                            kws.add(k.strip())
        appended = d.get("custom_appended") or []
        for k in appended:
            if isinstance(k, str) and k.strip():
                kws.add(k.strip())
        return kws
    except Exception as e:
        print(f"  [D] seeds parse fail: {e!r}")
        return set()


def _collect_from_industry_names(data_dir: Path, ent_type: str, busi_type: str, max_per_name: int = 2) -> Set[str]:
    """从 industries 的 name 字段切出"可能的 hyPecul"短语，限制每条 name 切出数量。
    规则：取 name 的后 2-3 字作为主特征（行业名通常以"...制造/销售/批发..."结尾）。"""
    p = data_dir / f"dictionaries/industries/entType_{ent_type}_busi_{busi_type}.json"
    if not p.exists():
        return set()
    try:
        wrapper = json.loads(p.read_text(encoding="utf-8"))
        resp = wrapper.get("data") or {}
        bd = extract_busi_data(resp)
        kws: Set[str] = set()
        if isinstance(bd, list):
            for row in bd:
                if not isinstance(row, dict):
                    continue
                nm = str(row.get("name") or "").strip()
                if not nm:
                    continue
                # 只切叶子节点（minKindSign=True）避免父类别
                if row.get("minKindSign") is False and row.get("kindSign") is False:
                    continue
                # 整名作为一个候选（≤ 6 字）
                if 2 <= len(nm) <= 6:
                    kws.add(nm)
                # 尾 2 字
                if len(nm) >= 2:
                    kws.add(nm[-2:])
                # 头 2 字
                if len(nm) >= 4:
                    kws.add(nm[:2])
        return kws
    except Exception as e:
        print(f"  [D] industry names parse fail: {e!r}")
        return set()


def _extract_hypecul_from_industries(
    data_dir: Path, ent_type: str, busi_type: str, *, seeds_only: bool = False
) -> Set[str]:
    """Tier D 关键词集合 = L1 seeds ∪ industries name 切片（seeds_only=True 时仅种子）。"""
    seeds = _load_seed_keywords()
    if seeds_only:
        return seeds
    names = _collect_from_industry_names(data_dir, ent_type, busi_type)
    return seeds | names


def _hypecul_hash(kw: str) -> str:
    return hashlib.md5(kw.encode("utf-8")).hexdigest()[:8]


def run_tier_d(
    client: ICPSPClient,
    tier_d_config: Dict[str, Any],
    data_dir: Path,
    state: CensusState,
    pace: PaceConfig,
    *,
    force: bool = False,
    only_ent_types: List[str] | None = None,
    only_busi_types: List[str] | None = None,
    limit_per_ent_type: int | None = None,
    seeds_only: bool = False,
) -> None:
    # 列出所有 (entType, busiType) 组合
    ent_types = only_ent_types
    if not ent_types:
        industries_dir = data_dir / "dictionaries/industries"
        ent_types = sorted({
            fn.stem.split("_")[1]
            for fn in industries_dir.glob("entType_*_busi_*.json")
            if fn.is_file()
        })

    busi_types = only_busi_types or tier_d_config.get("busi_types", ["01"])
    path = tier_d_config["path"]

    # 先采集所有 hyPecul
    all_combos: List[Tuple[str, str, str]] = []
    for et in ent_types:
        for bt in busi_types:
            kws = _extract_hypecul_from_industries(data_dir, et, bt, seeds_only=seeds_only)
            kws_list = sorted(kws)
            if limit_per_ent_type:
                kws_list = kws_list[:limit_per_ent_type]
            for kw in kws_list:
                all_combos.append((et, bt, kw))

    total = len(all_combos)
    print(f"  [D] 经营范围关键词矩阵：{len(ent_types)} entType × {len(busi_types)} busi × Σ = {total} 请求")
    if total == 0:
        print("  [D] 无 hyPecul 关键词可用，请确认 Tier B 已完成并产出了 industries/ 数据")
        return
    if total > 3000:
        print(f"  [!] 请求数 {total} 较大，预计耗时 {total * 2.5 / 3600:.1f}h。可用 --limit_per_ent_type 缩减")

    i = 0
    STATE_FLUSH_EVERY = 10   # 每 10 个请求回写一次 state，避免意外中断丢进度
    for et, bt, kw in all_combos:
        i += 1
        params = {"busType": bt, "entType": et, "hyPecul": kw}
        ckey = state.key("D:scope", params)
        kw_hash = _hypecul_hash(kw)
        save_rel = f"dictionaries/business_scopes/entType_{et}_busi_{bt}/{kw_hash}_{kw[:20]}.json"
        out_path = data_dir / save_rel

        # 文件级 skip：数据已落盘就跳过，避免 state 丢失时重抓
        if not force and (ckey in state.completed or out_path.exists()):
            if ckey not in state.completed and out_path.exists():
                state.completed[ckey] = {"status": "ok", "saved_path": save_rel, "ts": int(out_path.stat().st_mtime), "dur_ms": 0, "_recovered": True}
            if i % 50 == 0:
                print(f"  [D {i}/{total}] et={et} bt={bt} kw='{kw[:20]}' [skip: file exists]")
            continue

        print(f"  [D {i}/{total}] et={et} bt={bt} kw='{kw[:30]}'")
        started = time.time()
        resp = do_get(client, path, params)
        dur_ms = int((time.time() - started) * 1000)

        if check_rate_limit(resp):
            state.d0029_count += 1
            print(f"     !! D0029 累计 {state.d0029_count}，冷却 {pace.d0029_cooldown_sec}s")
            time.sleep(pace.d0029_cooldown_sec)
            if state.d0029_count >= pace.d0029_retry_threshold:
                raise RuntimeError("Tier D D0029 连续，中止")
            continue

        code = str(resp.get("code") or "")
        if code != "00000":
            state.failed[ckey] = {"job_id": "D:scope", "params": params, "resp_code": code, "ts": int(time.time())}
            pace_sleep(pace)
            continue

        save_payload(
            out_path, resp,
            {"job_id": "D:scope", "path": path, "params": params, "dur_ms": dur_ms, "keyword": kw, "ts": int(time.time())},
        )
        state.completed[ckey] = {"status": "ok", "saved_path": save_rel, "ts": int(time.time()), "dur_ms": dur_ms}
        state.total_requests += 1
        state.d0029_count = 0

        # 定期 flush state 到磁盘（每 10 个请求）
        if i % STATE_FLUSH_EVERY == 0:
            from phase1_service.census.run_census import STATE_PATH  # type: ignore
            try:
                state.save(STATE_PATH)
            except Exception:
                pass

        pace_sleep(pace)
