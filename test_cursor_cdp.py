#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Cursor chat via CDP and explore its structure."""

import json
import time
import requests
import websocket


CDP_PORT = 9223


def main():
    pages = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3).json()
    print("CDP Pages: %d" % len(pages))

    page = None
    for p in pages:
        if p.get("type") == "page" and ("Cursor" in p.get("title", "") or "cursor" in p.get("url", "").lower()):
            page = p
            break

    if not page:
        print("No Cursor page found")
        return

    print("Page: %s" % page.get("title", ""))
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

    # Search for chat/AI panel elements
    js_search = """
    (function() {
        var editables = document.querySelectorAll('[contenteditable="true"]');
        var editableInfo = [];
        for (var i = 0; i < editables.length; i++) {
            var e = editables[i];
            editableInfo.push({
                tag: e.tagName,
                cls: (e.className || '').substring(0, 80),
                text: (e.textContent || '').substring(0, 80),
                placeholder: e.getAttribute('placeholder') || ''
            });
        }

        var chatElements = [];
        var allEl = document.querySelectorAll(
            '[class*="chat"], [class*="aislash"], [class*="cursor-chat"], ' +
            '[class*="composer"], [class*="message"], [class*="conversation"], ' +
            '[class*="answering"], [class*="ai-message"], [class*="human-message"]'
        );
        for (var i = 0; i < allEl.length && i < 40; i++) {
            var el = allEl[i];
            chatElements.push({
                tag: el.tagName,
                cls: (el.className || '').substring(0, 100),
                text: (el.textContent || '').substring(0, 100)
            });
        }

        return {
            editables: editableInfo,
            chatElements: chatElements,
            title: document.title
        };
    })()
    """

    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": js_search, "returnByValue": True}
    }))
    result = json.loads(ws.recv())
    value = result.get("result", {}).get("result", {}).get("value", {})

    print("\n=== Cursor Chat Structure ===")
    print("Contenteditable elements: %d" % len(value.get("editables", [])))
    for e in value.get("editables", [])[:10]:
        print("  %s class=%s text=%s placeholder=%s" % (
            e["tag"], e["cls"][:50], e["text"][:40], e.get("placeholder", "")))

    print("\nChat/AI elements: %d" % len(value.get("chatElements", [])))
    for e in value.get("chatElements", [])[:25]:
        print("  %s class=%s" % (e["tag"], e["cls"][:80]))
        if e["text"]:
            print("    text: %s" % e["text"][:80])

    ws.close()


if __name__ == "__main__":
    main()
