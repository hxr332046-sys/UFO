#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Explore Cursor DOM structure via CDP."""

import json
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
print("Pages:")
for p in pages:
    print("  type=%s title=%s" % (p.get("type", "?"), p.get("title", "")[:80]))

page = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

js = """
(function() {
    var results = {};
    var editables = document.querySelectorAll('[contenteditable="true"]');
    results.editables = [];
    for (var i = 0; i < editables.length; i++) {
        results.editables.push({
            tag: editables[i].tagName,
            cls: (editables[i].className || '').substring(0, 80),
            text: (editables[i].textContent || '').substring(0, 60)
        });
    }
    var chatEls = document.querySelectorAll(
        '[class*="composer"], [class*="aislash"], [class*="chat-"], [class*="conversation"], [class*="message"]'
    );
    results.chatCount = chatEls.length;
    results.chatSamples = [];
    for (var i = 0; i < Math.min(chatEls.length, 25); i++) {
        results.chatSamples.push({
            tag: chatEls[i].tagName,
            cls: (chatEls[i].className || '').substring(0, 100),
            text: (chatEls[i].textContent || '').substring(0, 100)
        });
    }
    return results;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nContenteditable: %d" % len(value.get("editables", [])))
for e in value.get("editables", [])[:5]:
    print("  %s cls=%s text=%s" % (e["tag"], e["cls"][:60], e["text"][:40]))

print("\nChat elements: %d" % value.get("chatCount", 0))
for e in value.get("chatSamples", [])[:20]:
    print("  %s cls=%s" % (e["tag"], e["cls"][:80]))
    if e["text"]:
        print("    text: %s" % e["text"][:80])

ws.close()
