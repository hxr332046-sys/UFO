"""Extract producePdf logic from core JS chunks"""
import re
for f in ['dashboard/data/records/core_assets/core~40cc254d.js',
          'dashboard/data/records/core_assets/core~0c65a408.js',
          'dashboard/data/records/core_assets/base~21833f8f.js']:
    try:
        text = open(f, encoding='utf-8').read()
    except:
        continue
    # Find producePdf context (200 chars before and after)
    for m in re.finditer(r'producePdf', text):
        start = max(0, m.start() - 300)
        end = min(len(text), m.end() + 300)
        chunk = text[start:end]
        print(f"\n=== {f} at pos {m.start()} ===")
        print(chunk)
