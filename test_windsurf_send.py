#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Send a message to Windsurf Cascade input box via UIA automation."""

import time
import ctypes
from pywinauto import Application, Desktop


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
    app = Application(backend="uia").connect(process=target_pid, timeout=5)
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
        print("Cascade not found")
        return

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
        print("Input box not found")
        return

    rect = input_box.rectangle()
    print("Input box found: rect=(%d,%d,%d,%d)" % (rect.left, rect.top, rect.right, rect.bottom))
    print("Current text: '%s'" % (input_box.window_text() or ""))

    # First, bring the Windsurf window to foreground
    print("Bringing window to foreground...")
    try:
        top_win.set_focus()
        time.sleep(0.5)
    except:
        pass

    # Click on the input box to focus it
    print("Clicking input box...")
    try:
        input_box.click()
        time.sleep(0.3)
    except Exception as e:
        print("Click failed: %s, trying center click..." % str(e)[:60])
        # Try clicking at center of input box
        import pyautogui
        center_x = (rect.left + rect.right) // 2
        center_y = (rect.top + rect.bottom) // 2
        # If rect is off-screen (negative), we need to use the visible area
        # The cascade panel might be in a different virtual screen position
        # Let's try to activate the Cascade panel first
        print("Input box position seems off-screen, trying keyboard shortcut...")
        # Ctrl+L opens Cascade input
        from pywinauto import keyboard
        top_win.set_focus()
        time.sleep(0.3)
        keyboard.send_keys('^l')  # Ctrl+L
        time.sleep(1)
        # Re-find input box after Ctrl+L
        for c in top_win.descendants():
            try:
                cls = c.element_info.class_name or ""
                ctype = c.element_info.control_type
                if ctype == "Edit" and "min-h" in cls:
                    input_box = c
                    rect = input_box.rectangle()
                    print("Re-found input box: rect=(%d,%d,%d,%d)" % (rect.left, rect.top, rect.right, rect.bottom))
                    break
            except:
                pass

    # Now try to type the message
    message = "Embedding不能用GEMINI的来做备选质量差影响整体"
    print("Sending message: %s" % message)

    # Method 1: set_edit_text + Enter
    try:
        input_box.set_edit_text(message)
        time.sleep(0.3)
        print("Text set successfully, checking...")
        current = input_box.window_text() or ""
        print("Current input text: '%s'" % current[:80])

        if message in current:
            print("Message confirmed in input box! Sending with Enter...")
            from pywinauto import keyboard
            keyboard.send_keys('{ENTER}')
            print("✅ Message sent!")
        else:
            print("Text not confirmed, trying keyboard input...")
            # Method 2: keyboard.send_keys
            input_box.click()
            time.sleep(0.2)
            keyboard.send_keys('^a')  # Select all
            time.sleep(0.1)
            keyboard.send_keys(message + '{ENTER}')
            print("✅ Message sent via keyboard!")
    except Exception as e:
        print("Method 1 failed: %s" % str(e)[:100])
        print("Trying Method 3: pyautogui...")
        import pyautogui
        # Click input area
        center_x = (rect.left + rect.right) // 2
        center_y = (rect.top + rect.bottom) // 2
        if center_y < 0:
            # Input is off-screen, need to activate Cascade first
            print("Input off-screen, activating Cascade with Ctrl+L...")
            from pywinauto import keyboard
            top_win.set_focus()
            time.sleep(0.3)
            keyboard.send_keys('^l')
            time.sleep(1)
            # Re-find
            for c in top_win.descendants():
                try:
                    cls = c.element_info.class_name or ""
                    ctype = c.element_info.control_type
                    if ctype == "Edit" and "min-h" in cls:
                        input_box = c
                        rect = input_box.rectangle()
                        break
                except:
                    pass
            center_x = (rect.left + rect.right) // 2
            center_y = (rect.top + rect.bottom) // 2

        pyautogui.click(center_x, center_y)
        time.sleep(0.3)
        pyautogui.typewrite(message, interval=0.02)
        time.sleep(0.3)
        pyautogui.press('enter')
        print("✅ Message sent via pyautogui!")

    # Wait and verify
    time.sleep(2)
    print("\nVerifying message was sent...")
    # Check if input box is now empty (message was sent)
    try:
        remaining = input_box.window_text() or ""
        if not remaining.strip():
            print("✅ Input box is empty - message was sent successfully!")
        else:
            print("Input box still has text: '%s'" % remaining[:60])
    except:
        pass


if __name__ == "__main__":
    main()
