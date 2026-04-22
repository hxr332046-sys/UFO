#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze Windsurf Cascade chat structure - identify user vs AI messages."""

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

    app = Application(backend="uia").connect(process=target_pid, timeout=5)
    top_win = app.top_window()

    # Find cascade scrollbar (parent of all messages)
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

    # Get scrollbar
    scrollbar = None
    for c in cascade_root.descendants():
        try:
            if "cascade-scrollbar" in (c.element_info.class_name or ""):
                scrollbar = c
                break
        except:
            pass

    if not scrollbar:
        print("Scrollbar not found")
        return

    # Direct children of scrollbar = message wrappers
    children = scrollbar.descendants(depth=1)
    print("Scrollbar direct children: %d" % len(children))
    print()

    # Filter to find message wrapper groups (not individual text nodes)
    message_wrappers = []
    for child in children:
        try:
            cls = child.element_info.class_name or ""
            ctype = child.element_info.control_type
            # Message wrappers are Groups with specific class patterns
            if ctype == "Group" and cls and len(cls) > 10:
                # Get text content
                texts = []
                for d in child.descendants():
                    try:
                        if d.element_info.control_type == "Text" and d.window_text():
                            texts.append(d.window_text())
                    except:
                        pass
                
                # Check for images
                has_img = any(
                    d.element_info.control_type == "Image"
                    for d in child.descendants()
                    if hasattr(d, "element_info")
                )
                
                # Determine role from class name
                role = "???"
                cls_lower = cls.lower()
                if "user" in cls_lower or "human" in cls_lower:
                    role = "USER"
                elif "bot" in cls_lower or "assistant" in cls_lower:
                    role = "AI"
                
                # Also check: short text + has_image = likely user
                # long text + code blocks = likely AI
                if role == "???":
                    if has_img and len(texts) <= 2:
                        role = "USER(guess)"
                    elif len(texts) > 10:
                        role = "AI(guess)"
                    elif len(texts) <= 2 and texts:
                        role = "USER(guess)"
                    else:
                        role = "AI(guess)"
                
                full_text = " ".join(texts)[:200]
                message_wrappers.append({
                    "role": role,
                    "cls": cls[:80],
                    "text_count": len(texts),
                    "has_img": has_img,
                    "preview": full_text,
                })
        except:
            pass

    print("=" * 70)
    print("  Cascade Chat Messages (%d)" % len(message_wrappers))
    print("=" * 70)
    print()

    for i, m in enumerate(message_wrappers):
        icon = "USER" if "USER" in m["role"] else "AI  "
        img_tag = " [IMG]" if m["has_img"] else ""
        print("[%s] msg %d (%d texts)%s" % (icon, i, m["text_count"], img_tag))
        print("  class: %s" % m["cls"])
        print("  text: %s" % m["preview"][:150])
        print()

    # Also check: can we find the input box and type into it?
    print("=" * 70)
    print("  Input Box Test")
    print("=" * 70)
    for c in cascade_root.descendants():
        try:
            cls = c.element_info.class_name or ""
            ctype = c.element_info.control_type
            if ctype == "Edit" and "min-h" in cls:
                rect = c.rectangle()
                print("  Found input: class=%s" % cls)
                print("  Position: (%d,%d,%d,%d)" % (rect.left, rect.top, rect.right, rect.bottom))
                print("  Current text: '%s'" % (c.window_text() or ""))
                print("  Enabled: %s, Visible: %s" % (c.is_enabled(), c.is_visible()))
                print()
                print("  >>> This input box is ACCESSIBLE for writing messages!")
                break
        except:
            pass


if __name__ == "__main__":
    main()
