#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Antigravity: Click conversation via CDP, read messages, verify sent message."""

import json
import time
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Step 1: Get the position of the conversation button to click it via CDP Input
js_get_pos = """
(function() {
    var btns = document.querySelectorAll('button[title]');
    for (var i = 0; i < btns.length; i++) {
        if (btns[i].getAttribute('title') === '\u4f60\u662f\u4ec0\u4e48\u6a21\u578b') {
            var rect = btns[i].getBoundingClientRect();
            return {found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2, w: rect.width, h: rect.height};
        }
    }
    return {found: false};
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_get_pos, "returnByValue": True}}))
result = json.loads(ws.recv())
pos = result.get("result", {}).get("result", {}).get("value", {})
print("Button position: %s" % json.dumps(pos))

if pos.get("found"):
    # Click via CDP Input (mouse events)
    x, y = pos["x"], pos["y"]
    print("Clicking at (%d, %d) via CDP Input..." % (x, y))

    ws.send(json.dumps({"id": 2, "method": "Input.dispatchMouseEvent", "params": {
        "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
    }}))
    ws.recv()
    time.sleep(0.05)
    ws.send(json.dumps({"id": 3, "method": "Input.dispatchMouseEvent", "params": {
        "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
    }}))
    ws.recv()
    print("Clicked!")

    time.sleep(2)

    # Step 2: Read the expanded conversation
    js_read = """
    (function() {
        var chatArea = document.querySelector('[class*="text-ide-message-block-bot-color"]');
        if (!chatArea) return {found: false};
        var fullText = chatArea.textContent;
        return {found: true, fullText: fullText.substring(0, 1500)};
    })()
    """

    ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
    result = json.loads(ws.recv())
    value = result.get("result", {}).get("result", {}).get("value", {})
    print("\nChat text after click:")
    print(value.get("fullText", "")[:800])

    # Step 3: Search for our CDP message
    ws.send(json.dumps({"id": 5, "method": "Runtime.evaluate", "params": {
        "expression": "document.body.textContent.indexOf('CDP') >= 0",
        "returnByValue": True
    }}))
    result = json.loads(ws.recv())
    found = result.get("result", {}).get("result", {}).get("value", False)
    print("\nCDP message in body: %s" % found)

else:
    print("Button not found")

ws.close()
