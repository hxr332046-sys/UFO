"""Deep search for auto-producePdf trigger mechanism."""
import re

# Search core~0c65a408.js for auto_produce context
for fname in ["core~0c65a408.js", "core~40cc254d.js", "core~002699c4.js"]:
    fpath = f"packet_lab/out/frontend/{fname}"
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"\n{'='*80}")
    print(f"  {fname}")
    print(f"{'='*80}")
    
    # auto_produce
    for m in re.finditer(r'.{0,500}auto.{0,100}produce.{0,500}', content):
        print(m.group()[:600])
        print("---")
    
    # trigger_auto
    for m in re.finditer(r'.{0,500}trigger.{0,100}auto.{0,500}', content):
        ctx = m.group()
        if "producePdf" in ctx or "save" in ctx or "event" in ctx or "button" in ctx:
            print(ctx[:600])
            print("---")
    
    # save_callback
    for m in re.finditer(r'.{0,400}save.{0,100}callback.{0,400}', content, re.IGNORECASE):
        print(m.group()[:500])
        print("---")
