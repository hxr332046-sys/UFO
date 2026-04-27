"""Extract customError handling logic from core JS"""
import re
with open("dashboard/data/records/core_assets/core~40cc254d.js", "r", encoding="utf-8") as f:
    text = f.read()

# Find customError usage patterns
for m in re.finditer(r'customError[^;]{0,200}', text):
    print(m.group()[:150])
    print("---")
