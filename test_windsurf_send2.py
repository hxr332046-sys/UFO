#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Send message to Windsurf Cascade - reliable method via keyboard shortcuts."""

import time
import ctypes
from pywinauto import Application, Desktop
from pywinauto import keyboard


def main():
    desktop = Desktop(backend="win32")
    target_pid = None
    for w in desktop.windows():
        if w.is_visible() and "2046" in w.window_text() and "Windsurf" in w.window_text():
            hwnd = w.element_info.handle
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            target_pid = pid.value
            break

    if not target_pid:
        print("Windsurf 2046 not found")
        return

    print("Found Windsurf 2046: PID=%d" % target_pid)

    # Step 1: Bring window to foreground
    app = Application(backend="uia").connect(process=target_pid, timeout=5)
    top_win = app.top_window()
    print("Step 1: Setting focus to Windsurf window...")
    top_win.set_focus()
    time.sleep(1)

    # Step 2: Use Ctrl+L to activate Cascade input
    print("Step 2: Pressing Ctrl+L to focus Cascade input...")
    keyboard.send_keys('^l')
    time.sleep(1.5)

    # Step 3: Verify input box is now focused by checking its state
    cascade_root = None
    for c in top_win.descendants():
        try:
            if "chat-client-root" in (c.element_info.class_name or ""):
                cascade_root = c
                break
        except:
            pass

    input_box = None
    if cascade_root:
        for c in cascade_root.descendants():
            try:
                cls = c.element_info.class_name or ""
                ctype = c.element_info.control_type
                if ctype == "Edit" and "min-h" in cls:
                    input_box = c
                    break
            except:
                pass

    if input_box:
        rect = input_box.rectangle()
        print("  Input box rect: (%d,%d,%d,%d)" % (rect.left, rect.top, rect.right, rect.bottom))
        print("  Input box text: '%s'" % (input_box.window_text() or "")[:60])

    # Step 4: Type the message using keyboard.send_keys (handles Chinese via clipboard)
    message = "Embedding不能用GEMINI的来做备选质量差影响整体"
    print("Step 3: Typing message via clipboard paste...")

    # Use clipboard to paste Chinese text (keyboard.send_keys can't handle Chinese directly)
    import pyperclip
    pyperclip.copy(message)

    # Ctrl+A to select any existing text, then Ctrl+V to paste
    keyboard.send_keys('^a')
    time.sleep(0.2)
    keyboard.send_keys('^v')
    time.sleep(0.5)

    # Verify text was pasted
    if input_box:
        current = input_box.window_text() or ""
        print("  Input box now contains: '%s'" % current[:80])
        if message in current:
            print("  ✅ Message confirmed in input box!")
        else:
            print("  ⚠️ Message may not be in input box, trying again...")
            keyboard.send_keys('^a')
            time.sleep(0.1)
            keyboard.send_keys('^v')
            time.sleep(0.5)

    # Step 5: Press Enter to send
    print("Step 4: Pressing Enter to send...")
    keyboard.send_keys('{ENTER}')
    time.sleep(1)

    # Step 6: Verify message was sent
    print("Step 5: Verifying...")
    time.sleep(2)

    # Re-check input box
    if cascade_root:
        for c in cascade_root.descendants():
            try:
                cls = c.element_info.class_name or ""
                ctype = c.element_info.control_type
                if ctype == "Edit" and "min-h" in cls:
                    remaining = c.window_text() or ""
                    if not remaining.strip() or remaining.strip() == '\n':
                        print("✅ Input box is empty - MESSAGE SENT SUCCESSFULLY!")
                    else:
                        print("Input box still has: '%s'" % remaining[:60])
                    break
            except:
                pass

    # Search for our message in cascade - re-find root first
    print("\nSearching for our message in Cascade content...")
    cascade_root2 = None
    for c in top_win.descendants():
        try:
            if "chat-client-root" in (c.element_info.class_name or ""):
                cascade_root2 = c
                break
        except:
            pass

    if not cascade_root2:
        print("Cascade root not found after send, searching all descendants...")
        search_root = top_win
    else:
        search_root = cascade_root2

    all_texts = []
    for c in search_root.descendants():
        try:
            name = c.window_text() or ""
            if "Embedding" in name and "GEMINI" in name:
                all_texts.append(name[:100])
        except:
            pass

    if all_texts:
        print("✅ Found our message in Cascade:")
        for t in all_texts[:3]:
            print("  %s" % t)
    else:
        print("Message not yet visible in bubbles (may still be processing)")


if __name__ == "__main__":
    main()
