"""Extract reProducePdf and related functions."""
import re

with open("packet_lab/out/frontend/core~0c65a408.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find the "45a0" module that contains reProducePdf
idx = content.find('"45a0"')
if idx >= 0:
    ctx = content[idx:idx+3000]
    print("Module 45a0 (reProducePdf):")
    print(ctx)
    print("---")

# Search for reProducePdf
print("\n\n=== reProducePdf ===")
for m in re.finditer(r'.{0,500}reProducePdf.{0,500}', content):
    print(m.group()[:800])
    print("---")

# Search for generalPreviewEleDoc
print("\n\n=== generalPreviewEleDoc ===")
for m in re.finditer(r'.{0,500}generalPreviewEleDoc.{0,500}', content):
    print(m.group()[:800])
    print("---")
