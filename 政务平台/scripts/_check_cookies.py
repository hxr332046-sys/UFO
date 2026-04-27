"""Check if session cookies are still valid."""
import sys, json, pickle
from pathlib import Path

# Check pkl file
pkl_path = Path("packet_lab/out/http_session_cookies.pkl")
if pkl_path.exists():
    with open(pkl_path, "rb") as f:
        cj = pickle.load(f)
    print(f"CookieJar type: {type(cj)}")
    print(f"Cookies count: {len(list(cj))}")
    for c in cj:
        print(f"  {c.name}={c.value[:20]}... domain={c.domain} path={c.path}")
else:
    print("No pkl file found!")

# Check runtime_auth_headers.json
auth_path = Path("packet_lab/out/runtime_auth_headers.json")
if auth_path.exists():
    with open(auth_path, "r", encoding="utf-8") as f:
        auth = json.load(f)
    print(f"\nRuntime auth headers:")
    for k, v in auth.items():
        if k == "Cookie":
            print(f"  {k}: {v[:80]}...")
        else:
            print(f"  {k}: {v}")
