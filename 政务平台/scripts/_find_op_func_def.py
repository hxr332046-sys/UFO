"""Search for the operationBusinessDataInfo function signature and its 6th param."""
import re, os

out_dir = "packet_lab/out/frontend"

# The function signature is: operationBusinessDataInfo(opeType, compUrl, busiData, itemId, continueFlag, noAutoNav)
# The 6th param noAutoNav controls whether to auto-navigate after save
# Search for this pattern in all JS files

for fname in sorted(os.listdir(out_dir)):
    if not fname.endswith(".js"):
        continue
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Search for the function definition with 6 params
    for m in re.finditer(r'.{0,200}operationBusinessDataInfo.{0,200}', content):
        ctx = m.group()
        if "function" in ctx or "params" in ctx or "arg" in ctx:
            print(f"[{fname}] {ctx[:400]}")
            print("---")

# Also search for the mixin that defines operationBusinessDataInfo
print("\n\n=== Looking for the mixin definition ===")
for fname in ["vue-element~fa510715.js"]:
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find operationBusinessDataInfo definition
    for m in re.finditer(r'.{0,500}operationBusinessDataInfo.{0,500}', content):
        ctx = m.group()
        if "function" in ctx or "method" in ctx or "prototype" in ctx or "defineProperty" in ctx:
            print(ctx[:800])
            print("---")
