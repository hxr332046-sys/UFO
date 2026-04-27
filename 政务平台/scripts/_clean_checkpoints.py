"""Clean up stale checkpoints and run fresh."""
import sys, json, os
from pathlib import Path

# Clean checkpoint directory
cp_dir = Path("dashboard/data/checkpoints")
if cp_dir.exists():
    for f in cp_dir.glob("*.json"):
        if "phase2" in f.name or "establish" in f.name or "兴裕为" in f.name or "xingyuwei" in f.name:
            print(f"  Deleting: {f.name}")
            f.unlink()

# Also clean the latest records that reference old busiId
records_dir = Path("dashboard/data/records")
for f in records_dir.glob("smart_register__*.json"):
    print(f"  Deleting: {f.name}")
    f.unlink()

# Clean phase2 latest
for f in records_dir.glob("phase2_establish_latest.json"):
    print(f"  Deleting: {f.name}")
    f.unlink()

print("\nCheckpoint cleanup done!")
