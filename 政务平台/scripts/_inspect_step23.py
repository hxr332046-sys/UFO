"""Inspect the latest run results to understand step23 behavior."""
import json
from pathlib import Path

# Read the latest record
records = list(Path("dashboard/data/records").glob("smart_register__case_兴裕为*.json"))
if records:
    latest = max(records, key=lambda p: p.stat().st_mtime)
    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Find step 23 details
    steps = data.get("steps", [])
    for step in steps:
        name = step.get("name", "")
        if "23" in name or "ybb" in name.lower() or "produce" in name.lower():
            print(f"\n=== {name} ===")
            print(f"  ok: {step.get('ok')}")
            print(f"  code: {step.get('code')}")
            print(f"  result_type: {step.get('result_type')}")
            print(f"  message: {step.get('message', '')[:200]}")
            ext = step.get("extracted", {})
            if ext:
                print(f"  extracted:")
                for k, v in ext.items():
                    print(f"    {k}: {v}")

# Also read the phase2 establish latest
p2_path = Path("dashboard/data/records/phase2_establish_latest.json")
if p2_path.exists():
    with open(p2_path, "r", encoding="utf-8") as f:
        p2 = json.load(f)
    
    steps = p2.get("steps", [])
    for step in steps:
        name = step.get("name", "")
        idx = step.get("index", 0)
        if idx >= 22:  # Steps 23+
            print(f"\n=== [{idx}] {name} ===")
            print(f"  ok: {step.get('ok')}")
            print(f"  code: {step.get('code')}")
            print(f"  result_type: {step.get('result_type')}")
            print(f"  message: {step.get('message', '')[:200]}")
            ext = step.get("extracted", {})
            if ext:
                for k, v in ext.items():
                    val_str = str(v)[:120]
                    print(f"    {k}: {val_str}")
