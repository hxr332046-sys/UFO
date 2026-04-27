"""Find the save→producePdf flow in the Vue flow-control framework.
Search for the mixin that handles save success and auto-triggers producePdf.
"""
import re

# The flow-control framework is likely in core~0c65a408.js (637K, largest core file)
# or vendors~core~253ae210.js (555K)
for fname in ["core~0c65a408.js"]:
    fpath = f"packet_lab/out/frontend/{fname}"
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"Analyzing {fname} ({len(content)} chars)...")
    
    # Search for save success handler that triggers producePdf
    # The pattern would be: after save, check buttons for trigger="auto"
    patterns = [
        # Save callback
        r'.{0,300}save.*success.{0,300}',
        r'.{0,300}resultType.*0.{0,300}producePdf.{0,300}',
        r'.{0,300}producePdf.*resultType.{0,300}',
        # Auto trigger
        r'.{0,300}auto.*trigger.{0,300}producePdf.{0,300}',
        r'.{0,300}producePdf.*auto.{0,300}',
        # Button dispatch
        r'.{0,300}dispatch.*save.{0,300}',
        r'.{0,300}eventBus.{0,300}',
        # Flow control
        r'.{0,300}flowControl.{0,300}',
        r'.{0,300}fc\..{0,300}',
    ]
    
    for pat in patterns:
        matches = list(re.finditer(pat, content, re.IGNORECASE))
        if matches:
            print(f"\n  Pattern '{pat}': {len(matches)} matches")
            for m in matches[:2]:
                print(f"    {m.group()[:400]}")
                print("    ---")

# Also search for the Vue component that renders YbbSelect
print("\n\n=== YbbSelect Vue component ===")
for fname in ["core~0c65a408.js"]:
    fpath = f"packet_lab/out/frontend/{fname}"
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find YbbSelect component definition
    for m in re.finditer(r'.{0,200}YbbSelect.{0,500}', content):
        ctx = m.group()
        if "component" in ctx.lower() or "vue" in ctx.lower() or "name:" in ctx or "methods" in ctx:
            print(ctx[:600])
            print("---")
