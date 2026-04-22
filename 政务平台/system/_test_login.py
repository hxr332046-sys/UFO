"""Test CDP browser availability and attempt auto-login."""
import json, requests, sys

# Step 1: Check CDP
port = 9225
try:
    pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
    print(f"CDP tabs: {len(pages)}")
    for p in pages[:5]:
        print(f"  {p.get('type')}: {p.get('url', '')[:100]}")
except Exception as e:
    print(f"ERROR: CDP not available on port {port}: {e}")
    print("Please start the browser first!")
    sys.exit(2)
