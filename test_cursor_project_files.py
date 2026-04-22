#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Cursor project files and code via CDP - explore editor tabs, file tree, and open files."""

import json
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Explore: file tree, editor tabs, open file content
js = """
(function() {
    var result = {};
    
    // 1. Editor tabs - currently open files
    var tabs = document.querySelectorAll('[class*="tab"][class*="label"], [class*="tabs-container"] [role="tab"]');
    var openFiles = [];
    for (var i = 0; i < tabs.length; i++) {
        var text = (tabs[i].textContent || '').trim();
        if (text && text.length > 0 && text.length < 100) {
            openFiles.push(text);
        }
    }
    result.openFiles = openFiles;
    
    // 2. File explorer tree items
    var treeItems = document.querySelectorAll('[class*="explorer-item"], [class*="tree-item"], [class*="file-icon"], [role="treeitem"]');
    var files = [];
    var seen = {};
    for (var i = 0; i < treeItems.length; i++) {
        var text = (treeItems[i].textContent || '').trim();
        if (text && text.length > 1 && text.length < 80 && !seen[text]) {
            seen[text] = true;
            files.push(text);
        }
    }
    result.fileTree = files.slice(0, 50);
    
    // 3. Active editor content (Monaco editor)
    var monacoEditor = document.querySelector('[class*="monaco-editor"]');
    if (monacoEditor) {
        // Get visible lines from Monaco
        var lines = monacoEditor.querySelectorAll('[class*="view-line"]');
        var codeLines = [];
        for (var i = 0; i < lines.length; i++) {
            var text = (lines[i].textContent || '');
            if (text) codeLines.push(text);
        }
        result.activeEditorLines = codeLines.length;
        result.activeEditorPreview = codeLines.slice(0, 30).join('\\n');
    }
    
    // 4. Breadcrumb / path of current file
    var breadcrumbs = document.querySelectorAll('[class*="breadcrumb"]');
    var breadcrumbTexts = [];
    for (var i = 0; i < breadcrumbs.length; i++) {
        var text = (breadcrumbs[i].textContent || '').trim();
        if (text) breadcrumbTexts.push(text);
    }
    result.breadcrumbs = breadcrumbTexts;
    
    // 5. Status bar info
    var statusBar = document.querySelector('[class*="statusbar"]');
    if (statusBar) {
        result.statusBar = statusBar.textContent.substring(0, 200);
    }
    
    // 6. Explorer panel sections
    var explorerSections = document.querySelectorAll('[class*="explorer"] [class*="header"], [class*="explorer"] [class*="section"]');
    var sections = [];
    for (var i = 0; i < explorerSections.length; i++) {
        var text = explorerSections[i].textContent.trim();
        if (text && text.length < 60) sections.push(text);
    }
    result.explorerSections = sections;
    
    return result;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("=== Open Files (Tabs) ===")
for f in value.get("openFiles", []):
    print("  %s" % f)

print("\n=== File Tree (%d items) ===" % len(value.get("fileTree", [])))
for f in value.get("fileTree", [])[:30]:
    print("  %s" % f)

print("\n=== Active Editor ===")
print("  Lines: %d" % value.get("activeEditorLines", 0))
if value.get("activeEditorPreview"):
    print("  Preview:")
    print(value["activeEditorPreview"][:600])

print("\n=== Breadcrumbs ===")
for b in value.get("breadcrumbs", []):
    print("  %s" % b)

print("\n=== Status Bar ===")
print("  %s" % value.get("statusBar", "")[:100])

print("\n=== Explorer Sections ===")
for s in value.get("explorerSections", []):
    print("  %s" % s)

ws.close()
