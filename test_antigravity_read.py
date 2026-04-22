#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Antigravity active conversation messages via CDP."""

import json
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Get the full chat structure - look for active conversation messages
js_read = """
(function() {
    var result = {};
    
    // Find all conversation items in the list
    var convButtons = document.querySelectorAll('button[title]');
    var conversations = [];
    for (var i = 0; i < convButtons.length; i++) {
        var btn = convButtons[i];
        var title = btn.getAttribute('title') || '';
        if (title && title.length > 1 && title.length < 100) {
            conversations.push(title);
        }
    }
    result.conversations = conversations;
    
    // Find the active/visible chat messages
    // Look for elements with message content in the main chat area
    var chatArea = document.querySelector('[class*="text-ide-message-block-bot-color"]');
    if (chatArea) {
        // Get all direct and nested text content
        var msgElements = chatArea.querySelectorAll('[class*="message-block"], [class*="msg-content"], [class*="chat-bubble"], [class*="prose"]');
        var messages = [];
        for (var i = 0; i < msgElements.length; i++) {
            var text = msgElements[i].textContent.trim();
            if (text && text.length > 5) {
                messages.push({
                    cls: (msgElements[i].className || '').substring(0, 80),
                    text: text.substring(0, 200)
                });
            }
        }
        result.messages = messages;
        
        // Also get the full text of the chat area
        result.chatFullText = chatArea.textContent.substring(0, 500);
    }
    
    // Check the input box area for any pending text
    var inputBox = document.querySelector('#antigravity.agentSidePanelInputBox');
    if (inputBox) {
        var editable = inputBox.querySelector('[contenteditable="true"]');
        result.inputText = editable ? editable.textContent : 'no editable found';
    }
    
    return result;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_read, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("Conversations: %d" % len(value.get("conversations", [])))
for c in value.get("conversations", []):
    print("  - %s" % c[:80])

print("\nMessages: %d" % len(value.get("messages", [])))
for m in value.get("messages", [])[:15]:
    print("  cls=%s" % m["cls"][:60])
    print("  text: %s" % m["text"][:120])

print("\nChat full text:")
print(value.get("chatFullText", "")[:400])

print("\nInput box: '%s'" % value.get("inputText", ""))

ws.close()
