#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Trae chat + silent send test via CDP."""

import json
import time
import requests
import websocket

CDP_PORT = 9224

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# === 1. Explore DOM structure ===
js_explore = """
(function() {
    var editables = document.querySelectorAll('[contenteditable="true"]');
    var editableInfo = [];
    for (var i = 0; i < editables.length; i++) {
        var e = editables[i];
        editableInfo.push({
            tag: e.tagName,
            cls: (e.className || '').substring(0, 80),
            text: (e.textContent || '').substring(0, 60),
            placeholder: e.getAttribute('placeholder') || ''
        });
    }
    var chatEls = document.querySelectorAll(
        '[class*="composer"], [class*="aislash"], [class*="chat-"], ' +
        '[class*="conversation"], [class*="message"], [class*="answering"]'
    );
    var chatSamples = [];
    for (var i = 0; i < Math.min(chatEls.length, 25); i++) {
        chatSamples.push({
            tag: chatEls[i].tagName,
            cls: (chatEls[i].className || '').substring(0, 100),
            text: (chatEls[i].textContent || '').substring(0, 100)
        });
    }
    return {editables: editableInfo, chatCount: chatEls.length, chatSamples: chatSamples};
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_explore, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nContenteditable: %d" % len(value.get("editables", [])))
for e in value.get("editables", [])[:5]:
    print("  %s cls=%s text=%s placeholder=%s" % (e["tag"], e["cls"][:60], e["text"][:40], e.get("placeholder", "")))

print("\nChat elements: %d" % value.get("chatCount", 0))
for e in value.get("chatSamples", [])[:15]:
    print("  %s cls=%s" % (e["tag"], e["cls"][:80]))
    if e["text"]:
        print("    text: %s" % e["text"][:80])

# === 2. Try to read messages ===
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

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
result = json.loads(ws.recv())
msgs = result.get("result", {}).get("result", {}).get("value", [])

print("\n=== Trae Chat Messages (%d) ===" % len(msgs))
for i, m in enumerate(msgs):
    print()
    print("[%d] USER: %s" % (i, m.get("human", "")[:120]))
    print("[%d] AI:   %s" % (i, m.get("ai", "")[:120]))

# === 3. Silent Send ===
print("\n" + "=" * 60)
print("  Silent Send Test")
print("=" * 60)

message = "CDP静默发送测试-Trae成功"

# Find and focus input
js_focus = """
(function() {
    var input = document.querySelector('.aislash-editor-input');
    if (!input) {
        var editables = document.querySelectorAll('[contenteditable="true"]');
        if (editables.length > 0) input = editables[0];
    }
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
    var result = document.execCommand('insertText', false, '%s');
    var input = document.querySelector('.aislash-editor-input') || document.querySelectorAll('[contenteditable="true"]')[0];
    return {success: result, text: input ? input.textContent.substring(0, 60) : 'none'};
})()
""" % escaped

ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": js_insert, "returnByValue": True}}))
result = json.loads(ws.recv())
insert_val = result.get("result", {}).get("result", {}).get("value", {})
print("Insert: %s" % json.dumps(insert_val, ensure_ascii=False))

time.sleep(0.3)

# Send Enter
print("Sending Enter via CDP Input...")
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
print("Enter sent!")

# Verify
time.sleep(3)
js_verify = """
(function() {
    var all = document.querySelectorAll('[class*="composer-human-message"], [class*="human-message"]');
    for (var i = 0; i < all.length; i++) {
        if (all[i].textContent.includes('CDP') && all[i].textContent.includes('Trae')) {
            return {found: true, text: all[i].textContent.substring(0, 80)};
        }
    }
    return {found: false};
})()
"""

ws.send(json.dumps({"id": 7, "method": "Runtime.evaluate", "params": {"expression": js_verify, "returnByValue": True}}))
result = json.loads(ws.recv())
verify = result.get("result", {}).get("result", {}).get("value", {})
print("\nVerify: %s" % json.dumps(verify, ensure_ascii=False))

if verify.get("found"):
    print("\n>>> CDP SILENT SEND TO TRAE: SUCCESS! <<<")
else:
    print("\nMessage not confirmed in DOM yet")

ws.close()
