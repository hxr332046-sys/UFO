#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read all Cursor conversations and projects via CDP."""

import json
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Get all conversations from sidebar
js = """
(function() {
    var result = {};
    
    // Conversation list
    var convBtns = document.querySelectorAll('[class*="glass-sidebar-agent-menu-btn"]');
    var convs = [];
    for (var i = 0; i < convBtns.length; i++) {
        convs.push(convBtns[i].textContent.trim());
    }
    result.conversations = convs;
    
    // Project/workspace list - look for workspace indicators
    var wsEls = document.querySelectorAll('[class*="workspace"], [class*="project"], [class*="folder"]');
    var projects = [];
    for (var i = 0; i < wsEls.length; i++) {
        var text = wsEls[i].textContent.trim();
        if (text && text.length > 2 && text.length < 100) {
            projects.push({
                cls: (wsEls[i].className || '').substring(0, 80),
                text: text.substring(0, 80)
            });
        }
    }
    result.projects = projects;
    
    // Title bar / tab info for current workspace
    var titleBar = document.querySelector('[class*="titlebar"], [class*="tab"]');
    if (titleBar) {
        result.titleBarText = titleBar.textContent.substring(0, 200);
    }
    
    // Sidebar sections
    var sidebarSections = document.querySelectorAll('[class*="sidebar-section"], [class*="sidebar-header"]');
    var sections = [];
    for (var i = 0; i < sidebarSections.length; i++) {
        sections.push(sidebarSections[i].textContent.trim().substring(0, 60));
    }
    result.sidebarSections = sections;
    
    // All sidebar buttons with meaningful text
    var allSidebarBtns = document.querySelectorAll('[class*="sidebar"] button, [class*="sidebar"] [role="button"]');
    var sidebarItems = [];
    var seen = {};
    for (var i = 0; i < allSidebarBtns.length; i++) {
        var text = (allSidebarBtns[i].textContent || '').trim();
        if (text && text.length > 1 && text.length < 80 && !seen[text.substring(0, 15)]) {
            seen[text.substring(0, 15)] = true;
            sidebarItems.push(text);
        }
    }
    result.sidebarItems = sidebarItems;
    
    // Page title = current workspace name
    result.pageTitle = document.title;
    
    return result;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("Page: %s" % value.get("pageTitle", ""))
print("\n=== Conversations (%d) ===" % len(value.get("conversations", [])))
for i, c in enumerate(value.get("conversations", [])):
    print("[%d] %s" % (i, c))

print("\n=== Projects/Workspaces (%d) ===" % len(value.get("projects", [])))
for p in value.get("projects", [])[:20]:
    print("  cls=%s" % p["cls"][:50])
    print("  text: %s" % p["text"])

print("\n=== Sidebar Sections ===" )
for s in value.get("sidebarSections", []):
    print("  %s" % s)

print("\n=== Sidebar Items (%d) ===" % len(value.get("sidebarItems", [])))
for item in value.get("sidebarItems", [])[:30]:
    print("  %s" % item)

ws.close()
