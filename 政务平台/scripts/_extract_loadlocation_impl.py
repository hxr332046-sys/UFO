"""Extract loadCurrentLocationInfo implementation precisely."""
import re

with open("packet_lab/out/frontend/core~002699c4.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find the loadCurrentLocationInfo function definition
# It should be near the linkData.token=u() call
idx = content.find("loadCurrentLocationInfo")
while idx >= 0:
    # Get 1000 chars before and after
    start = max(0, idx - 1000)
    end = min(len(content), idx + 1000)
    ctx = content[start:end]
    print(f"Position {idx}:")
    print(ctx)
    print("\n" + "=" * 80 + "\n")
    idx = content.find("loadCurrentLocationInfo", idx + 1)
