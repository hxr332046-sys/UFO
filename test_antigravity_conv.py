#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check Antigravity conversation list for new message entry."""

import json
import time
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Get ALL conversation buttons and their titles
js_conv = """
(function() {
    var btns = document.querySelectorAll('button[title]');
    var convs = [];
    for (var i = 0; i < btns.length; i++) {
        var title = btns[i].getAttribute('title') || '';
        if (title && title.length > 1 && title.length < 200) {
            convs.push({
                title: title,
                cls: (btns[i].className || '').substring(0, 80),
                text: (btns[i].textContent || '').substring(0, 100)
            });
        }
    }
    return convs;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_conv, "returnByValue": True}}))
result = json.loads(ws.recv())
convs = result.get("result", {}).get("result", {}).get("value", [])

print("Conversations: %d" % len(convs))
for i, c in enumerate(convs):
    print("[%d] title=%s" % (i, c["title"][:80]))
    print("    text=%s" % c["text"][:80])

# Click on the last conversation (likely our new one)
if len(convs) > 0:
    last = convs[-1]
    print("\nClicking last conversation: %s" % last["title"][:60])

    js_click_last = """
    (function() {
        var btns = document.querySelectorAll('button[title="' + arguments[0] + '"]');
        if (btns.length > 0) {
            var rect = btns[0].getBoundingClientRect();
            return {found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2};
        }
        return {found: false};
    })()
    """ % last["title"].replace('"', '\\"')

    # Simpler: just click via JS
    js_js_click = """
    (function() {
        var btns = document.querySelectorAll('button[title]');
        for (var i = btns.length - 1; i >= 0; i--) {
            var title = btns[i].getAttribute('title') || '';
            if (title.length > 1) {
                btns[i].click();
                return {clicked: true, title: title};
            }
        }
        return {clicked: false};
    })()
    """

    ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_js_click, "returnByValue": True}}))
    result = json.loads(ws.recv())
    print("Click result: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))

    time.sleep(3)

    # Now read the expanded chat
    js_read_expanded = """
    (function() {
        var chatArea = document.querySelector('[class*="text-ide-message-block-bot-color"]');
        if (!chatArea) return {found: false};
        return {found: true, text: chatArea.textContent.substring(0, 2000)};
    })()
    """

    ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": js_read_expanded, "returnByValue": True}}))
    result = json.loads(ws.recv())
    value = result.get("result", {}).get("result", {}).get("value", {})
    print("\nExpanded chat text:")
    print(value.get("text", "")[:1000])

ws.close()
