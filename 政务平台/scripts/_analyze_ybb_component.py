"""Find the auto-trigger logic for producePdf after save."""
import re

with open("packet_lab/out/frontend/core~0c65a408.js", "r", encoding="utf-8") as f:
    content = f.read()

# This file contains YbbSelect and isSelectYbb - likely has the component logic
print("=" * 80)
print("1. YbbSelect component - save and producePdf trigger")
print("=" * 80)
for m in re.finditer(r'.{0,500}YbbSelect.{0,500}', content):
    print(m.group())
    print("---")

print("\n" + "=" * 80)
print("2. isSelectYbb logic")
print("=" * 80)
for m in re.finditer(r'.{0,400}isSelectYbb.{0,400}', content):
    print(m.group())
    print("---")

print("\n" + "=" * 80)
print("3. trigger auto handling")
print("=" * 80)
for m in re.finditer(r'.{0,300}"auto".{0,300}', content):
    ctx = m.group()
    if "trigger" in ctx or "producePdf" in ctx or "save" in ctx or "event" in ctx:
        print(ctx)
        print("---")
