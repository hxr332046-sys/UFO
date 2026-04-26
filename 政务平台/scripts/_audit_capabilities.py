"""Audit all system/*.py for protocol capabilities not yet in the pipeline"""
import os, re, json

files = {}
for root, dirs, fnames in os.walk('system'):
    dirs[:] = [d for d in dirs if d not in ('_archive', '__pycache__')]
    for f in fnames:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        with open(path, encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
        defs = re.findall(r'def (\w+)', text)
        eps = set(re.findall(r'/icpsp-api/v[34]/pc/[a-zA-Z/]+', text))
        files[path] = {"defs": defs, "endpoints": eps, "size": len(text)}

# Core pipeline files
pipeline_apis = set()
for path in ['system/phase1_protocol_driver.py', 'system/phase2_protocol_driver.py',
             'system/run_smart_register.py', 'system/phase2_bodies.py']:
    if path in files:
        pipeline_apis |= files[path]["endpoints"]

# Categorize
categories = {
    "login_auth": ["login", "auth", "session", "qrcode", "keepalive", "token"],
    "upload": ["upload", "attachment", "file"],
    "cdp": ["cdp"],
    "crypto": ["crypto", "encrypt", "decrypt"],
    "monitor": ["mitm", "capture", "replay", "watch", "monitor"],
    "api_server": ["server", "api", "route", "endpoint"],
    "other_protocol": [],
}

print("=" * 70)
print("  PROTOCOL CAPABILITY AUDIT")
print("=" * 70)

# 1. APIs in pipeline vs total
all_apis = set()
for info in files.values():
    all_apis |= info["endpoints"]

print(f"\n1. API ENDPOINTS")
print(f"   Total discovered: {len(all_apis)}")
print(f"   In pipeline:      {len(pipeline_apis)}")
print(f"   NOT in pipeline:")
for api in sorted(all_apis - pipeline_apis):
    print(f"     - {api}")

# 2. Key standalone files with protocol capabilities
print(f"\n2. STANDALONE FILES WITH PROTOCOL CAPABILITIES")
standalone_keywords = {
    "login_auth": ["login", "auth", "session", "qrcode", "keepalive", "token", "slider"],
    "upload": ["upload", "attachment", "sl_upload", "uploadfile"],
    "cdp": ["cdp"],
    "crypto": ["crypto", "encrypt"],
    "monitor": ["mitm", "capture", "replay"],
    "api_server": ["server.py", "api/server"],
    "entry": ["entry", "icpsp_entry"],
    "notification": ["notifier", "notify"],
    "pacing": ["pacing", "human_pacing"],
    "asset": ["asset", "node_asset"],
    "checkpoint": ["checkpoint"],
    "intelligence": ["intelligence"],
}

for path, info in sorted(files.items()):
    size = info["size"]
    if size < 300:
        continue
    eps = info["endpoints"]
    defs = info["defs"]
    # Check if this file has unique capabilities
    unique_eps = eps - pipeline_apis
    has_unique = bool(unique_eps)
    is_standalone = any(kw in path.lower() for kws in standalone_keywords.values() for kw in kws)
    is_helper = path.endswith(('_grab_session.py', '_check_browser.py', '_diag_complement.py',
                               '_cleanup_tmp.py', '_phase2_1151_check_state.py',
                               '_phase2_1151_force_reload.py', '_phase2_1151_open_fresh.py',
                               '_phase2_bo_diagnose.py', '_phase2_bo_navigate_1151.py',
                               '_phase2_bo_reload.py'))
    is_core = path.startswith('system/core/') or path.startswith('system/orchestrator/')
    
    if has_unique or is_standalone or is_helper:
        cat = "unknown"
        for cname, kws in standalone_keywords.items():
            if any(kw in path.lower() for kw in kws):
                cat = cname
                break
        if is_core:
            cat = "core_framework"
        if is_helper:
            cat = "helper_script"
        
        print(f"\n   [{cat}] {path} ({size}B)")
        if unique_eps:
            print(f"     Unique APIs: {sorted(unique_eps)}")
        key_defs = [d for d in defs if not d.startswith('_') and len(d) > 5]
        if key_defs:
            print(f"     Key functions: {key_defs[:10]}")

# 3. Phase1 driver capabilities
print(f"\n3. PHASE1 PROTOCOL DRIVER — step functions")
if 'system/phase1_protocol_driver.py' in files:
    p1_defs = files['system/phase1_protocol_driver.py']["defs"]
    step_defs = [d for d in p1_defs if 'step' in d.lower() or 'name' in d.lower()]
    print(f"   Step functions: {step_defs}")

# 4. Upload capability analysis
print(f"\n4. UPLOAD CAPABILITY (SlUploadMaterial step21)")
upload_files = [p for p in files if 'upload' in p.lower() or 'attachment' in p.lower()]
for p in upload_files:
    if '_archive' not in p:
        print(f"   {p} ({files[p]['size']}B)")
        print(f"     APIs: {sorted(files[p]['endpoints'])}")
        key_defs = [d for d in files[p]['defs'] if not d.startswith('_')]
        if key_defs:
            print(f"     Functions: {key_defs[:8]}")

# 5. Login capability
print(f"\n5. LOGIN/AUTH CAPABILITY")
login_files = [p for p in files if any(k in p.lower() for k in ['login', 'auth', 'qrcode'])]
for p in login_files:
    if '_archive' not in p:
        print(f"   {p} ({files[p]['size']}B)")
        print(f"     APIs: {sorted(files[p]['endpoints'])}")
        key_defs = [d for d in files[p]['defs'] if not d.startswith('_')]
        if key_defs:
            print(f"     Functions: {key_defs[:8]}")

# 6. CDP capability
print(f"\n6. CDP/BROWSER AUTOMATION CAPABILITY")
cdp_files = [p for p in files if 'cdp' in p.lower()]
for p in cdp_files:
    if '_archive' not in p:
        print(f"   {p} ({files[p]['size']}B)")
        key_defs = [d for d in files[p]['defs'] if not d.startswith('_')]
        if key_defs:
            print(f"     Functions: {key_defs[:10]}")

# 7. Summary: what's missing from the pipeline
print(f"\n{'='*70}")
print(f"  SUMMARY: GAPS IN PIPELINE")
print(f"{'='*70}")
gaps = []
# Check login
has_login = any('login' in p for p in files if '_archive' not in p and 'auth' in p)
gaps.append(("Login (QR code scan)", "login_qrcode.py exists but not integrated as auto-fallback"))
gaps.append(("Session keepalive", "auth_keepalive_service.py exists but not integrated"))
gaps.append(("Upload (pure protocol)", "step21 uses CDP for upload; pure HTTP upload not integrated"))
gaps.append(("producePdf", "API exists but always returns A0002; not working"))
gaps.append(("Submit (final)", "submit API exists but not in pipeline (stops at PreSubmitSuccess)"))
gaps.append(("Name release", "No protocol for releasing occupied names after cleanup"))
gaps.append(("1151 full validation", "1151 path has 28 steps but never end-to-end tested"))
gaps.append(("CDP fallback", "cdp_ybb_select.py exists but not wired into pipeline"))
gaps.append(("Benefit users (1151)", "cdp_benefit_users.py exists for 1151 step19 but may not be in protocol driver"))
gaps.append(("Error recovery", "No auto-retry or smart recovery for transient errors"))
gaps.append(("Multi-case batch", "No batch mode for running multiple cases"))

for name, desc in gaps:
    print(f"   ❌ {name}")
    print(f"      {desc}")
