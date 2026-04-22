#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump Antigravity chat HTML structure to understand message rendering."""

import json
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Get the full HTML of the chat area
js_html = """
(function() {
    var chatArea = document.querySelector('[class*="text-ide-message-block-bot-color"]');
    if (!chatArea) return {error: 'no chat area'};
    return {html: chatArea.innerHTML.substring(0, 5000)};
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_html, "returnByValue": True}}))
result = json.loads(ws.recv())
html = result.get("result", {}).get("result", {}).get("value", {}).get("html", "")
print(html)

ws.close()
