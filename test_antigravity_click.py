#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Click on Antigravity conversation to read messages, then verify our sent message."""

import json
import time
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Click on the first conversation "你是什么模型" to expand it
js_click = """
(function() {
    var btns = document.querySelectorAll('button[title]');
    for (var i = 0; i < btns.length; i++) {
        if (btns[i].getAttribute('title') === '你是什么模型') {
            btns.click();
            return {clicked: true, title: btns[i].getAttribute('title')};
        }
    }
    return {clicked: false};
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_click, "returnByValue": True}}))
result = json.loads(ws.recv())
print("Click: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))

time.sleep(2)

# Now read the expanded conversation messages
js_read = """
(function() {
    var chatArea = document.querySelector('[class*="text-ide-message-block-bot-color"]');
    if (!chatArea) return {found: false, reason: 'no chat area'};

    // Get all message blocks - try various patterns
    var allDivs = chatArea.querySelectorAll('div');
    var messages = [];
    var seen = {};

    for (var i = 0; i < allDivs.length; i++) {
        var div = allDivs[i];
        var cls = div.className || '';
        var text = div.textContent.trim();

        // Look for message content divs (prose/markdown rendered)
        if (cls.includes('prose') || cls.includes('markdown') || cls.includes('msg-content')) {
            if (text.length > 5 && !seen[text.substring(0, 30)]) {
                seen[text.substring(0, 30)] = true;
                messages.push({cls: cls.substring(0, 60), text: text.substring(0, 200)});
            }
        }
    }

    // If no prose/markdown found, get all significant text blocks
    if (messages.length === 0) {
        // Get the full chat area text, split by significant blocks
        var fullText = chatArea.textContent;
        return {found: true, fullText: fullText.substring(0, 1000), msgCount: 0};
    }

    return {found: true, msgCount: messages.length, messages: messages};
})()
"""

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nMessages found: %d" % value.get("msgCount", 0))
if value.get("messages"):
    for m in value["messages"][:15]:
        print("  cls=%s" % m["cls"][:50])
        print("  text: %s" % m["text"][:120])
else:
    print("\nFull chat text:")
    print(value.get("fullText", "")[:600])

# Also search for our CDP message in ALL pages
time.sleep(1)
ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {
    "expression": "document.body.textContent.indexOf('CDP') >= 0 ? document.body.textContent.substring(document.body.textContent.indexOf('CDP')-20, document.body.textContent.indexOf('CDP')+60) : 'NOT FOUND'",
    "returnByValue": True
}}))
result = json.loads(ws.recv())
cdp_pos = result.get("result", {}).get("result", {}).get("value", "NOT FOUND")
print("\nCDP in body: %s" % cdp_pos)

ws.close()
