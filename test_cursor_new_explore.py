#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Explore new Cursor version DOM structure via CDP."""

import json
import time
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
print("Pages: %d" % len(pages))
for p in pages:
    if p.get("type") == "page":
        print("  %s - %s" % (p.get("type", "?"), p.get("title", "")[:80]))

page = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Explore DOM structure
js_explore = """
(function() {
    var editables = document.querySelectorAll('[contenteditable="true"]');
    var editableInfo = [];
    for (var i = 0; i < editables.length; i++) {
        var e = editables[i];
        editableInfo.push({
            tag: e.tagName,
            cls: (e.className || '').substring(0, 100),
            text: (e.textContent || '').substring(0, 60),
            placeholder: e.getAttribute('placeholder') || '',
            attrs: (e.getAttribute('data-lexical-editor') || '') + ' ' + (e.getAttribute('role') || '')
        });
    }
    var chatEls = document.querySelectorAll(
        '[class*="composer"], [class*="aislash"], [class*="chat-"], ' +
        '[class*="conversation"], [class*="message"], [class*="answering"], ' +
        '[class*="thread"], [class*="reply"]'
    );
    var chatSamples = [];
    for (var i = 0; i < Math.min(chatEls.length, 35); i++) {
        chatSamples.push({
            tag: chatEls[i].tagName,
            cls: (chatEls[i].className || '').substring(0, 120),
            text: (chatEls[i].textContent || '').substring(0, 120)
        });
    }
    return {editables: editableInfo, chatCount: chatEls.length, chatSamples: chatSamples, title: document.title};
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_explore, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nTitle: %s" % value.get("title", ""))
print("\nContenteditable: %d" % len(value.get("editables", [])))
for e in value.get("editables", [])[:8]:
    print("  %s cls=%s" % (e["tag"], e["cls"][:80]))
    print("    text=%s placeholder=%s attrs=%s" % (e["text"][:40], e.get("placeholder", ""), e.get("attrs", "")))

print("\nChat elements: %d" % value.get("chatCount", 0))
for e in value.get("chatSamples", [])[:25]:
    print("  %s cls=%s" % (e["tag"], e["cls"][:100]))
    if e["text"]:
        print("    text: %s" % e["text"][:100])

ws.close()
