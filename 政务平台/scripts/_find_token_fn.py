"""Find the u() token generator function used in producePdf"""
import re

text = open('dashboard/data/records/core_assets/core~40cc254d.js', encoding='utf-8', errors='ignore').read()

# The producePdf function does: t.linkData.token = u()
# Find u() near the flow API module (around pos 262000-266000)
chunk = text[260000:270000]

# Find function u or var u near producePdf
for m in re.finditer(r'function\s+u\s*\(\s*\)\s*\{[^}]{0,300}\}', chunk):
    print(f"\n=== function u() at chunk pos {m.start()} ===")
    print(chunk[m.start():m.start()+300])

# Also search for u= assignment
for m in re.finditer(r'u\s*=\s*function\s*\(\s*\)\s*\{[^}]{0,300}\}', chunk):
    print(f"\n=== u = function() at chunk pos {m.start()} ===")
    print(chunk[m.start():m.start()+300])

# Search for token generation patterns
for m in re.finditer(r'token.*?uuid|token.*?random|token.*?Date\.now|token.*?timestamp', chunk):
    start = max(0, m.start() - 100)
    end = min(len(chunk), m.end() + 200)
    print(f"\n=== token generation at chunk pos {m.start()} ===")
    print(chunk[start:end][:300])

# Also check what customError does in the HTTP client
for m in re.finditer(r'customError', text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 200)
    chunk2 = text[start:end]
    if 'interceptor' in chunk2.lower() or 'error' in chunk2.lower() or 'catch' in chunk2.lower() or 'response' in chunk2.lower():
        print(f"\n=== customError handling at pos {m.start()} ===")
        print(chunk2[:400])
