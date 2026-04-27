"""Search core JS files for noAutoNav and the save→auto-trigger chain."""
import re, os

out_dir = "packet_lab/out/frontend"
for fname in sorted(os.listdir(out_dir)):
    if not fname.endswith(".js"):
        continue
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    for pat in ["noAutoNav", "autoNav", "autoNext", "autoAdvance", "handleAutoBtn", "autoBtn", "autoEvent"]:
        count = content.count(pat)
        if count > 0:
            print(f"{fname}: '{pat}' found {count} times")

# Deep search in core~0c65a408.js for noAutoNav
print("\n=== noAutoNav in core~0c65a408.js ===")
fpath = os.path.join(out_dir, "core~0c65a408.js")
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

for m in re.finditer(r'.{0,500}noAutoNav.{0,500}', content):
    print(m.group()[:800])
    print("---")

# Also search for the save callback that triggers auto buttons
print("\n=== save callback + next/advance in core~0c65a408.js ===")
for m in re.finditer(r'.{0,300}resultType.*0.{0,300}', content):
    ctx = m.group()
    if "producePdf" in ctx or "auto" in ctx or "next" in ctx or "advance" in ctx or "trigger" in ctx:
        print(ctx[:500])
        print("---")
