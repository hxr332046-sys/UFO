#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test: Silent message sending to minimized Windsurf Cascade.
3 approaches:
  1. UIA ValuePattern (programmatic, no focus needed)
  2. SendMessage / PostMessage (Win32 API)
  3. InvokePattern (UIA button click)
"""

import time
import ctypes
import json
from pywinauto import Application, Desktop
import pyperclip


def find_windsurf_2046():
    """Find Windsurf 2046 window."""
    desktop = Desktop(backend="win32")
    for w in desktop.windows():
        if "2046" in w.window_text() and "Windsurf" in w.window_text():
            hwnd = w.element_info.handle
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value, hwnd
    return None, None


def test_uia_value_pattern(pid):
    """
    Approach 1: UIA ValuePattern
    Directly set Edit control value via COM, no keyboard/mouse/focus needed.
    This is how Power Automate's "simulated" mode works.
    """
    print("=" * 60)
    print("  Approach 1: UIA ValuePattern (Silent)")
    print("=" * 60)

    app = Application(backend="uia").connect(process=pid, timeout=5)
    top_win = app.top_window()

    # Find cascade root
    cascade_root = None
    for c in top_win.descendants():
        try:
            if "chat-client-root" in (c.element_info.class_name or ""):
                cascade_root = c
                break
        except:
            pass

    if not cascade_root:
        print("  Cascade not found")
        return False

    # Find input box
    input_box = None
    for c in cascade_root.descendants():
        try:
            cls = c.element_info.class_name or ""
            ctype = c.element_info.control_type
            if ctype == "Edit" and "min-h" in cls:
                input_box = c
                break
        except:
            pass

    if not input_box:
        print("  Input box not found")
        return False

    print("  Found input box: class=%s" % (input_box.element_info.class_name or ""))

    # Try ValuePattern to set text directly
    message = "静默发送测试-UIA-ValuePattern"
    try:
        # Method A: set_edit_text uses ValuePattern internally
        input_box.set_edit_text(message)
        time.sleep(0.5)

        # Verify text was set
        current = input_box.window_text() or ""
        if message in current:
            print("  ValuePattern SET text: OK")
            print("  Current text: %s" % current[:60])

            # Now need to "submit" - try InvokePattern on send button
            # or use ValuePattern + keyboard Enter without focusing window
            # First, let's see if there's a send button
            send_btn = None
            for c in cascade_root.descendants():
                try:
                    name = (c.window_text() or "").lower()
                    ctype = c.element_info.control_type
                    if ctype == "Button" and ("send" in name or "submit" in name or "ask" in name):
                        send_btn = c
                        break
                except:
                    pass

            if send_btn:
                print("  Found send button: %s" % send_btn.window_text())
                try:
                    send_btn.click_input()  # Try invoke
                    print("  Clicked send button")
                    return True
                except:
                    try:
                        send_btn.invoke()
                        print("  Invoked send button")
                        return True
                    except:
                        print("  Send button click failed")
            else:
                print("  No send button found, trying Enter via SendKeys...")
                # This requires focus unfortunately
                return False
        else:
            print("  ValuePattern SET text: FAILED")
            print("  Current: '%s'" % current[:60])
            return False
    except Exception as e:
        print("  ValuePattern error: %s" % str(e)[:100])
        return False


def test_sendmessage(hwnd):
    """
    Approach 2: SendMessage / PostMessage (Win32 API)
    Send WM_CHAR messages directly to the window handle.
    No focus needed, but only works for Win32 controls.
    """
    print("\n" + "=" * 60)
    print("  Approach 2: SendMessage/PostMessage (Win32)")
    print("=" * 60)

    WM_CHAR = 0x0102
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SETTEXT = 0x000C

    # SendMessage can set text on Win32 Edit controls
    # But Windsurf uses Chromium (not Win32 Edit), so this likely won't work
    print("  Note: Windsurf is Chromium-based, not Win32 Edit")
    print("  SendMessage WM_SETTEXT only works on native Win32 controls")
    print("  Skipping (will not work for Chromium/Electron)")
    return False


def test_uia_invoke_pattern(pid):
    """
    Approach 3: UIA InvokePattern + ValuePattern combo
    1. Use ValuePattern to set text (no focus)
    2. Find the "Ask" submit element and use InvokePattern
    """
    print("\n" + "=" * 60)
    print("  Approach 3: UIA InvokePattern (Silent Submit)")
    print("=" * 60)

    app = Application(backend="uia").connect(process=pid, timeout=5)
    top_win = app.top_window()

    # Find all buttons/elements near the input box
    cascade_root = None
    for c in top_win.descendants():
        try:
            if "chat-client-root" in (c.element_info.class_name or ""):
                cascade_root = c
                break
        except:
            pass

    if not cascade_root:
        print("  Cascade not found")
        return False

    # Find input box and set text via ValuePattern
    input_box = None
    for c in cascade_root.descendants():
        try:
            cls = c.element_info.class_name or ""
            ctype = c.element_info.control_type
            if ctype == "Edit" and "min-h" in cls:
                input_box = c
                break
        except:
            pass

    if not input_box:
        print("  Input box not found")
        return False

    message = "静默发送测试-InvokePattern"
    try:
        input_box.set_edit_text(message)
        time.sleep(0.3)
        current = input_box.window_text() or ""
        print("  Text set: '%s'" % current[:60])

        if message not in current:
            print("  Text not confirmed, aborting")
            return False
    except Exception as e:
        print("  set_edit_text failed: %s" % str(e)[:80])
        return False

    # Now find the submit trigger
    # In Windsurf Cascade, pressing Enter submits
    # We need to find a way to trigger submit without keyboard

    # Option A: Look for a submit button
    print("  Searching for submit button...")
    for c in cascade_root.descendants():
        try:
            cls = c.element_info.class_name or ""
            name = c.window_text() or ""
            ctype = c.element_info.control_type

            # Check for button-like elements near input
            if ctype == "Button" and any(k in name.lower() for k in ["send", "submit", "ask", "go"]):
                print("  Found candidate: %s (%s)" % (name, cls[:40]))
                try:
                    # Try InvokePattern
                    c.invoke()
                    print("  Invoked!")
                    return True
                except:
                    try:
                        c.click_input()
                        print("  Clicked!")
                        return True
                    except:
                        pass
        except:
            pass

    # Option B: Use UIA's keyboard simulation without window focus
    # IUIAutomationElement::SetFocus + SendKeys
    print("  No submit button found")
    print("  Trying SetFocus on input + SendKeys Enter (may pop window)...")

    # Check if we can use IUIAutomation::SetFocus (not Win32 SetForegroundWindow)
    try:
        # element.SetFocus() is UIA-level, might not bring window to front
        input_box.element_info.element.SetFocus()
        time.sleep(0.3)
        from pywinauto import keyboard
        keyboard.send_keys("{ENTER}")
        print("  Sent Enter via UIA SetFocus + SendKeys")
        return True
    except Exception as e:
        print("  UIA SetFocus failed: %s" % str(e)[:80])
        return False


def main():
    # First minimize the window
    pid, hwnd = find_windsurf_2046()
    if not pid:
        print("Windsurf 2046 not found")
        return

    print("Found Windsurf 2046: PID=%d HWND=%d" % (pid, hwnd))

    # Minimize it
    print("\nMinimizing window...")
    app_win32 = Application(backend="win32").connect(process=pid, timeout=5)
    top_win32 = app_win32.top_window()
    top_win32.minimize()
    time.sleep(1)
    print("Minimized: %s" % top_win32.is_minimized())

    # Test all approaches
    result1 = test_uia_value_pattern(pid)
    result2 = test_sendmessage(hwnd)
    result3 = test_uia_invoke_pattern(pid)

    # Restore window and verify
    print("\n" + "=" * 60)
    print("  Verification")
    print("=" * 60)
    top_win32.restore()
    time.sleep(2)

    app = Application(backend="uia").connect(process=pid, timeout=5)
    top_win = app.top_window()

    # Search for our messages
    for msg in ["静默发送测试-UIA-ValuePattern", "静默发送测试-InvokePattern"]:
        found = False
        for c in top_win.descendants():
            try:
                if msg in (c.window_text() or ""):
                    print("  FOUND: %s" % msg)
                    found = True
                    break
            except:
                pass
        if not found:
            print("  NOT FOUND: %s" % msg)

    # Summary
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print("  UIA ValuePattern (set text):  %s" % ("OK" if result1 else "FAILED"))
    print("  SendMessage/PostMessage:      %s" % ("OK" if result2 else "N/A (Chromium)"))
    print("  UIA InvokePattern (submit):   %s" % ("OK" if result3 else "FAILED"))


if __name__ == "__main__":
    main()
