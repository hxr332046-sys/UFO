"""Search for trigger:auto handling in flow-control framework."""
import re, os

out_dir = "packet_lab/out/frontend"

# The framework must have code like:
# if (button.trigger === "auto") { executeButton(button) }
# or: switch(trigger) { case "auto": ... }

for fname in sorted(os.listdir(out_dir)):
    if not fname.endswith(".js"):
        continue
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Search for "auto" in code context (not just string literals)
    # Look for comparison with "auto" 
    for m in re.finditer(r'.{0,200}===?\s*"auto".{0,200}', content):
        ctx = m.group()
        print(f"[{fname}] {ctx[:400]}")
        print("---")
    
    for m in re.finditer(r'.{0,200}"auto"===?\s*.{0,200}', content):
        ctx = m.group()
        if "trigger" in ctx or "type" in ctx:
            print(f"[{fname}] {ctx[:400]}")
            print("---")
