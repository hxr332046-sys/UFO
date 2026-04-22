#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test: Send message to Windsurf Cascade when window is minimized."""

import time
import ctypes
from pywinauto import Application, Desktop, keyboard
import pyperclip


def main():
    # Find Windsurf 2046
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

    if not target_pid:
        print("Windsurf 2046 not found")
        return

    # Step 1: Minimize it
    print("Step 1: Minimizing Windsurf 2046...")
    target_win.minimize()
    time.sleep(1)
    print("  Minimized: %s" % target_win.is_minimized())

    # Step 2: Send message (set_focus will auto-restore)
    print("Step 2: Sending message while minimized...")
    app = Application(backend="uia").connect(process=target_pid, timeout=5)
    top_win = app.top_window()

    # set_focus restores the window
    top_win.set_focus()
    time.sleep(1)
    print("  After set_focus - Minimized: %s" % target_win.is_minimized())

    # Ctrl+L to focus Cascade input
    keyboard.send_keys("^l")
    time.sleep(1.5)

    # Paste message via clipboard
    message = "最小化窗口发送测试成功"
    pyperclip.copy(message)
    keyboard.send_keys("^a")
    time.sleep(0.2)
    keyboard.send_keys("^v")
    time.sleep(0.5)
    keyboard.send_keys("{ENTER}")
    time.sleep(2)

    # Step 3: Verify by reading cascade
    print("Step 3: Verifying message in Cascade...")
    time.sleep(2)  # Wait for UIA tree to refresh

    # Re-connect and search
    app2 = Application(backend="uia").connect(process=target_pid, timeout=5)
    top_win2 = app2.top_window()

    found = False
    for c in top_win2.descendants():
        try:
            name = c.window_text() or ""
            if message in name:
                ctype = c.element_info.control_type
                print("  FOUND: %s = %s" % (ctype, name[:80]))
                found = True
                break
        except:
            pass

    if found:
        print("\n>>> SUCCESS: Message sent from minimized window! <<<")
    else:
        print("\nMessage not found in UIA tree yet (may need more time)")
        # Check last bubbles
        print("Last bubbles:")
        for c in top_win2.descendants():
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
                    full = " ".join(texts)[:150]
                    if full.strip():
                        print("  %s" % full[:120])
            except:
                pass


if __name__ == "__main__":
    main()
