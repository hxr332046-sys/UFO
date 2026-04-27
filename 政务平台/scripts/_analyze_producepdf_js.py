"""Deep analysis of producePdf and linkData.token in core~40cc254d.js."""
import re

with open("packet_lab/out/frontend/core~40cc254d.js", "r", encoding="utf-8") as f:
    content = f.read()

print("=" * 80)
print("1. producePdf function definition")
print("=" * 80)
# Find producePdf function with wider context
for m in re.finditer(r'.{0,500}producePdf.{0,500}', content):
    ctx = m.group()
    if "function" in ctx or "return" in ctx or "token" in ctx:
        print(ctx)
        print("---")

print("\n" + "=" * 80)
print("2. All linkData.token occurrences with context")
print("=" * 80)
for m in re.finditer(r'.{0,300}linkData\.token.{0,300}', content):
    print(m.group())
    print("---")

print("\n" + "=" * 80)
print("3. producePdf button config and event handler")
print("=" * 80)
for m in re.finditer(r'.{0,400}producePdf.{0,400}', content):
    ctx = m.group()
    if "button" in ctx.lower() or "event" in ctx.lower() or "trigger" in ctx.lower() or "save" in ctx.lower():
        print(ctx)
        print("---")

print("\n" + "=" * 80)
print("4. u() function (user ID getter)")
print("=" * 80)
# Find the u() function that returns user ID
for m in re.finditer(r'function u\(\).{0,200}', content):
    print(m.group())
    print("---")
# Also search for sessionStorage.getItem pattern
for m in re.finditer(r'.{0,200}sessionStorage.{0,200}userinfo.{0,200}', content):
    print(m.group())
    print("---")

print("\n" + "=" * 80)
print("5. YbbSelect save/producePdf flow")
print("=" * 80)
for m in re.finditer(r'.{0,400}YbbSelect.{0,400}', content):
    print(m.group())
    print("---")
