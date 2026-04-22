#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP Silent Send v2 - Use CDP Input domain to dispatch key events at browser level.
This bypasses DOM event system entirely and works with minimized windows.
"""

import json
import time
import requests
import websocket


CDP_PORT = 9222


def get_ws_url():
    r = requests.get("http://127.0.0.1:%d/json" % CDP_PORT, timeout=3)
    pages = r.json()
    for p in pages:
        if "2046" in p.get("title", ""):
            return p["webSocketDebuggerUrl"]
    return pages[0]["webSocketDebuggerUrl"] if pages else None


def cdp_send(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    # Read responses until we get our reply
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            return resp
        # Skip events


def cdp_evaluate(ws, expression, msg_id=1):
    return cdp_send(ws, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True,
    }, msg_id)


def focus_cascade_input(ws):
    """Focus the Cascade input via DOM, then use CDP Input to type."""
    js = """
    (function() {
        const input = document.querySelector('[contenteditable="true"][class*="min-h"]');
        if (input) {
            input.focus();
            // Clear existing content
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(input);
            sel.removeAllRanges();
            sel.addRange(range);
            return {found: true, focused: true};
        }
        return {found: false};
    })()
    """
    result = cdp_evaluate(ws, js)
    return result.get("result", {}).get("result", {}).get("value", {})


def type_text_via_cdp_input(ws, text):
    """
    Type text using CDP Input.dispatchKeyEvent.
    This works at browser level - no window focus needed.
    For Chinese text, use clipboard paste via CDP.
    """
    # Method: Use CDP to insert text via clipboard
    # Step 1: Focus the input element via DOM
    focus_result = focus_cascade_input(ws)
    print("  Focus result: %s" % json.dumps(focus_result))

    if not focus_result.get("found"):
        return False

    # Step 2: Use document.execCommand('insertText') which works with React
    # This is the key - execCommand triggers React's input handler
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    js_insert = """
    (function() {
        const input = document.querySelector('[contenteditable="true"][class*="min-h"]');
        if (!input) return {success: false};
        input.focus();

        // Select all existing content first
        const sel = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(input);
        sel.removeAllRanges();
        sel.addRange(range);

        // execCommand triggers React's onChange
        const result = document.execCommand('insertText', false, '%s');
        return {success: result, text: input.textContent.substring(0, 60)};
    })()
    """ % escaped

    result = cdp_evaluate(ws, js_insert)
    value = result.get("result", {}).get("result", {}).get("value", {})
    print("  Insert result: %s" % json.dumps(value))

    if not value.get("success"):
        # Fallback: try Input.insertText CDP method
        print("  execCommand failed, trying CDP Input.insertText...")
        result2 = cdp_send(ws, "Input.insertText", {
            "text": text
        })
        print("  Input.insertText result: %s" % json.dumps(result2.get("result", {})))

    time.sleep(0.3)

    # Step 3: Send Enter key via CDP Input domain (browser-level, not DOM)
    print("  Sending Enter via CDP Input.dispatchKeyEvent...")
    # keyDown
    cdp_send(ws, "Input.dispatchKeyEvent", {
        "type": "keyDown",
        "key": "Enter",
        "code": "Enter",
        "windowsVirtualKeyCode": 13,
        "nativeVirtualKeyCode": 13,
    })
    time.sleep(0.05)
    # keyUp
    cdp_send(ws, "Input.dispatchKeyEvent", {
        "type": "keyUp",
        "key": "Enter",
        "code": "Enter",
        "windowsVirtualKeyCode": 13,
        "nativeVirtualKeyCode": 13,
    })

    return True


def verify_message(ws, message):
    """Check if message appears in Cascade DOM."""
    time.sleep(3)
    escaped = message.replace("\\", "\\\\").replace("'", "\\'")
    js = """
    (function() {
        const panels = document.querySelectorAll('[class*="panel-border"]');
        for (const p of panels) {
            if (p.textContent && p.textContent.includes('%s')) {
                return {found: true, text: p.textContent.substring(0, 100)};
            }
        }
        return {found: false};
    })()
    """ % escaped

    result = cdp_evaluate(ws, js)
    return result.get("result", {}).get("result", {}).get("value", {})


def main():
    # Minimize window first
    from pywinauto import Application, Desktop
    import ctypes

    desktop = Desktop(backend="win32")
    target_pid = None
    target_win = None
    for w in desktop.windows():
        if "2046" in w.window_text() and "Windsurf" in w.window_text():
            hwnd = w.element_info.handle
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            target_pid = pid.value
            target_win = w
            break

    if target_win:
        print("Step 1: Minimizing Windsurf 2046...")
        target_win.minimize()
        time.sleep(1)
        print("  Minimized: %s" % target_win.is_minimized())

    # Connect CDP
    ws_url = get_ws_url()
    if not ws_url:
        print("CDP not available")
        return

    print("\nStep 2: CDP Silent Send (window minimized)...")
    print("  Connecting: %s" % ws_url[:60])
    ws = websocket.create_connection(ws_url, timeout=15)

    message = "CDP静默发送成功-最小化窗口"
    print("  Message: %s" % message)

    success = type_text_via_cdp_input(ws, message)

    # Verify via CDP DOM
    print("\nStep 3: Verifying via CDP DOM...")
    verify = verify_message(ws, message)
    print("  Verify: %s" % json.dumps(verify))

    ws.close()

    # Also restore and verify via UIA
    if target_win:
        target_win.restore()
        time.sleep(2)

    if target_pid:
        app = Application(backend="uia").connect(process=target_pid, timeout=5)
        top_win = app.top_window()
        for c in top_win.descendants():
            try:
                name = c.window_text() or ""
                if "CDP" in name and "静默" in name:
                    print("  UIA verify: FOUND - %s" % name[:80])
                    break
            except:
                pass

    print("\n" + "=" * 60)
    if verify.get("found"):
        print("  >>> CDP SILENT SEND: SUCCESS! <<<")
        print("  >>> Message sent while window was MINIMIZED <<<")
    else:
        print("  CDP Silent Send: Text may be set but submit not confirmed")
        print("  (CDP Input events may need the renderer process to be active)")


if __name__ == "__main__":
    main()
