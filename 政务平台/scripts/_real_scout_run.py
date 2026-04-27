"""真实跑一次 Scout：用 packet_lab/out/component_loads/ 中的 8 个真实组件响应做扫描。
"""
import sys, json
from pathlib import Path

sys.path.insert(0, 'system')
from governance import OptionsScout, OptionDict


def main():
    src_dir = Path("packet_lab/out/component_loads")
    files = sorted(src_dir.glob("*_load.json"))
    print(f"=== Scout 普查：扫描 {len(files)} 个真实组件 load 响应 ===\n")

    od = OptionDict.load()
    scout = OptionsScout(od, log=True)

    for f in files:
        comp_name = f.stem.replace("_load", "")
        print(f"\n--- {comp_name} ---")
        try:
            resp = json.load(open(f, "r", encoding="utf-8"))
        except Exception as e:
            print(f"  跳过（解析失败）: {e}")
            continue
        scout.ingest_load_response(component=comp_name, load_resp=resp)

    print("\n\n=== 扫描完成 ===")
    rep = scout.report()
    print(f"  总 findings: {rep['total_findings']}")
    print(f"  涉及组件: {rep['components_seen']}")
    print(f"\n  字段一览:")
    for f in rep["fields"]:
        sample_codes = [s.get("code", "?") + "=" + s.get("name", "?")[:10] for s in f["sample"][:3]]
        print(f"    [{f['component']:18s}] {f['path']:55s} ×{f['options_count']:3d}  样本: {sample_codes}")

    # 持久化
    p = scout.persist()
    print(f"\n  字典已写入: {p}")

    # 复读看效果
    od2 = OptionDict.load()
    print(f"\n=== 字典最终状态 ===")
    print(f"  字段总数: {len(od2.fields)}")
    for fname, fopt in sorted(od2.fields.items()):
        print(f"  {fname:30s} ×{len(fopt.options):3d} options  source={fopt.source}")


if __name__ == "__main__":
    main()
