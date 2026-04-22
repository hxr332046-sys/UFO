#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create new Cursor conversation via CDP."""

import json
import time
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
print("Connected: %s" % page.get("title", ""))
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# === 1. Find "New" button or shortcut ===
js_find_new = """
(function() {
    var result = {};
    
    // Search for "New" / "New Agent" buttons
    var btns = document.querySelectorAll('button, [role="button"], a');
    var newBtns = [];
    for (var i = 0; i < btns.length; i++) {
        var text = (btns[i].textContent || '').trim();
        var aria = btns[i].getAttribute('aria-label') || '';
        var title = btns[i].getAttribute('title') || '';
        if ((text.match(/^New$/i) || text.includes('New Agent') || text.includes('New Chat') ||
             aria.includes('New') || title.includes('New')) && text.length < 30) {
            var rect = btns[i].getBoundingClientRect();
            newBtns.push({
                tag: btns[i].tagName,
                cls: (btns[i].className || '').substring(0, 80),
                text: text.substring(0, 30),
                aria: aria.substring(0, 30),
                title: title.substring(0, 30),
                x: rect.x + rect.width/2,
                y: rect.y + rect.height/2,
                visible: rect.width > 0 && rect.height > 0
            });
        }
    }
    result.newButtons = newBtns;
    
    // Also check for keyboard shortcut hints (like Ctrl+N, ⇧Tab)
    var shortcuts = document.querySelectorAll('[class*="shortcut"], [class*="keybinding"]');
    result.shortcuts = [];
    for (var i = 0; i < shortcuts.length; i++) {
        result.shortcuts.push(shortcuts[i].textContent.trim().substring(0, 30));
    }
    
    // Check the agent panel empty state for "New" options
    var emptyState = document.querySelector('[class*="agent-panel-empty"]');
    if (emptyState) {
        result.emptyStateText = emptyState.textContent.substring(0, 200);
        result.emptyStateHTML = emptyState.innerHTML.substring(0, 500);
    }
    
    // Check sidebar for "New" button
    var sidebarBtns = document.querySelectorAll('[class*="sidebar"] button, [class*="sidebar"] [role="button"]');
    result.sidebarNewBtns = [];
    for (var i = 0; i < sidebarBtns.length; i++) {
        var text = (sidebarBtns[i].textContent || '').trim();
        if (text.length < 30 && (text.match(/^New$/i) || text.includes('+') || text.includes('新建'))) {
            var rect = sidebarBtns[i].getBoundingClientRect();
            result.sidebarNewBtns.push({
                text: text,
                cls: (sidebarBtns[i].className || '').substring(0, 60),
                x: rect.x + rect.width/2,
                y: rect.y + rect.height/2,
                visible: rect.width > 0 && rect.height > 0
            });
        }
    }
    
    return result;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_find_new, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("\nNew buttons: %d" % len(value.get("newButtons", [])))
for b in value.get("newButtons", []):
    print("  %s text=%s aria=%s title=%s visible=%s pos=(%d,%d)" % (
        b["tag"], b["text"], b["aria"], b["title"], b["visible"], b["x"], b["y"]))

print("\nSidebar New buttons: %d" % len(value.get("sidebarNewBtns", [])))
for b in value.get("sidebarNewBtns", []):
    print("  text=%s cls=%s visible=%s pos=(%d,%d)" % (b["text"], b["cls"][:40], b["visible"], b["x"], b["y"]))

print("\nShortcuts: %s" % str(value.get("shortcuts", []))[:200])

empty = value.get("emptyStateText", "")
if empty:
    print("\nEmpty state: %s" % empty[:200])
    print("Empty HTML: %s" % value.get("emptyStateHTML", "")[:300])

ws.close()
