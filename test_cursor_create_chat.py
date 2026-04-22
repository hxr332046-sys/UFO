#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create new Cursor conversation via CDP and send a message to it."""

import json
import time
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# === 1. Click "New Agent" button via CDP Input (mouse) ===
print("Step 1: Click 'New Agent' button...")

# Get exact position
js_get_pos = """
(function() {
    var btn = document.querySelector('.glass-sidebar-agent-menu-btn');
    // Find the "New Agent" text in sidebar
    var allBtns = document.querySelectorAll('button, [role="button"]');
    for (var i = 0; i < allBtns.length; i++) {
        var text = (allBtns[i].textContent || '').trim();
        var aria = allBtns[i].getAttribute('aria-label') || '';
        if (text.match(/^New Agent/) || aria === 'New Agent') {
            var rect = allBtns[i].getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                return {found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2, text: text, aria: aria};
            }
        }
    }
    return {found: false};
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_get_pos, "returnByValue": True}}))
result = json.loads(ws.recv())
pos = result.get("result", {}).get("result", {}).get("value", {})
print("  Button: %s" % json.dumps(pos, ensure_ascii=False))

if pos.get("found"):
    x, y = pos["x"], pos["y"]
    # CDP mouse click
    ws.send(json.dumps({"id": 2, "method": "Input.dispatchMouseEvent", "params": {
        "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
    }}))
    ws.recv()
    time.sleep(0.05)
    ws.send(json.dumps({"id": 3, "method": "Input.dispatchMouseEvent", "params": {
        "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
    }}))
    ws.recv()
    print("  Clicked at (%d, %d)" % (x, y))
else:
    # Fallback: try JS click
    print("  Trying JS click...")
    js_js_click = """
    (function() {
        var allBtns = document.querySelectorAll('button, [role="button"]');
        for (var i = 0; i < allBtns.length; i++) {
            var aria = allBtns[i].getAttribute('aria-label') || '';
            if (aria === 'New Agent') {
                allBtns[i].click();
                return {clicked: true};
            }
        }
        return {clicked: false};
    })()
    """
    ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_js_click, "returnByValue": True}}))
    result = json.loads(ws.recv())
    print("  JS click: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))

time.sleep(2)

# === 2. Check if new conversation was created ===
js_check_new = """
(function() {
    var panel = document.querySelector('[class*="agent-panel"]');
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    return {
        panelText: panel ? panel.textContent.substring(0, 200) : 'none',
        inputFound: !!input,
        inputText: input ? input.textContent.trim() : 'none',
        inputCls: input ? (input.className || '').substring(0, 80) : 'none'
    };
})()
"""

ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": js_check_new, "returnByValue": True}}))
result = json.loads(ws.recv())
check = result.get("result", {}).get("result", {}).get("value", {})
print("\nStep 2: After click - %s" % json.dumps(check, ensure_ascii=False))

# === 3. Send message to new conversation ===
print("\nStep 3: Send message to new conversation...")

message = "CDP新建对话并发送测试-成功"

# Focus input
js_focus = """
(function() {
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    if (!input) return {found: false};
    input.focus();
    return {found: true};
})()
"""

ws.send(json.dumps({"id": 5, "method": "Runtime.evaluate", "params": {"expression": js_focus, "returnByValue": True}}))
result = json.loads(ws.recv())
print("  Focus: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))

# Insert text
escaped = message.replace("\\", "\\\\").replace("'", "\\'")
js_insert = """
(function() {
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    if (!input) return {success: false};
    input.focus();
    var result = document.execCommand('insertText', false, '%s');
    return {success: result, text: input.textContent.substring(0, 60)};
})()
""" % escaped

ws.send(json.dumps({"id": 6, "method": "Runtime.evaluate", "params": {"expression": js_insert, "returnByValue": True}}))
result = json.loads(ws.recv())
insert_val = result.get("result", {}).get("result", {}).get("value", {})
print("  Insert: %s" % json.dumps(insert_val, ensure_ascii=False))

time.sleep(0.5)

# Send Enter
ws.send(json.dumps({"id": 7, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyDown", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()
time.sleep(0.05)
ws.send(json.dumps({"id": 8, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyUp", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()
print("  Enter sent!")

time.sleep(3)

# === 4. Verify ===
js_verify = """
(function() {
    var body = document.body.textContent;
    var found = body.indexOf('CDP') >= 0 && body.indexOf('新建对话');
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    var inputEmpty = input ? input.textContent.trim().length === 0 : false;
    return {foundInBody: found, inputEmpty: inputEmpty};
})()
"""

ws.send(json.dumps({"id": 9, "method": "Runtime.evaluate", "params": {"expression": js_verify, "returnByValue": True}}))
result = json.loads(ws.recv())
verify = result.get("result", {}).get("result", {}).get("value", {})
print("\nStep 4: Verify - %s" % json.dumps(verify, ensure_ascii=False))

if verify.get("inputEmpty"):
    print("\n>>> CDP CREATE NEW CHAT + SEND: SUCCESS! <<<")
else:
    print("\nNew chat creation may need different approach")

ws.close()
