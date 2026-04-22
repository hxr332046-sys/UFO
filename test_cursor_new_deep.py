#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deep explore new Cursor version DOM - broader search."""

import json
import requests
import websocket

CDP_PORT = 9223

pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
page = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

# Very broad search
js_broad = """
(function() {
    var result = {};
    
    // All contenteditable
    var editables = document.querySelectorAll('[contenteditable="true"]');
    result.editableCount = editables.length;
    result.editables = [];
    for (var i = 0; i < editables.length; i++) {
        var e = editables[i];
        result.editables.push({
            tag: e.tagName,
            cls: (e.className || '').substring(0, 120),
            id: e.id || '',
            text: (e.textContent || '').substring(0, 80),
            parentCls: (e.parentElement ? e.parentElement.className || '' : '').substring(0, 80)
        });
    }
    
    // Search for any element with significant text content
    var allDivs = document.querySelectorAll('div, section, article, main');
    var textBlocks = [];
    var seen = {};
    for (var i = 0; i < allDivs.length; i++) {
        var el = allDivs[i];
        var text = el.textContent.trim();
        // Only leaf-ish elements with real content
        if (text.length > 10 && text.length < 300 && !seen[text.substring(0, 20)]) {
            seen[text.substring(0, 20)] = true;
            var cls = (el.className || '').substring(0, 100);
            if (cls.includes('chat') || cls.includes('message') || cls.includes('thread') || 
                cls.includes('response') || cls.includes('prompt') || cls.includes('agent') ||
                cls.includes('bubble') || cls.includes('panel') || cls.includes('turn') ||
                cls.includes('prose') || cls.includes('tiptap') || cls.includes('input') ||
                cls.includes('reply') || cls.includes('conversation') || cls.includes('human') ||
                cls.includes('bot') || cls.includes('ai-') || cls.includes('user-')) {
                textBlocks.push({cls: cls, text: text.substring(0, 150)});
            }
        }
    }
    result.textBlocks = textBlocks;
    
    // Get body text summary
    result.bodyTextLength = document.body.textContent.length;
    result.bodyPreview = document.body.textContent.substring(0, 500);
    
    return result;
})()
"""

ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_broad, "returnByValue": True}}))
result = json.loads(ws.recv())
value = result.get("result", {}).get("result", {}).get("value", {})

print("Editables: %d" % value.get("editableCount", 0))
for e in value.get("editables", [])[:5]:
    print("  %s cls=%s id=%s" % (e["tag"], e["cls"][:80], e["id"]))
    print("    text=%s parent=%s" % (e["text"][:50], e["parentCls"][:50]))

print("\nRelevant text blocks: %d" % len(value.get("textBlocks", [])))
for b in value.get("textBlocks", [])[:20]:
    print("  cls=%s" % b["cls"][:80])
    print("    text: %s" % b["text"][:100])

print("\nBody text length: %d" % value.get("bodyTextLength", 0))
print("Body preview: %s" % value.get("bodyPreview", "")[:300])

ws.close()
