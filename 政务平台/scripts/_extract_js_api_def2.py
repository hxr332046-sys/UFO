"""Broader search for producePdf API definition in all JS assets"""
import re, os

# Search all JS files in core_assets
for root, dirs, files in os.walk('dashboard/data/records/core_assets'):
    for f in files:
        if not f.endswith('.js'):
            continue
        path = os.path.join(root, f)
        t = open(path, encoding='utf-8', errors='ignore').read()
        # Find producePdf with URL pattern
        for m in re.finditer(r'producePdf', t):
            start = max(0, m.start() - 200)
            end = min(len(t), m.end() + 200)
            chunk = t[start:end]
            if 'api' in chunk.lower() or 'url' in chunk.lower() or 'post' in chunk.lower() or 'request' in chunk.lower():
                print(f"\n=== {f} at pos {m.start()} ===")
                print(chunk[:500])

# Also search for the flow API module
for root, dirs, files in os.walk('dashboard/data/records/core_assets'):
    for f in files:
        if not f.endswith('.js'):
            continue
        path = os.path.join(root, f)
        t = open(path, encoding='utf-8', errors='ignore').read()
        # Find producePdf in API definitions
        for m in re.finditer(r'producePdf.*?:.*?function|producePdf.*?\(.*?\).*?\{', t):
            start = max(0, m.start() - 100)
            end = min(len(t), m.end() + 300)
            chunk = t[start:end]
            print(f"\n=== API DEF {f} at pos {m.start()} ===")
            print(chunk[:400])
