#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Trae chat + silent send v2 - adapted for Trae's unique DOM structure."""

import json
import time
import requests
import websocket

CDP_PORT = 9224

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# === 1. Read Messages (Trae-specific selectors) ===
js_read = """
(function() {
    var turns = document.querySelectorAll('section[class*="chat-turn"]');
    var msgs = [];
    for (var i = 0; i < turns.length; i++) {
        var turn = turns[i];
        var cls = turn.className || '';
        var isUser = cls.includes('user');
        var bubble = turn.querySelector('[class*="user-chat-bubble-request__content-wrapper"]')
            || turn.querySelector('[class*="user-chat-bubble"]')
            || turn.querySelector('[class*="ai-chat-bubble"]')
            || turn.querySelector('[class*="bot-chat"]');
        var text = bubble ? bubble.textContent.trim() : turn.textContent.trim();
        if (text && text.length > 0) {
            msgs.push({role: isUser ? 'USER' : 'AI', text: text.substring(0, 200)});
        }
    }
    return msgs;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
result = json.loads(ws.recv())
msgs = result.get("result", {}).get("result", {}).get("value", [])

print("\n=== Trae Chat Messages (%d) ===" % len(msgs))
for i, m in enumerate(msgs):
    print("[%d] %s: %s" % (i, m["role"], m["text"][:120]))

# === 2. Check current input box state ===
js_check_input = """
(function() {
    var input = document.querySelector('.chat-input-v2-input-box-editable');
    if (!input) return {found: false};
    return {
        found: true,
        tag: input.tagName,
        cls: (input.className || '').substring(0, 80),
        text: (input.textContent || '').substring(0, 60),
        childCount: input.childNodes.length
    };
})()
"""

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_check_input, "returnByValue": True}}))
result = json.loads(ws.recv())
input_info = result.get("result", {}).get("result", {}).get("value", {})
print("\nInput box: %s" % json.dumps(input_info, ensure_ascii=False))

# === 3. Silent Send ===
print("\n" + "=" * 60)
print("  Silent Send Test v2")
print("=" * 60)

message = "CDP静默发送测试-Trae成功"

# Focus and clear input
js_focus = """
(function() {
    var input = document.querySelector('.chat-input-v2-input-box-editable');
    if (!input) return {found: false};
    input.focus();
    // Select all content
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(input);
    sel.removeAllRanges();
    sel.addRange(range);
    return {found: true, cls: (input.className||'').substring(0,60)};
})()
"""

ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": js_focus, "returnByValue": True}}))
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
    var input = document.querySelector('.chat-input-v2-input-box-editable');
    if (!input) return {success: false, error: 'no input'};
    input.focus();
    // Clear first
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(input);
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand('delete');
    // Now insert
    var result = document.execCommand('insertText', false, '%s');
    return {success: result, text: input.textContent.substring(0, 60)};
})()
""" % escaped

ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": js_insert, "returnByValue": True}}))
result = json.loads(ws.recv())
insert_val = result.get("result", {}).get("result", {}).get("value", {})
print("Insert: %s" % json.dumps(insert_val, ensure_ascii=False))

time.sleep(0.5)

# Try multiple submit methods
# Method 1: CDP Input.dispatchKeyEvent Enter
print("Method 1: CDP Input Enter...")
ws.send(json.dumps({"id": 5, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyDown", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()
time.sleep(0.05)
ws.send(json.dumps({"id": 6, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyUp", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()

time.sleep(3)

# Check if message was sent (input should be empty now)
js_check_sent = """
(function() {
    var input = document.querySelector('.chat-input-v2-input-box-editable');
    var inputText = input ? input.textContent.trim() : '';
    return {inputText: inputText, inputEmpty: inputText.length === 0};
})()
"""

ws.send(json.dumps({"id": 7, "method": "Runtime.evaluate", "params": {"expression": js_check_sent, "returnByValue": True}}))
result = json.loads(ws.recv())
sent_check = result.get("result", {}).get("result", {}).get("value", {})
print("After Enter - Input state: %s" % json.dumps(sent_check, ensure_ascii=False))

if sent_check.get("inputEmpty"):
    print("Input cleared - message likely sent!")
else:
    print("Input not cleared - Enter may not have triggered submit")
    # Method 2: Try DOM Enter event
    print("Method 2: DOM KeyboardEvent Enter...")
    js_dom_enter = """
    (function() {
        var input = document.querySelector('.chat-input-v2-input-box-editable');
        if (!input) return {done: false};
        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        return {done: true};
    })()
    """
    ws.send(json.dumps({"id": 8, "method": "Runtime.evaluate", "params": {"expression": js_dom_enter, "returnByValue": True}}))
    result = json.loads(ws.recv())
    print("DOM Enter result: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))
    time.sleep(3)

# Final verify - check if message appears in chat
js_verify = """
(function() {
    var turns = document.querySelectorAll('section[class*="chat-turn"]');
    for (var i = turns.length - 1; i >= Math.max(0, turns.length - 5); i--) {
        var text = turns[i].textContent || '';
        if (text.includes('CDP') && text.includes('Trae')) {
            return {found: true, text: text.substring(0, 100)};
        }
    }
    return {found: false};
})()
"""

ws.send(json.dumps({"id": 9, "method": "Runtime.evaluate", "params": {"expression": js_verify, "returnByValue": True}}))
result = json.loads(ws.recv())
verify = result.get("result", {}).get("result", {}).get("value", {})
print("\nFinal verify: %s" % json.dumps(verify, ensure_ascii=False))

if verify.get("found"):
    print("\n>>> CDP SILENT SEND TO TRAE: SUCCESS! <<<")
else:
    print("\nMessage not confirmed in chat yet")

ws.close()
