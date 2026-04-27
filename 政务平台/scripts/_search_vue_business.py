"""Search vue-business for trigger:auto and producePdf flow control."""
import re

with open("packet_lab/out/frontend/vue-business~76eadadb.js", "r", encoding="utf-8") as f:
    content = f.read()

print(f"File size: {len(content)} chars")

# Search for trigger:auto in context
print("\n=== trigger + auto ===")
for m in re.finditer(r'.{0,400}trigger.{0,100}auto.{0,400}', content):
    ctx = m.group()
    if "producePdf" in ctx or "save" in ctx or "button" in ctx or "event" in ctx or "click" in ctx:
        print(ctx[:600])
        print("---")

# Search for producePdf
print("\n=== producePdf ===")
for m in re.finditer(r'.{0,400}producePdf.{0,400}', content):
    print(m.group()[:600])
    print("---")

# Search for noAutoNav (key flag that controls auto navigation)
print("\n=== noAutoNav ===")
for m in re.finditer(r'.{0,400}noAutoNav.{0,400}', content):
    print(m.group()[:600])
    print("---")

# Search for operationBusinessDataInfo (the save function)
print("\n=== operationBusinessDataInfo ===")
for m in re.finditer(r'.{0,300}operationBusinessDataInfo.{0,300}', content):
    ctx = m.group()
    if "producePdf" in ctx or "trigger" in ctx or "auto" in ctx or "next" in ctx or "success" in ctx:
        print(ctx[:500])
        print("---")
