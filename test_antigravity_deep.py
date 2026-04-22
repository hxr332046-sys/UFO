#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deep search Antigravity DOM including iframes and shadow DOM."""

import json
import requests
import websocket

CDP_PORT = 9225

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page" and "2046" in p.get("title", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Search including iframes and shadow DOM
js_deep = """
(function() {
    var results = {iframes: [], shadowRoots: [], messageFound: false};
    
    // Check all iframes
    var iframes = document.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        results.iframes.push({
            src: (iframes[i].src || '').substring(0, 100),
            id: iframes[i].id || '',
            cls: (iframes[i].className || '').substring(0, 60)
        });
    }
    
    // Check for webview tags
    var webviews = document.querySelectorAll('webview');
    results.webviewCount = webviews.length;
    
    // Search shadow DOMs
    var allElements = document.querySelectorAll('*');
    for (var i = 0; i < allElements.length; i++) {
        if (allElements[i].shadowRoot) {
            var shadowText = allElements[i].shadowRoot.textContent || '';
            results.shadowRoots.push({
                host: allElements[i].tagName,
                hostCls: (allElements[i].className || '').substring(0, 60),
                hasCDP: shadowText.includes('CDP'),
                textPreview: shadowText.substring(0, 100)
            });
        }
    }
    
    // Get the chat container's inner HTML structure (first 2000 chars)
    var chatContainer = document.querySelector('[class*="text-ide-message-block-bot-color"]');
    if (chatContainer) {
        results.chatHTML = chatContainer.innerHTML.substring(0, 2000);
    }
    
    // Also check the second child (actual messages)
    var msgContainer = chatContainer ? chatContainer.children[1] : null;
    if (msgContainer) {
        results.msgContainerHTML = msgContainer.innerHTML.substring(0, 3000);
    }
    
    return results;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_deep, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("Iframes: %d" % len(value.get("iframes", [])))
for i in value.get("iframes", []):
    print("  src=%s id=%s cls=%s" % (i["src"][:60], i["id"], i["cls"][:40]))

print("Webviews: %d" % value.get("webviewCount", 0))
print("Shadow roots: %d" % len(value.get("shadowRoots", [])))
for s in value.get("shadowRoots", []):
    print("  host=%s hasCDP=%s" % (s["host"], s.get("hasCDP")))

print("\nChat HTML (first 500 chars):")
print(value.get("chatHTML", "")[:500])

print("\nMsg container HTML (first 1000 chars):")
print(value.get("msgContainerHTML", "")[:1000])

ws.close()
