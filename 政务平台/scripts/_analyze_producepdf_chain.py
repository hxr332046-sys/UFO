"""Find who calls producePdf - the complete call chain."""
import re

with open("packet_lab/out/frontend/core~40cc254d.js", "r", encoding="utf-8") as f:
    content = f.read()

# The producePdf button config says: trigger:"auto", refresh:!0, hide:!0
# This means producePdf is triggered automatically after save, not by user click
# Let's find the auto-trigger logic

print("=" * 80)
print("1. producePdf button: trigger='auto' - find auto trigger logic")
print("=" * 80)

# Search for trigger:"auto" or trigger==="auto" logic
for m in re.finditer(r'.{0,300}trigger.{0,100}auto.{0,300}', content):
    ctx = m.group()
    if "producePdf" in ctx or "save" in ctx or "button" in ctx or "event" in ctx:
        print(ctx)
        print("---")

print("\n" + "=" * 80)
print("2. fc.save / flowControl save logic")
print("=" * 80)
for m in re.finditer(r'.{0,400}fc\.save.{0,400}', content):
    print(m.group())
    print("---")

print("\n" + "=" * 80)
print("3. saveAndSubmit / save callback that triggers producePdf")
print("=" * 80)
for m in re.finditer(r'.{0,400}saveAndSubmit.{0,400}', content):
    ctx = m.group()
    if "producePdf" in ctx or "token" in ctx or "callback" in ctx or "then" in ctx:
        print(ctx)
        print("---")

print("\n" + "=" * 80)
print("4. o.http.request - the HTTP client wrapper")
print("=" * 80)
# Find the http module definition
for m in re.finditer(r'.{0,200}http\.request.{0,200}method.{0,100}post.{0,200}', content):
    ctx = m.group()
    if "producePdf" in ctx or "customError" in ctx:
        print(ctx)
        print("---")

print("\n" + "=" * 80)
print("5. customError handling in http.request")
print("=" * 80)
for m in re.finditer(r'.{0,300}customError.{0,300}', content):
    print(m.group())
    print("---")
