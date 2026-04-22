#!/usr/bin/env python
import json, requests
pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
for p in pages:
    if p.get("type") == "page":
        print(f"{p.get('url','')[:100]}")
