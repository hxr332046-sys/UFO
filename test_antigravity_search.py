#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Search all Antigravity CDP pages for our message."""

import json
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
for p in pages:
    if p.get("type") != "page":
        continue
    print("Checking: %s" % p.get("title", "")[:60])
    try:
        ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=10)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": "document.body.textContent.includes('CDP')",
            "returnByValue": True
        }}))
        result = json.loads(ws.recv())
        found = result.get("result", {}).get("result", {}).get("value", False)
        print("  Has 'CDP': %s" % found)

        if found:
            # Get context around it
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
                "expression": """
                (function() {
                    var idx = document.body.textContent.indexOf('CDP');
                    return document.body.textContent.substring(Math.max(0, idx-20), idx+80);
                })()
                """,
                "returnByValue": True
            }}))
            result2 = json.loads(ws.recv())
            context = result2.get("result", {}).get("result", {}).get("value", "")
            print("  Context: %s" % context)

        ws.close()
    except Exception as e:
        print("  Error: %s" % str(e)[:60])
