#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Cursor chat + silent send test via CDP."""

import json
import time
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# === 1. Read Messages ===
js_read = """
(function() {
    var pairs = document.querySelectorAll('[class*="composer-human-ai-pair"]');
    var msgs = [];
    for (var i = 0; i < pairs.length; i++) {
        var pair = pairs[i];
        var human = pair.querySelector('[class*="composer-human-message"]');
        var aiEls = pair.querySelectorAll('[class*="composer-rendered-message"]');
        var aiText = '';
        for (var j = 0; j < aiEls.length; j++) {
            var cls = aiEls[j].className || '';
            if (!cls.includes('human')) {
                aiText = aiEls[j].textContent.trim();
            }
        }
        var humanText = human ? human.textContent.trim() : '';
        if (humanText || aiText) {
            msgs.push({human: humanText.substring(0, 200), ai: aiText.substring(0, 200)});
        }
    }
    return msgs;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
result = json.loads(ws.recv())
msgs = result.get("result", {}).get("result", {}).get("value", [])

print("\n=== Cursor Chat Messages (%d) ===" % len(msgs))
for i, m in enumerate(msgs):
    print()
    print("[%d] USER: %s" % (i, m.get("human", "")[:120]))
    print("[%d] AI:   %s" % (i, m.get("ai", "")[:120]))

# === 2. Silent Send ===
print("\n" + "=" * 60)
print("  Silent Send Test")
print("=" * 60)

message = "CDP静默发送测试-Cursor成功"

# Focus input
js_focus = """
(function() {
    var input = document.querySelector('.aislash-editor-input');
    if (!input) return {found: false};
    input.focus();
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(input);
    sel.removeAllRanges();
    sel.addRange(range);
    return {found: true, cls: (input.className||'').substring(0,60)};
})()
"""

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_focus, "returnByValue": True}}))
result = json.loads(ws.recv())
focus_val = result.get("result", {}).get("result", {}).get("value", {})
print("Focus: %s" % json.dumps(focus_val, ensure_ascii=False))

if not focus_val.get("found"):
    print("Input not found!")
    ws.close()
    exit()

# Insert text
escaped = message.replace("\\", "\\\\").replace("'", "\\'")
js_insert = """
(function() {
    var result = document.execCommand('insertText', false, '%s');
    var input = document.querySelector('.aislash-editor-input');
    return {success: result, text: input ? input.textContent.substring(0, 60) : 'none'};
})()
""" % escaped

ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": js_insert, "returnByValue": True}}))
result = json.loads(ws.recv())
insert_val = result.get("result", {}).get("result", {}).get("value", {})
print("Insert: %s" % json.dumps(insert_val, ensure_ascii=False))

time.sleep(0.3)

# Send Enter
print("Sending Enter via CDP Input...")
ws.send(json.dumps({"id": 4, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyDown", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()
time.sleep(0.05)
ws.send(json.dumps({"id": 5, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyUp", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()
print("Enter sent!")

# Verify
time.sleep(3)
js_verify = """
(function() {
    var all = document.querySelectorAll('[class*="composer-human-message"]');
    for (var i = 0; i < all.length; i++) {
        if (all[i].textContent.includes('CDP') && all[i].textContent.includes('Cursor')) {
            return {found: true, text: all[i].textContent.substring(0, 80)};
        }
    }
    return {found: false};
})()
"""

ws.send(json.dumps({"id": 6, "method": "Runtime.evaluate", "params": {"expression": js_verify, "returnByValue": True}}))
result = json.loads(ws.recv())
verify = result.get("result", {}).get("result", {}).get("value", {})
print("\nVerify: %s" % json.dumps(verify, ensure_ascii=False))

if verify.get("found"):
    print("\n>>> CDP SILENT SEND TO CURSOR: SUCCESS! <<<")
else:
    print("\nMessage not confirmed in DOM yet")

ws.close()
