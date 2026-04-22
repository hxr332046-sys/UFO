#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test: Can we read Windsurf Cascade chat messages via UIA?"""

import time
import ctypes
from pywinauto import Application, Desktop


def get_pid_from_hwnd(hwnd):
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def find_windsurf_2046():
    desktop = Desktop(backend="win32")
    for w in desktop.windows():
        if w.is_visible() and "2046" in w.window_text() and "Windsurf" in w.window_text():
            hwnd = w.element_info.handle
            return get_pid_from_hwnd(hwnd)
    return None


def main():
    pid = find_windsurf_2046()
    if not pid:
        print("Windsurf 2046 not found")
        return

    print("Found Windsurf 2046: PID=%d" % pid)
    app = Application(backend="uia").connect(process=pid, timeout=5)
    top_win = app.top_window()
    descs = top_win.descendants()

    # Find cascade root
    cascade_root = None
    for c in descs:
        try:
            cls = c.element_info.class_name or ""
            if "chat-client-root" in cls:
                cascade_root = c
                break
        except:
            pass

    if not cascade_root:
        print("Cascade panel not found")
        return

    cascade_descs = cascade_root.descendants()
    print("Cascade descendants: %d" % len(cascade_descs))

    # === Message Bubbles ===
    print("\n" + "=" * 70)
    print("  Message Bubbles in Cascade")
    print("=" * 70)

    bubbles = []
    for c in cascade_descs:
        try:
            cls = c.element_info.class_name or ""
            ctype = c.element_info.control_type
            if "panel-border" in cls and ctype == "Group":
                # Collect all text inside this bubble
                bubble_texts = []
                for child in c.descendants():
                    try:
                        if child.element_info.control_type == "Text":
                            t = child.window_text() or ""
                            if t:
                                bubble_texts.append(t)
                    except:
                        pass

                # Determine role
                role = "unknown"
                if "user" in cls.lower() or "human" in cls.lower():
                    role = "user"
                elif "assistant" in cls.lower() or "ai" in cls.lower():
                    role = "assistant"

                # Check for image
                has_image = False
                for child in c.descendants():
                    try:
                        if child.element_info.control_type == "Image":
                            has_image = True
                            break
                    except:
                        pass

                full_text = " ".join(bubble_texts)[:300]
                bubbles.append((role, cls[:50], full_text, has_image, len(bubble_texts)))
        except:
            pass

    print("\nFound %d message bubbles\n" % len(bubbles))
    for i, (role, cls, text, has_img, text_count) in enumerate(bubbles[-25:]):
        icon = "USER" if role == "user" else "AI  " if role == "assistant" else "????"
        img_tag = " [HAS_IMAGE]" if has_img else ""
        print("[%s] bubble %d (%d fragments)%s" % (icon, i, text_count, img_tag))
        print("  class: %s" % cls)
        print("  text: %s" % text[:200])
        print()

    # === Input Box ===
    print("=" * 70)
    print("  Input Box")
    print("=" * 70)
    for c in cascade_descs:
        try:
            cls = c.element_info.class_name or ""
            ctype = c.element_info.control_type
            if ctype == "Edit" and "min-h" in cls:
                rect = c.rectangle()
                current_text = c.window_text() or ""
                print("  class: %s" % cls)
                print("  rect: (%d,%d,%d,%d)" % (rect.left, rect.top, rect.right, rect.bottom))
                print("  current text: '%s'" % current_text)
                print("  enabled: %s" % c.is_enabled())
                print("  visible: %s" % c.is_visible())
                break
        except:
            pass

    # === Summary ===
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    user_msgs = [b for b in bubbles if b[0] == "user"]
    ai_msgs = [b for b in bubbles if b[0] == "assistant"]
    unknown_msgs = [b for b in bubbles if b[0] == "unknown"]
    print("  User messages: %d" % len(user_msgs))
    print("  AI messages: %d" % len(ai_msgs))
    print("  Unknown messages: %d" % len(unknown_msgs))
    print("  Total: %d" % len(bubbles))
    print()
    print("  CONCLUSION: Cascade chat content is %s via UIA" % (
        "READABLE" if bubbles else "NOT readable"))


if __name__ == "__main__":
    main()
