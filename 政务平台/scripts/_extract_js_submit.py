"""Extract submit API definition from JS"""
import re
text = open('dashboard/data/records/core_assets/core~40cc254d.js', encoding='utf-8', errors='ignore').read()

# Find submit function near producePdf (around pos 265000-270000)
chunk = text[264000:270000]
for m in re.finditer(r'submit.*?function.*?return.*?request', chunk):
    start = max(0, m.start() - 200)
    end = min(len(chunk), m.end() + 300)
    print(f"\n=== submit function at chunk pos {m.start()} ===")
    print(chunk[start:end][:500])

# Also check preSubmit
for m in re.finditer(r'preSubmit.*?function.*?return.*?request', chunk):
    start = max(0, m.start() - 200)
    end = min(len(chunk), m.end() + 300)
    print(f"\n=== preSubmit function at chunk pos {m.start()} ===")
    print(chunk[start:end][:500])
