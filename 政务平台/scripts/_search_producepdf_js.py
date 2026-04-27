"""Search downloaded JS files for producePdf call context."""
import re, os
from pathlib import Path

# Search all downloaded JS files
js_dir = Path("packet_lab/out")
js_files = list(js_dir.glob("*.js")) + list(js_dir.glob("core*.js"))

# Also search the vue-business file
for f in js_dir.glob("vue-business*.js"):
    js_files.append(f)

# And tools
for f in js_dir.glob("tools*.js"):
    js_files.append(f)

print(f"Found {len(js_files)} JS files to search")

# Search for producePdf
for fp in js_files:
    if not fp.exists():
        continue
    content = fp.read_text(encoding="utf-8", errors="ignore")
    
    # Find producePdf
    matches = list(re.finditer(r'producePdf', content))
    if matches:
        print(f"\n=== {fp.name}: {len(matches)} matches ===")
        for m in matches[:5]:
            start = max(0, m.start() - 200)
            end = min(len(content), m.end() + 200)
            context = content[start:end]
            print(f"  ...{context}...")
            print()
