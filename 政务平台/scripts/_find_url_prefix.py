"""Find the s() URL prefix mapper function in core JS"""
import re

text = open('dashboard/data/records/core_assets/core~40cc254d.js', encoding='utf-8', errors='ignore').read()

# The s() is used in URL construction: "/".concat(s(busiType), "/producePdf")
# It maps busiType like "02" to a URL prefix like "register/establish"
# Search near the flow API module definition

# Find the module that exports producePdf, submit, etc.
for m in re.finditer(r'producePdf.*?function.*?return.*?request', text):
    start = max(0, m.start() - 3000)
    end = min(len(text), m.end() + 200)
    chunk = text[start:end]
    # Look for s= or function s in this chunk
    s_defs = list(re.finditer(r'function\s+s\s*\([^)]*\)\s*\{[^}]{0,500}\}', chunk))
    if s_defs:
        for sd in s_defs:
            print(f"\n=== s() definition near producePdf ===")
            print(chunk[sd.start():sd.start()+300])
    
    # Also look for s= assignment
    s_assigns = list(re.finditer(r's\s*=\s*function\s*\([^)]*\)\s*\{[^}]{0,300}\}', chunk))
    if s_assigns:
        for sa in s_assigns:
            print(f"\n=== s= assignment near producePdf ===")
            print(chunk[sa.start():sa.start()+300])

# Direct search for the URL prefix mapper
for m in re.finditer(r'register/establish|register/name|register/alt', text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 100)
    chunk = text[start:end]
    if 'busiType' in chunk or 'function' in chunk:
        print(f"\n=== URL prefix at pos {m.start()} ===")
        print(chunk[:300])
