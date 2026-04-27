"""Deep extract of producePdf API call pattern from base~21833f8f.js"""
import re

text = open('dashboard/data/records/core_assets/base~21833f8f.js', encoding='utf-8').read()

# Find the requestWidgetApiByName function and how it constructs the API call
# Key pattern: a.$api.flow[t](h, g) where t="producePdf"
# When producePdf and no continueFlag: g = "2"
# This second arg "2" is MISSING from our protocol driver!

# Extract the full producePdf call chain
for m in re.finditer(r'producePdf.*?continueFlag', text):
    start = max(0, m.start() - 500)
    end = min(len(text), m.end() + 500)
    chunk = text[start:end]
    print(f"\n=== pos {m.start()} ===")
    print(chunk[:800])
    print("...")

# Also find $api.flow definition
for m in re.finditer(r'\$api\.flow', text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 200)
    chunk = text[start:end]
    print(f"\n=== $api.flow at pos {m.start()} ===")
    print(chunk[:400])
