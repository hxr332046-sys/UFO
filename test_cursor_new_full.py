#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""New Cursor version: read conversations + silent send via CDP."""

import json
import time
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# === 1. Read conversation list ===
js_read_list = """
(function() {
    var btns = document.querySelectorAll('[class*="glass-sidebar-agent-menu-btn"]');
    var convs = [];
    for (var i = 0; i < btns.length; i++) {
        convs.push(btns[i].textContent.trim().substring(0, 80));
    }
    return convs;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_read_list, "returnByValue": True}}))
result = json.loads(ws.recv())
convs = result.get("result", {}).get("result", {}).get("value", [])
print("\nConversations: %d" % len(convs))
for i, c in enumerate(convs):
    print("  [%d] %s" % (i, c))

# === 2. Click first conversation to open it ===
js_click_conv = """
(function() {
    var btns = document.querySelectorAll('[class*="glass-sidebar-agent-menu-btn"]');
    if (btns.length > 0) {
        var rect = btns[0].getBoundingClientRect();
        btns[0].click();
        return {clicked: true, title: btns[0].textContent.trim().substring(0, 60), x: rect.x, y: rect.y};
    }
    return {clicked: false};
})()
"""

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_click_conv, "returnByValue": True}}))
result = json.loads(ws.recv())
click_val = result.get("result", {}).get("result", {}).get("value", {})
print("\nClick conversation: %s" % json.dumps(click_val, ensure_ascii=False))

time.sleep(2)

# === 3. Read messages in opened conversation ===
js_read_msgs = """
(function() {
    var result = {};
    
    // Search for message content elements
    var allEls = document.querySelectorAll('div, section, p, span');
    var msgs = [];
    var seen = {};
    for (var i = 0; i < allEls.length; i++) {
        var el = allEls[i];
        var cls = el.className || '';
        var text = el.textContent.trim();
        
        // Look for message-like elements
        if ((cls.includes('message') || cls.includes('thread') || cls.includes('response') ||
             cls.includes('turn') || cls.includes('bubble') || cls.includes('prose') ||
             cls.includes('markdown') || cls.includes('agent-message') || cls.includes('human') ||
             cls.includes('bot') || cls.includes('chat')) && text.length > 5 && text.length < 500) {
            var key = text.substring(0, 30);
            if (!seen[key]) {
                seen[key] = true;
                msgs.push({cls: cls.substring(0, 100), text: text.substring(0, 200)});
            }
        }
    }
    result.messages = msgs;
    
    // Get the agent panel content
    var panel = document.querySelector('[class*="agent-panel"]');
    if (panel) {
        result.panelText = panel.textContent.substring(0, 1500);
    }
    
    // Get full body text
    result.bodyPreview = document.body.textContent.substring(0, 1000);
    
    return result;
})()
"""

ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": js_read_msgs, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nMessage-like elements: %d" % len(value.get("messages", [])))
for m in value.get("messages", [])[:15]:
    print("  cls=%s" % m["cls"][:60])
    print("    text: %s" % m["text"][:120])

print("\nAgent panel text:")
print(value.get("panelText", "")[:500])

# === 4. Silent Send ===
print("\n" + "=" * 60)
print("  Silent Send Test (TipTap/ProseMirror)")
print("=" * 60)

message = "CDP静默发送测试-新Cursor版本"

# Focus TipTap/ProseMirror input
js_focus = """
(function() {
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    if (!input) return {found: false};
    input.focus();
    return {found: true, cls: (input.className||'').substring(0,80)};
})()
"""

ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": js_focus, "returnByValue": True}}))
result = json.loads(ws.recv())
focus_val = result.get("result", {}).get("result", {}).get("value", {})
print("Focus: %s" % json.dumps(focus_val, ensure_ascii=False))

if not focus_val.get("found"):
    print("Input not found!")
    ws.close()
    exit()

# Insert text via execCommand
escaped = message.replace("\\", "\\\\").replace("'", "\\'")
js_insert = """
(function() {
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    if (!input) return {success: false};
    input.focus();
    // Select all and delete first
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(input);
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand('delete');
    // Insert
    var result = document.execCommand('insertText', false, '%s');
    return {success: result, text: input.textContent.substring(0, 60)};
})()
""" % escaped

ws.send(json.dumps({"id": 5, "method": "Runtime.evaluate", "params": {"expression": js_insert, "returnByValue": True}}))
result = json.loads(ws.recv())
insert_val = result.get("result", {}).get("result", {}).get("value", {})
print("Insert: %s" % json.dumps(insert_val, ensure_ascii=False))

time.sleep(0.5)

# Try CDP Input Enter
print("Sending Enter via CDP Input...")
ws.send(json.dumps({"id": 6, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyDown", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()
time.sleep(0.05)
ws.send(json.dumps({"id": 7, "method": "Input.dispatchKeyEvent", "params": {
    "type": "keyUp", "key": "Enter", "code": "Enter",
    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
}}))
ws.recv()

time.sleep(2)

# Check input state
js_check = """
(function() {
    var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
    return {inputText: input ? input.textContent.trim() : 'none', inputEmpty: input ? input.textContent.trim().length === 0 : false};
})()
"""

ws.send(json.dumps({"id": 8, "method": "Runtime.evaluate", "params": {"expression": js_check, "returnByValue": True}}))
result = json.loads(ws.recv())
check = result.get("result", {}).get("result", {}).get("value", {})
print("After CDP Enter: %s" % json.dumps(check, ensure_ascii=False))

if not check.get("inputEmpty"):
    # Try DOM Enter (Trae pattern)
    print("CDP Enter didn't submit, trying DOM KeyboardEvent...")
    js_dom_enter = """
    (function() {
        var input = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
        if (!input) return {done: false};
        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        return {done: true};
    })()
    """
    ws.send(json.dumps({"id": 9, "method": "Runtime.evaluate", "params": {"expression": js_dom_enter, "returnByValue": True}}))
    result = json.loads(ws.recv())
    print("DOM Enter: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))
    time.sleep(3)

    # Re-check
    ws.send(json.dumps({"id": 10, "method": "Runtime.evaluate", "params": {"expression": js_check, "returnByValue": True}}))
    result = json.loads(ws.recv())
    check2 = result.get("result", {}).get("result", {}).get("value", {})
    print("After DOM Enter: %s" % json.dumps(check2, ensure_ascii=False))

# Final verify - search body for our message
time.sleep(2)
js_verify = """
(function() {
    var body = document.body.textContent;
    var found = body.indexOf('CDP') >= 0 && body.indexOf('Cursor') >= 0;
    if (found) {
        var idx = body.indexOf('CDP');
        return {found: true, context: body.substring(Math.max(0, idx-20), idx+80)};
    }
    return {found: false};
})()
"""

ws.send(json.dumps({"id": 11, "method": "Runtime.evaluate", "params": {"expression": js_verify, "returnByValue": True}}))
result = json.loads(ws.recv())
verify = result.get("result", {}).get("result", {}).get("value", {})
print("\nFinal verify: %s" % json.dumps(verify, ensure_ascii=False))

if verify.get("found") or check.get("inputEmpty"):
    print("\n>>> CDP SILENT SEND TO NEW CURSOR: SUCCESS! <<<")
else:
    print("\nMessage send status unclear")

ws.close()
