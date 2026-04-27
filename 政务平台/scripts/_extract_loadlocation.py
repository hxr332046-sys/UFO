"""Extract loadCurrentLocationInfo and producePdf call patterns from JS."""
import re

with open("packet_lab/out/frontend/core~002699c4.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find loadCurrentLocationInfo with wider context
print("=" * 80)
print("1. loadCurrentLocationInfo full context")
print("=" * 80)
for m in re.finditer(r'.{0,800}loadCurrentLocationInfo.{0,800}', content):
    print(m.group()[:1200])
    print("---")

# Find the continueFlag logic
print("\n" + "=" * 80)
print("2. continueFlag logic")
print("=" * 80)
for m in re.finditer(r'.{0,400}continueFlag.{0,400}', content):
    print(m.group()[:600])
    print("---")

# Find the jump function (navigation between components)
print("\n" + "=" * 80)
print("3. jump function (component navigation)")
print("=" * 80)
for m in re.finditer(r'.{0,400}\.jump.{0,400}', content):
    ctx = m.group()
    if "function" in ctx or "next" in ctx or "save" in ctx or "producePdf" in ctx:
        print(ctx[:600])
        print("---")
