#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify Antigravity message and read chat structure."""

import json
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Search broadly for our message in the entire DOM
js_search = """
(function() {
    var body = document.body;
    var allText = body.textContent;
    var found = allText.includes('CDP') && allText.includes('Antigravity');
    
    // Find the specific element containing our message
    var foundEl = null;
    var walker = document.createTreeWalker(body, NodeFilter.SHOW_ELEMENT);
    while (walker.nextNode()) {
        var el = walker.currentNode;
        var text = el.textContent || '';
        if (text.includes('CDP') && text.includes('Antigravity') && text.length < 200) {
            foundEl = {tag: el.tagName, cls: (el.className||'').substring(0,80), text: text.substring(0,100)};
            break;
        }
    }
    
    // Also get chat message structure - look for message blocks
    var msgBlocks = document.querySelectorAll(
        '[class*="message-block"], [class*="chat-message"], [class*="msg-"], ' +
        '[class*="text-ide-message"]'
    );
    var msgSamples = [];
    for (var i = 0; i < Math.min(msgBlocks.length, 20); i++) {
        msgSamples.push({
            tag: msgBlocks[i].tagName,
            cls: (msgBlocks[i].className || '').substring(0, 100),
            text: (msgBlocks[i].textContent || '').substring(0, 100)
        });
    }
    
    // Get all direct children of the chat container
    var chatContainer = document.querySelector('[class*="text-ide-message-block-bot-color"]');
    var children = [];
    if (chatContainer) {
        for (var i = 0; i < chatContainer.children.length; i++) {
            var child = chatContainer.children[i];
            children.push({
                tag: child.tagName,
                cls: (child.className || '').substring(0, 100),
                text: (child.textContent || '').substring(0, 120)
            });
        }
    }
    
    return {
        foundInBody: found,
        foundElement: foundEl,
        msgBlockCount: msgBlocks.length,
        msgSamples: msgSamples,
        chatChildren: children
    };
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_search, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nMessage in body: %s" % value.get("foundInBody"))
print("Found element: %s" % json.dumps(value.get("foundElement"), ensure_ascii=False))
print("\nMsg blocks: %d" % value.get("msgBlockCount", 0))
for m in value.get("msgSamples", [])[:10]:
    print("  %s cls=%s" % (m["tag"], m["cls"][:60]))
    print("    text: %s" % m["text"][:80])

print("\nChat container children: %d" % len(value.get("chatChildren", [])))
for c in value.get("chatChildren", []):
    print("  %s cls=%s" % (c["tag"], c["cls"][:80]))
    print("    text: %s" % c["text"][:100])

ws.close()
