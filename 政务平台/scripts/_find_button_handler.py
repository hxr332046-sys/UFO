"""Search for the Vue mixin/component that handles save to producePdf flow."""
import re

for fname in ["vendors~core~253ae210.js", "core~002699c4.js", "core~25b9f56b.js"]:
    fpath = f"packet_lab/out/frontend/{fname}"
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"\n{'='*80}")
    print(f"  {fname} ({len(content)} chars)")
    print(f"{'='*80}")
    
    patterns = [
        (r'.{0,300}event.*producePdf.{0,300}', "event+producePdf"),
        (r'.{0,300}dispatch.*producePdf.{0,300}', "dispatch+producePdf"),
        (r'.{0,300}btnCode.*producePdf.{0,300}', "btnCode+producePdf"),
        (r'.{0,300}buttonClick.{0,300}', "buttonClick"),
        (r'.{0,300}handleButtonClick.{0,300}', "handleButtonClick"),
        (r'.{0,300}executeButton.{0,300}', "executeButton"),
        (r'.{0,300}processVo.{0,300}', "processVo"),
        (r'.{0,300}currentLocationVo.{0,300}', "currentLocationVo"),
    ]
    
    for pat, label in patterns:
        matches = list(re.finditer(pat, content))
        if matches:
            print(f"\n  [{label}] found {len(matches)} times:")
            for m in matches[:2]:
                print(f"    {m.group()[:400]}")
                print("    ---")
