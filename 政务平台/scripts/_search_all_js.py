"""Search ALL JS files for flow-control, save callback, producePdf trigger."""
import re, os

out_dir = "packet_lab/out/frontend"
patterns = {
    "flowControl": r'flowControl',
    "fc.save": r'fc\.save',
    "handleNext": r'handleNext',
    "producePdf_call": r'producePdf\s*\(',
    "afterSave": r'afterSave',
    "onSaveSuccess": r'onSaveSuccess',
    "save_callback": r'save.*callback|callback.*save',
    "trigger_auto": r'trigger.*auto|auto.*trigger',
    "auto_produce": r'auto.*produce|produce.*auto',
}

for fname in sorted(os.listdir(out_dir)):
    if not fname.endswith(".js"):
        continue
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    found = []
    for name, pat in patterns.items():
        count = len(re.findall(pat, content))
        if count > 0:
            found.append(f"{name}={count}")
    
    if found:
        print(f"{fname}: {', '.join(found)}")

# Now deep search for producePdf call site
print("\n" + "=" * 80)
print("Deep search: who calls producePdf(t, n)?")
print("=" * 80)
for fname in sorted(os.listdir(out_dir)):
    if not fname.endswith(".js"):
        continue
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find producePdf being called (not defined)
    for m in re.finditer(r'.{0,500}producePdf\(.{0,500}', content):
        ctx = m.group()
        # Skip the function definition itself
        if "t.linkData.token=u()" in ctx:
            continue
        print(f"\n[{fname}]")
        print(ctx[:600])
        print("---")
