#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test: Send message to Windsurf Cascade via CDP (Chrome DevTools Protocol)
Completely silent - no window focus, no keyboard, no mouse.
Window can be minimized.
"""

import json
import time
import requests
import websocket


CDP_PORT = 9222
CDP_HOST = "127.0.0.1"


def get_cdp_pages():
    """Get available CDP pages."""
    r = requests.get("http://%s:%d/json" % (CDP_HOST, CDP_PORT), timeout=3)
    return r.json()


def find_cascade_page(pages):
    """Find the page that contains Cascade (the main Windsurf window)."""
    for p in pages:
        if "2046" in p.get("title", ""):
            return p
    # Fallback: return first page
    return pages[0] if pages else None


def cdp_evaluate(ws, expression, timeout=10):
    """Execute JavaScript via CDP Runtime.evaluate."""
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
            "timeout": timeout * 1000,
        }
    }))
    result = json.loads(ws.recv())
    return result


def send_cascade_message_silent(message):
    """
    Send a message to Windsurf Cascade via CDP.
    No window focus, no keyboard, no mouse needed.
    """
    pages = get_cdp_pages()
    page = find_cascade_page(pages)
    if not page:
        print("No CDP page found")
        return False

    ws_url = page["webSocketDebuggerUrl"]
    print("Connecting to CDP: %s" % ws_url[:60])
    ws = websocket.create_connection(ws_url, timeout=15)

    # Step 1: Find the Cascade input element and set its content
    print("Step 1: Finding Cascade input element...")
    js_find_input = """
    (function() {
        // Find the contenteditable input in Cascade panel
        const input = document.querySelector('[contenteditable="true"][class*="min-h"]');
        if (input) {
            return {found: true, tag: input.tagName, class: input.className.substring(0, 60)};
        }
        // Try broader search
        const editables = document.querySelectorAll('[contenteditable="true"]');
        for (const el of editables) {
            const cls = el.className || '';
            if (cls.includes('min-h') || cls.includes('outline-none') || cls.includes('chat-input')) {
                return {found: true, tag: el.tagName, class: cls.substring(0, 60)};
            }
        }
        // Last resort: any contenteditable
        if (editables.length > 0) {
            return {found: true, tag: editables[0].tagName, class: (editables[0].className||'').substring(0, 60), count: editables.length};
        }
        return {found: false, count: editables.length};
    })()
    """

    result = cdp_evaluate(ws, js_find_input)
    print("  Result: %s" % json.dumps(result.get("result", {}).get("result", {}).get("value", {})))

    # Step 2: Set text content and trigger input event
    print("Step 2: Setting message content...")
    # Escape the message for JS
    escaped_msg = message.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", "\\n")

    js_set_text = """
    (function() {
        const input = document.querySelector('[contenteditable="true"][class*="min-h"]')
            || document.querySelectorAll('[contenteditable="true"]')[0];
        if (!input) return {success: false, error: 'no input found'};

        // Clear existing content
        input.textContent = '';

        // Set new content
        input.textContent = '%s';

        // Trigger input event so React/Vue picks up the change
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new InputEvent('beforeinput', {bubbles: true, inputType: 'insertText', data: '%s'}));
        input.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: '%s'}));

        return {success: true, text: input.textContent.substring(0, 50)};
    })()
    """ % (escaped_msg, escaped_msg, escaped_msg)

    result = cdp_evaluate(ws, js_set_text)
    value = result.get("result", {}).get("result", {}).get("value", {})
    print("  Set text result: %s" % json.dumps(value))

    if not value.get("success"):
        print("  FAILED to set text")
        ws.close()
        return False

    time.sleep(0.5)

    # Step 3: Trigger submit (Enter key)
    print("Step 3: Triggering submit (Enter key)...")
    js_submit = """
    (function() {
        const input = document.querySelector('[contenteditable="true"][class*="min-h"]')
            || document.querySelectorAll('[contenteditable="true"]')[0];
        if (!input) return {success: false, error: 'no input'};

        // Dispatch keydown Enter event
        const enterEvent = new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true,
            cancelable: true
        });
        input.dispatchEvent(enterEvent);

        // Also try keypress and keyup
        input.dispatchEvent(new KeyboardEvent('keypress', {
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
        }));
        input.dispatchEvent(new KeyboardEvent('keyup', {
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
        }));

        return {success: true};
    })()
    """

    result = cdp_evaluate(ws, js_submit)
    value = result.get("result", {}).get("result", {}).get("value", {})
    print("  Submit result: %s" % json.dumps(value))

    ws.close()
    return value.get("success", False)


def main():
    # First, minimize the Windsurf window
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
        print("Minimizing Windsurf 2046...")
        target_win.minimize()
        time.sleep(1)
        print("  Minimized: %s" % target_win.is_minimized())
    else:
        print("Windsurf 2046 not found (may already be minimized)")

    # Send message via CDP (completely silent)
    message = "CDP静默发送测试-窗口最小化状态"
    print("\nSending via CDP (silent, no focus): '%s'" % message)
    print("=" * 60)

    success = send_cascade_message_silent(message)

    # Wait and verify
    print("\nWaiting 3s for message to appear...")
    time.sleep(3)

    # Verify via UIA (restore window first)
    if target_win:
        target_win.restore()
        time.sleep(2)

    # Search for our message
    if target_pid:
        app = Application(backend="uia").connect(process=target_pid, timeout=5)
        top_win = app.top_window()

        found = False
        for c in top_win.descendants():
            try:
                name = c.window_text() or ""
                if "CDP" in name and "静默" in name:
                    print("FOUND via UIA: %s" % name[:80])
                    found = True
                    break
            except:
                pass

        if not found:
            print("Message not found in UIA tree yet")
            # Also check via CDP
            try:
                pages = get_cdp_pages()
                page = find_cascade_page(pages)
                ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
                result = cdp_evaluate(ws, """
                    (function() {
                        const all = document.querySelectorAll('[class*="panel-border"]');
                        const texts = [];
                        for (const el of all) {
                            const t = el.textContent || '';
                            if (t.includes('CDP') && t.includes('静默')) {
                                texts.push(t.substring(0, 100));
                            }
                        }
                        return texts;
                    })()
                """)
                value = result.get("result", {}).get("result", {}).get("value", [])
                if value:
                    print("FOUND via CDP DOM: %s" % json.dumps(value[:2]))
                else:
                    print("Not found via CDP DOM either - Enter event may not have triggered submit")
                ws.close()
            except Exception as e:
                print("CDP verify error: %s" % str(e)[:80])

    print("\n" + "=" * 60)
    print("  Result: CDP Silent Send %s" % ("SUCCESS" if success else "PARTIAL (text set, submit may need work)"))


if __name__ == "__main__":
    main()
