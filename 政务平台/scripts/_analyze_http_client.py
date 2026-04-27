"""Analyze core~002699c4.js - the HTTP client and linkData.token module."""
import re

with open("packet_lab/out/frontend/core~002699c4.js", "r", encoding="utf-8") as f:
    content = f.read()

print(f"File size: {len(content)} chars")

# Find linkData.token context
print("\n" + "=" * 80)
print("1. linkData.token occurrences")
print("=" * 80)
for m in re.finditer(r'.{0,400}linkData\.token.{0,400}', content):
    print(m.group()[:600])
    print("---")

# Find customError context
print("\n" + "=" * 80)
print("2. customError handling")
print("=" * 80)
for m in re.finditer(r'.{0,400}customError.{0,400}', content):
    print(m.group()[:600])
    print("---")

# Find the http.request implementation
print("\n" + "=" * 80)
print("3. http.request implementation")
print("=" * 80)
for m in re.finditer(r'.{0,200}http\.request.{0,400}', content):
    print(m.group()[:500])
    print("---")

# Find the o.http module definition
print("\n" + "=" * 80)
print("4. http module / axios interceptor")
print("=" * 80)
for m in re.finditer(r'.{0,200}interceptor.{0,200}', content):
    print(m.group()[:400])
    print("---")
for m in re.finditer(r'.{0,200}axios.{0,200}', content):
    ctx = m.group()
    if "create" in ctx or "interceptor" in ctx or "baseURL" in ctx:
        print(ctx[:400])
        print("---")
