"""Find the s() function that maps busiType to URL prefix"""
import re

text = open('dashboard/data/records/core_assets/core~40cc254d.js', encoding='utf-8', errors='ignore').read()

# Find the producePdf function and surrounding context
for m in re.finditer(r'producePdf', text):
    start = max(0, m.start() - 1000)
    end = min(len(text), m.end() + 500)
    chunk = text[start:end]
    if 'function' in chunk[-600:] and 'request' in chunk[-600:]:
        print(f"\n=== producePdf function context at pos {m.start()} ===")
        print(chunk[-800:])

# Find the s() helper - likely a URL prefix mapper
# Pattern: function s(t) returning a URL path prefix
for m in re.finditer(r'function\s+s\s*\(\s*t\s*\)\s*\{[^}]*icpsp|function\s+s\s*\(\s*\)\s*\{[^}]*register', text):
    start = max(0, m.start() - 100)
    end = min(len(text), m.end() + 300)
    print(f"\n=== s() function at pos {m.start()} ===")
    print(text[start:end][:400])

# Search for the URL prefix pattern near producePdf
for m in re.finditer(r'concat\(s\(', text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 200)
    chunk = text[start:end]
    if 'producePdf' in chunk or 'submit' in chunk or 'operationBusiness' in chunk:
        print(f"\n=== concat(s() at pos {m.start()} ===")
        print(chunk[:400])
