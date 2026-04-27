"""Find the flow-control mixin that handles trigger='auto' buttons."""
import re

# The mixin is likely in core~0c65a408.js (the largest core file)
# Search for the mixin that handles button triggers
with open("packet_lab/out/frontend/core~0c65a408.js", "r", encoding="utf-8") as f:
    content = f.read()

# Search for "cf5b" - this is the mixin referenced by many components
print("=== Searching for cf5b mixin ===")
idx = content.find('"cf5b"')
if idx >= 0:
    ctx = content[max(0,idx-200):idx+5000]
    print(ctx[:5000])

# Also search for the mixin that handles save/producePdf
print("\n\n=== Searching for operationBusinessDataInfo call in mixins ===")
for m in re.finditer(r'.{0,300}operationBusinessDataInfo.{0,300}', content):
    ctx = m.group()
    if "producePdf" in ctx or "trigger" in ctx or "auto" in ctx or "save" in ctx:
        print(ctx[:500])
        print("---")
