#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Antigravity chat + silent send test via CDP."""

import json
import time
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
print("CDP Pages: %d" % len(pages))
for p in pages:
    if p.get("type") == "page":
        print("  %s - %s" % (p.get("type", "?"), p.get("title", "")[:80]))

# Find the main Antigravity page (not Launchpad)
page = None
for p in pages:
    if p.get("type") == "page" and "2046" in p.get("title", ""):
        page = p
        break
if not page:
    for p in pages:
        if p.get("type") == "page" and "Antigravity" in p.get("title", ""):
            page = p
            break
if not page:
    page = [p for p in pages if p.get("type") == "page"][0]

print("\nConnected: %s" % page.get("title", ""))
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
        '[class*="conversation"], [class*="message"], [class*="answering"], ' +
        '[class*="chat-input"], [class*="user-chat"], [class*="ai-chat"]'
    );
    var chatSamples = [];
    for (var i = 0; i < Math.min(chatEls.length, 30); i++) {
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
for e in value.get("chatSamples", [])[:20]:
    print("  %s cls=%s" % (e["tag"], e["cls"][:80]))
    if e["text"]:
        print("    text: %s" % e["text"][:80])

# === 2. Read Messages ===
# Try multiple selectors (Windsurf/Cursor/Trae patterns)
js_read = """
(function() {
    var msgs = [];
    
    // Try Windsurf pattern: panel-border
    var panels = document.querySelectorAll('[class*="panel-border"]');
    if (panels.length > 0) {
        for (var i = 0; i < panels.length; i++) {
            var text = panels[i].textContent.trim();
            if (text) msgs.push({source: 'panel-border', text: text.substring(0, 150)});
        }
        return msgs;
    }
    
    // Try Cursor pattern: composer-human-message
    var humanMsgs = document.querySelectorAll('[class*="composer-human-message"]');
    var aiMsgs = document.querySelectorAll('[class*="composer-rendered-message"]');
    if (humanMsgs.length > 0 || aiMsgs.length > 0) {
        var pairs = document.querySelectorAll('[class*="composer-human-ai-pair"]');
        for (var i = 0; i < pairs.length; i++) {
            var human = pairs[i].querySelector('[class*="composer-human-message"]');
            var ai = pairs[i].querySelector('[class*="composer-rendered-message"]:not([class*="human"])');
            msgs.push({
                source: 'composer',
                human: human ? human.textContent.trim().substring(0, 150) : '',
                ai: ai ? ai.textContent.trim().substring(0, 150) : ''
            });
        }
        return msgs;
    }
    
    // Try Trae pattern: chat-turn
    var turns = document.querySelectorAll('section[class*="chat-turn"]');
    if (turns.length > 0) {
        for (var i = 0; i < turns.length; i++) {
            var cls = turns[i].className || '';
            var isUser = cls.includes('user');
            var text = turns[i].textContent.trim();
            msgs.push({source: 'chat-turn', role: isUser ? 'USER' : 'AI', text: text.substring(0, 150)});
        }
        return msgs;
    }
    
    return {source: 'none', count: msgs.length};
})()
"""

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
result = json.loads(ws.recv())
msgs = result.get("result", {}).get("result", {}).get("value", {})

print("\n=== Antigravity Chat Messages ===")
if isinstance(msgs, list):
    print("Messages: %d" % len(msgs))
    for i, m in enumerate(msgs[:15]):
        if m.get("source") == "composer":
            print("[%d] USER: %s" % (i, m.get("human", "")[:100]))
            print("[%d] AI:   %s" % (i, m.get("ai", "")[:100]))
        else:
            role = m.get("role", "")
            text = m.get("text", "")
            print("[%d] %s%s" % (i, (role + ": ") if role else "", text[:100]))
elif isinstance(msgs, dict):
    print("Result: %s" % json.dumps(msgs, ensure_ascii=False)[:300])

# === 3. Silent Send ===
print("\n" + "=" * 60)
print("  Silent Send Test")
print("=" * 60)

message = "CDP静默发送测试-Antigravity成功"

# Find input box
js_focus = """
(function() {
    var input = document.querySelector('.aislash-editor-input')
        || document.querySelector('.chat-input-v2-input-box-editable')
        || document.querySelector('[contenteditable="true"][class*="min-h"]');
    if (!input) {
        var editables = document.querySelectorAll('[contenteditable="true"]');
        if (editables.length > 0) input = editables[0];
    }
    if (!input) return {found: false, editableCount: document.querySelectorAll('[contenteditable="true"]').length};
    input.focus();
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(input);
    sel.removeAllRanges();
    sel.addRange(range);
    return {found: true, cls: (input.className||'').substring(0,80)};
})()
"""

ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": js_focus, "returnByValue": True}}))
result = json.loads(ws.recv())
focus_val = result.get("result", {}).get("result", {}).get("value", {})
print("Focus: %s" % json.dumps(focus_val, ensure_ascii=False))

if not focus_val.get("found"):
    print("Input not found! Editable count: %d" % focus_val.get("editableCount", 0))
    ws.close()
    exit()

# Insert text
escaped = message.replace("\\", "\\\\").replace("'", "\\'")
js_insert = """
(function() {
    var input = document.querySelector('.aislash-editor-input')
        || document.querySelector('.chat-input-v2-input-box-editable')
        || document.querySelector('[contenteditable="true"][class*="min-h"]')
        || document.querySelectorAll('[contenteditable="true"]')[0];
    if (!input) return {success: false};
    input.focus();
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(input);
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand('delete');
    var result = document.execCommand('insertText', false, '%s');
    return {success: result, text: input.textContent.substring(0, 60)};
})()
""" % escaped

ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": js_insert, "returnByValue": True}}))
result = json.loads(ws.recv())
insert_val = result.get("result", {}).get("result", {}).get("value", {})
print("Insert: %s" % json.dumps(insert_val, ensure_ascii=False))

time.sleep(0.5)

# Try CDP Input Enter first
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

time.sleep(2)

# Check if input was cleared
js_check = """
(function() {
    var input = document.querySelector('.aislash-editor-input')
        || document.querySelector('.chat-input-v2-input-box-editable')
        || document.querySelector('[contenteditable="true"][class*="min-h"]')
        || document.querySelectorAll('[contenteditable="true"]')[0];
    return {inputText: input ? input.textContent.trim() : 'no input', inputEmpty: input ? input.textContent.trim().length === 0 : false};
})()
"""

ws.send(json.dumps({"id": 7, "method": "Runtime.evaluate", "params": {"expression": js_check, "returnByValue": True}}))
result = json.loads(ws.recv())
check = result.get("result", {}).get("result", {}).get("value", {})
print("After CDP Enter: %s" % json.dumps(check, ensure_ascii=False))

if not check.get("inputEmpty"):
    # Try DOM Enter (like Trae)
    print("CDP Enter didn't submit, trying DOM KeyboardEvent...")
    js_dom_enter = """
    (function() {
        var input = document.querySelector('.aislash-editor-input')
            || document.querySelector('.chat-input-v2-input-box-editable')
            || document.querySelector('[contenteditable="true"][class*="min-h"]')
            || document.querySelectorAll('[contenteditable="true"]')[0];
        if (!input) return {done: false};
        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        return {done: true};
    })()
    """
    ws.send(json.dumps({"id": 8, "method": "Runtime.evaluate", "params": {"expression": js_dom_enter, "returnByValue": True}}))
    result = json.loads(ws.recv())
    print("DOM Enter: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {}), ensure_ascii=False))
    time.sleep(3)

# Final verify
js_verify = """
(function() {
    var all = document.querySelectorAll('[class*="panel-border"], [class*="composer-human-message"], [class*="user-chat-bubble"], [class*="chat-turn"]');
    for (var i = 0; i < all.length; i++) {
        if (all[i].textContent.includes('CDP') && all[i].textContent.includes('Antigravity')) {
            return {found: true, text: all[i].textContent.substring(0, 100), cls: (all[i].className||'').substring(0,60)};
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
    print("\n>>> CDP SILENT SEND TO ANTIGRAVITY: SUCCESS! <<<")
else:
    print("\nMessage not confirmed in chat yet")

ws.close()
