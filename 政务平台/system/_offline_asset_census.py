"""资产普查：盘点本仓库的所有数据/知识/代码资产，输出可读报告。不发网络请求。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent

def _size(p: Path) -> int:
    try:
        return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except Exception:
        return 0

def _fmt(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"

def count_jsonl(p: Path) -> int:
    if not p.exists():
        return 0
    c = 0
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for _ in f:
            c += 1
    return c


print("=" * 70)
print("   政务平台仓库资产普查  (by offline, no network)")
print("=" * 70)

# 1. 原始流量证据
print("\n[1] 原始流量证据（真实浏览器抓包）")
mitm_live = ROOT / "dashboard/data/records/mitm_ufo_flows.jsonl"
mitm_bak = ROOT / "dashboard/data/records/mitm_ufo_flows_backup_20260421_231343.jsonl"
print(f"  mitm_ufo_flows.jsonl           {_fmt(_size(mitm_live))}  {count_jsonl(mitm_live)} 条")
print(f"  mitm_ufo_flows_backup_...jsonl {_fmt(_size(mitm_bak))}  {count_jsonl(mitm_bak)} 条")

# 2. 字典缓存（dict_cache）
print("\n[2] 字典缓存 (dashboard/data/records/dict_cache)")
dc = ROOT / "dashboard/data/records/dict_cache"
groups = {}
for f in sorted(dc.glob("*_latest.json")):
    # 按接口名归类
    stem = f.stem.replace("_latest", "")
    # 去掉尾部参数
    base = stem.split("_entType")[0].split("_type")[0].split("_range")[0]
    groups.setdefault(base, []).append((f.name, _size(f)))

for base, items in groups.items():
    total = sum(s for _, s in items)
    print(f"  {base:45s}  {len(items)} 种参数组合   {_fmt(total)}")

# 3. 统一字典 SQLite
print("\n[3] 结构化字典（SQLite 统一存储）")
db = ROOT / "dashboard/data/records/dict_v2.sqlite"
print(f"  dict_v2.sqlite                 {_fmt(_size(db))}")
if db.exists():
    try:
        import sqlite3
        con = sqlite3.connect(str(db))
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"  tables ({len(tables)}):")
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                cnt = cur.fetchone()[0]
                print(f"    - {t:40s}  {cnt} 行")
            except Exception:
                pass
        con.close()
    except Exception as e:
        print(f"  [err] {e!r}")

# 4. 关键运行证据
print("\n[4] 运行证据（关键记录）")
key_records = [
    ("phase1_protocol_driver_latest.json", "最新一次里程碑"),
    ("phase1_all_requests.json", "第一阶段全链路请求索引"),
    ("phase1_full_chain.json", "完整 7 步链路摘要"),
    ("phase1_steps_5_7_dump.json", "step5/7 完整 body/resp dump"),
    ("guide_base_ent_type_hierarchy_latest.json", "企业类型层级普查"),
    ("framework_rehearsal_run_latest.json", "完整链路预演"),
    ("night_autorun_to_yunbangban.json", "通宵自动运行到云办结"),
    ("packet_chain_portal_from_start.json", "portal 起手完整链"),
]
for fn, desc in key_records:
    p = ROOT / "dashboard/data/records" / fn
    print(f"  {fn:55s} {_fmt(_size(p)):>10s}  - {desc}")

# 5. 代码资产（system/）
print("\n[5] 代码资产 (system/)")
sys_dir = ROOT / "system"
py_files = sorted(sys_dir.glob("*.py"))
total_bytes = sum(_size(f) for f in py_files)
print(f"  python 脚本总计                  {len(py_files)} 个文件   {_fmt(total_bytes)}")
# 归类
categories = {
    "核心协议驱动": ["phase1_protocol_driver.py", "icpsp_api_client.py", "session_bootstrap_cdp.py",
                     "run_phase1_from_case.py", "phase1_recipe_replay_http.py",
                     "phase1_flow_save_with_hook.py", "phase1_recipe_cdp_record.py"],
    "字典工具":     ["build_dict_v2.py", "dict_v2_store.py", "absorb_query_cases_into_dict.py"],
    "离线分析(保留)": ["_offline_diff_steps_1_4.py", "_offline_deep_diff_step5.py",
                      "_offline_peek_step5_samples.py", "_offline_diff_step5_multi.py"],
    "框架 & LLM":   ["gov_task_run_model.py", "page_action_framework.py", "form_filler.py"],
}
for cat, files in categories.items():
    size = sum(_size(sys_dir / f) for f in files if (sys_dir / f).exists())
    present = sum(1 for f in files if (sys_dir / f).exists())
    print(f"    [{cat:20s}] {present}/{len(files)} 存在   {_fmt(size)}")

e2e_count = len(list(sys_dir.glob("e2e_*.py")))
probe_count = len(list(sys_dir.glob("probe_*.py")))
debug_count = len(list(sys_dir.glob("debug_*.py")))
tmp_count = len(list(sys_dir.glob("_tmp_*.py")))
other_count = len(py_files) - e2e_count - probe_count - debug_count - tmp_count
print(f"    [历史调试脚本      ] e2e_*={e2e_count}  probe_*={probe_count}  debug_*={debug_count}  _tmp_*={tmp_count}")
print(f"    [其他              ] {other_count}")

# 6. 方法论 & 文档
print("\n[6] 方法论 & 文档 (docs/)")
docs_dir = ROOT / "docs"
for f in sorted(docs_dir.glob("*.md")):
    print(f"  {f.name:55s} {_fmt(_size(f)):>10s}")
for f in sorted(docs_dir.glob("*.json")):
    print(f"  {f.name:55s} {_fmt(_size(f)):>10s}")

# 7. 全量度量
print("\n[7] 字典覆盖度（全量普查检查）")
known_ent_types = set()
known_regions = set()
for f in dc.glob("*_latest.json"):
    n = f.name
    for tok in n.split("_"):
        if tok.startswith("entType"):
            known_ent_types.add(tok.replace("entType", ""))

# 检查行政区 coverage
region_file = dc / "queryRegcodeAndStreet_latest.json"
if region_file.exists():
    try:
        d = json.loads(region_file.read_text(encoding="utf-8"))
        bd = d.get("data", {}).get("busiData") if isinstance(d, dict) else d
        if isinstance(bd, list):
            # 顶层省份
            known_regions = {item.get("id", "") for item in bd if isinstance(item, dict)}
    except Exception:
        pass

print(f"  entType 覆盖: {sorted(known_ent_types)}   （全国约 20+ 种）")
print(f"  省级区划覆盖: {len(known_regions)} 条 (顶层)   （样本: {sorted(known_regions)[:5]}）")

# 未抓的可能接口
print("\n[8] 可能未完整抓取的接口（从 mitm 备份里探测）")
seen_paths = {}
if mitm_bak.exists():
    with mitm_bak.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            u = str(r.get("url") or "")
            if "/icpsp-api/" not in u:
                continue
            path = u.split("?")[0]
            seen_paths[path] = seen_paths.get(path, 0) + 1
print(f"  mitm 备份里共发现 {len(seen_paths)} 个不同 API 路径")
# 列出前 30
for p, c in sorted(seen_paths.items(), key=lambda x: -x[1])[:30]:
    short = p.replace("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/", ".../")
    print(f"    {c:4d}x  {short}")
print(f"  ... 总共 {len(seen_paths)} 个接口，以上仅前 30")
