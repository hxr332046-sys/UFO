"""Find the cf5b mixin definition - the core flow-control mixin."""
import re

# Search in vendors file first (likely contains shared mixins)
for fname in ["vendors~core~253ae210.js", "core~0c65a408.js", "core~002699c4.js", "core~25b9f56b.js"]:
    fpath = f"packet_lab/out/frontend/{fname}"
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Search for cf5b module definition
    idx = content.find('cf5b:function')
    if idx < 0:
        idx = content.find('"cf5b":function')
    if idx < 0:
        idx = content.find('"cf5b":')
    
    if idx >= 0:
        print(f"\nFound cf5b in {fname} at position {idx}")
        ctx = content[max(0,idx-100):idx+8000]
        print(ctx[:8000])
        break
else:
    print("cf5b module not found in core files, searching in other files...")
    
    # Search for the mixin by its exported content
    for fname in ["vendors~core~253ae210.js"]:
        fpath = f"packet_lab/out/frontend/{fname}"
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Search for producePdf in the context of save callback
        for m in re.finditer(r'.{0,500}producePdf.{0,500}', content):
            print(m.group()[:800])
            print("---")
