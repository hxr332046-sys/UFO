"""Find the $api.flow definition for producePdf - what does the 2nd arg 'g' map to?"""
import re

text = open('dashboard/data/records/core_assets/base~21833f8f.js', encoding='utf-8').read()

# Search for flow API definitions - producePdf endpoint
# Pattern: producePdf: function(...) or producePdf(t, ...) 
for m in re.finditer(r'producePdf[:\s]*function|producePdf\s*[:(]', text):
    start = max(0, m.start() - 100)
    end = min(len(text), m.end() + 400)
    chunk = text[start:end]
    print(f"\n=== pos {m.start()} ===")
    print(chunk[:500])

# Also search for the API module definition
for m in re.finditer(r'producePdf.*?icpsp-api', text):
    start = max(0, m.start() - 100)
    end = min(len(text), m.end() + 200)
    chunk = text[start:end]
    print(f"\n=== API path at pos {m.start()} ===")
    print(chunk[:300])

# Search in all JS files
import os
for root, dirs, files in os.walk('dashboard/data/records/core_assets'):
    for f in files:
        if not f.endswith('.js'):
            continue
        path = os.path.join(root, f)
        t = open(path, encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r'producePdf.*?icpsp-api.*?register', t):
            start = max(0, m.start() - 50)
            end = min(len(t), m.end() + 100)
            print(f"\n=== {f} at pos {m.start()} ===")
            print(t[start:end][:300])
