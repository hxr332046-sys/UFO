#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Desktop Quick Control - 基于存档的轻量直达操控
无需重新遍历控件树，按 automation_id / static name 直达目标控件
"""

import json
import os
import time
import ctypes
from typing import Any, Dict, List, Optional

import pywinauto
from pywinauto import Desktop, Application
import psutil


ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), "desktop_control_archive.json")


def get_pid_from_hwnd(hwnd):
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def load_archive() -> Dict:
    """加载控件存档"""
    with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_app_window(exe_name: str, title_substring: str = ""):
    """按 exe 名和标题子串快速定位窗口（无需遍历控件树）"""
    desktop = Desktop(backend="win32")
    windows = desktop.windows()
    for w in windows:
        if not w.is_visible() or not w.window_text():
            continue
        hwnd = w.element_info.handle
        pid = get_pid_from_hwnd(hwnd)
        try:
            proc = psutil.Process(pid)
            if proc.name().lower() == exe_name.lower():
                if not title_substring or title_substring.lower() in w.window_text().lower():
                    return {"hwnd": hwnd, "pid": pid, "title": w.window_text()}
        except:
            pass
    return None


def connect_uia(pid: int, timeout: int = 5) -> Any:
    """UIA 方式连接进程"""
    return Application(backend="uia").connect(process=pid, timeout=timeout)


def control_by_auto_id(app_window, auto_id: str):
    """按 automation_id 直达控件（最快路径）"""
    try:
        ctrl = app_window.child_window(auto_id=auto_id)
        return ctrl
    except Exception as e:
        return None


def control_by_name(app_window, control_type: str, name: str):
    """按 control_type + name 直达控件"""
    try:
        ctrl = app_window.child_window(control_type=control_type, title=name)
        return ctrl
    except Exception as e:
        return None


def click_control(ctrl):
    """点击控件"""
    try:
        ctrl.click()
        return True
    except Exception as e:
        return False


def set_edit_text(ctrl, text: str):
    """设置编辑框文本"""
    try:
        ctrl.set_edit_text(text)
        return True
    except Exception as e:
        return False


def get_control_info(ctrl):
    """获取控件当前动态信息"""
    try:
        return {
            "name": ctrl.window_text()[:100],
            "control_type": ctrl.element_info.control_type,
            "class_name": ctrl.element_info.class_name,
            "enabled": ctrl.is_enabled(),
            "visible": ctrl.is_visible(),
            "rect": str(ctrl.rectangle()),
        }
    except Exception as e:
        return {"error": str(e)[:100]}


def demo_quick_operations():
    """演示：基于存档的直达操控"""
    archive = load_archive()
    
    print("=" * 70)
    print("  Quick Control Demo - 基于存档直达操控")
    print("=" * 70)
    
    # === Demo 1: Chrome 地址栏 ===
    print("\n--- Demo 1: Chrome 地址栏直达 ---")
    chrome_info = find_app_window("chrome.exe")
    if chrome_info:
        print("  找到 Chrome: PID=%d, Title=%s" % (chrome_info["pid"], chrome_info["title"][:50]))
        app = connect_uia(chrome_info["pid"])
        top_win = app.top_window()
        
        # 从存档索引直达：view_1012 = 地址栏 Edit
        start = time.time()
        addr_bar = control_by_auto_id(top_win, "view_1012")
        elapsed = time.time() - start
        
        if addr_bar:
            info = get_control_info(addr_bar)
            print("  🎯 直达地址栏: %.3fs (跳过树遍历)" % elapsed)
            print("     当前内容: %s" % info.get("name", ""))
            print("     类型: %s, 类名: %s" % (info.get("control_type"), info.get("class_name")))
        else:
            print("  ❌ 未找到地址栏")
    else:
        print("  Chrome 未运行")
    
    # === Demo 2: 任务栏快捷操作 ===
    print("\n--- Demo 2: 任务栏直达 ---")
    explorer_info = find_app_window("explorer.exe", "Program Manager")
    if explorer_info:
        print("  找到 Explorer: PID=%d" % explorer_info["pid"])
        app = connect_uia(explorer_info["pid"])
        top_win = app.top_window()
        
        # 从存档直达：开始按钮
        start_btn = control_by_name(top_win, "Button", "开始")
        if start_btn:
            info = get_control_info(start_btn)
            print("  🎯 直达开始按钮: %s" % info.get("name", ""))
        
        # 直达：显示桌面按钮 (auto_id=307)
        show_desktop = control_by_auto_id(top_win, "307")
        if show_desktop:
            info = get_control_info(show_desktop)
            print("  🎯 直达显示桌面按钮: %s" % info.get("name", ""))
        
        # 直达：微信任务栏按钮
        wechat_btn = control_by_auto_id(top_win, r"D:\Program Files\Weixin\Weixin.exe")
        if wechat_btn:
            info = get_control_info(wechat_btn)
            print("  🎯 直达微信按钮: %s" % info.get("name", "")[:60])
    else:
        print("  Explorer 未找到")
    
    # === Demo 3: 性能对比 ===
    print("\n--- Demo 3: 直达 vs 全遍历 性能对比 ---")
    if chrome_info:
        app = connect_uia(chrome_info["pid"])
        top_win = app.top_window()
        
        # 方法1: 全遍历 descendants
        t1 = time.time()
        all_ctrls = top_win.descendants()
        t_full = time.time() - t1
        print("  全遍历: %.3fs, 找到 %d 个控件" % (t_full, len(all_ctrls)))
        
        # 方法2: 按 auto_id 直达
        t2 = time.time()
        target = control_by_auto_id(top_win, "view_1012")
        t_direct = time.time() - t2
        print("  直达:   %.3fs, 找到: %s" % (t_direct, "Yes" if target else "No"))
        print("  加速比: %.1fx" % (t_full / t_direct if t_direct > 0 else 999))
    
    # === Demo 4: 存档索引统计 ===
    print("\n--- 存档索引统计 ---")
    total_auto_ids = 0
    total_static_names = 0
    for app_key, app_data in archive["applications"].items():
        qi = app_data.get("quick_index", {})
        aids = qi.get("by_auto_id", {})
        snames = qi.get("by_static_name", {})
        total_auto_ids += len(aids)
        total_static_names += len(snames)
        if aids or snames:
            print("  %s: %d auto_ids, %d static_names" % (
                app_data.get("exe", "?"), len(aids), len(snames)))
    
    print("\n  总计: %d 个直达锚点 (auto_id), %d 个快捷定位 (static_name)" % (
        total_auto_ids, total_static_names))
    print("  运行时只需: find_app_window → connect_uia → control_by_auto_id")
    print("  无需: descendants() 全树遍历")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    demo_quick_operations()
