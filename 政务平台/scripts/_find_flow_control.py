"""Find flow-control save callback and auto-trigger logic."""
import re

# Search in the largest JS file which likely contains the flow-control framework
for fname in ["core~0c65a408.js", "core~002699c4.js", "vendors~core~253ae210.js", "core~40cc254d.js"]:
    fpath = f"packet_lab/out/frontend/{fname}"
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
    except:
        continue
    
    # Search for flowControl or fc. patterns
    fc_patterns = [
        r'.{0,300}flowControl.{0,300}',
        r'.{0,300}fc\.save.{0,300}',
        r'.{0,300}handleNext.{0,300}',
        r'.{0,300}afterSave.{0,300}',
        r'.{0,300}onSave.{0,300}',
        r'.{0,300}saveCallback.{0,300}',
        r'.{0,300}saveSuccess.{0,300}',
    ]
    
    for pat in fc_patterns:
        matches = list(re.finditer(pat, content))
        if matches:
            print(f"\n{'='*80}")
            print(f"  {fname}: '{pat}' found {len(matches)} times")
            print(f"{'='*80}")
            for m in matches[:3]:  # Show first 3
                ctx = m.group()
                if "producePdf" in ctx or "trigger" in ctx or "auto" in ctx or "token" in ctx or "next" in ctx:
                    print(ctx[:500])
                    print("---")
