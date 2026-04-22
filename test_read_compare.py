#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare CDP vs UIA reading speed for Windsurf Cascade chat."""

import json
import time
import ctypes
import requests
import websocket
from pywinauto import Application, Desktop


def cdp_read():
    """Read Cascade messages via CDP."""
    t0 = time.time()
    pages = requests.get("http://127.0.0.1:9222/json", timeout=3).json()
    ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=10)

    js_code = r"""
    (function() {
        const panels = document.querySelectorAll('[class*="panel-border"]');
        const msgs = [];
        for (const p of panels) {
            const text = p.textContent || '';
            if (text.trim()) {
                const parent = p.parentElement;
                const parentCls = parent ? parent.className : '';
                const isBot = parentCls.includes('bot') || parentCls.includes('message-block-bot');
                const isUser = parentCls.includes('user') || parentCls.includes('human');
                const role = isBot ? 'AI' : isUser ? 'USER' : (text.length > 50 ? 'AI' : 'USER');
                msgs.push({role: role, text: text.substring(0, 120)});
            }
        }
        return msgs;
    })()
    """

    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": js_code, "returnByValue": True}
    }))
    result = json.loads(ws.recv())
    elapsed = time.time() - t0
    msgs = result.get("result", {}).get("result", {}).get("value", [])
    ws.close()
    return msgs, elapsed


def uia_read():
    """Read Cascade messages via UIA."""
    t0 = time.time()

    desktop = Desktop(backend="win32")
    target_pid = None
    for w in desktop.windows():
        if "2046" in w.window_text() and "Windsurf" in w.window_text():
            hwnd = w.element_info.handle
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            target_pid = pid.value
            break

    app = Application(backend="uia").connect(process=target_pid, timeout=5)
    top_win = app.top_window()

    cascade_root = None
    for c in top_win.descendants():
        try:
            if "chat-client-root" in (c.element_info.class_name or ""):
                cascade_root = c
                break
        except:
            pass

    msgs = []
    for c in cascade_root.descendants():
        try:
            cls = c.element_info.class_name or ""
            ctype = c.element_info.control_type
            if "panel-border" in cls and ctype == "Group":
                texts = []
                for d in c.descendants():
                    try:
                        if d.element_info.control_type == "Text" and d.window_text():
                            texts.append(d.window_text())
                    except:
                        pass
                full = " ".join(texts)[:120]
                if full.strip():
                    role = "AI" if len(texts) > 5 else "USER"
                    msgs.append({"role": role, "text": full})
        except:
            pass

    elapsed = time.time() - t0
    return msgs, elapsed


def main():
    print("=" * 60)
    print("  CDP vs UIA: Cascade Chat Reading Speed Comparison")
    print("=" * 60)

    # CDP Read
    cdp_msgs, cdp_time = cdp_read()
    print("\n--- CDP Read ---")
    print("Time: %.3fs | Messages: %d" % (cdp_time, len(cdp_msgs)))
    for m in cdp_msgs[-8:]:
        print("  [%s] %s" % (m["role"], m["text"][:80]))

    # UIA Read
    uia_msgs, uia_time = uia_read()
    print("\n--- UIA Read ---")
    print("Time: %.3fs | Messages: %d" % (uia_time, len(uia_msgs)))
    for m in uia_msgs[-8:]:
        print("  [%s] %s" % (m["role"], m["text"][:80]))

    # Comparison
    print("\n" + "=" * 60)
    print("  Result")
    print("=" * 60)
    print("  CDP: %.3fs (%d msgs)" % (cdp_time, len(cdp_msgs)))
    print("  UIA: %.3fs (%d msgs)" % (uia_time, len(uia_msgs)))
    if cdp_time > 0:
        print("  CDP is %.1fx faster than UIA" % (uia_time / cdp_time))


if __name__ == "__main__":
    main()
