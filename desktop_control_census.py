#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Desktop Control Census - 一次性普查所有桌面程序的控件树并存档
存档内容：控件结构、Automation ID、Control Type、Class Name、名称模式
运行时：按 automation_id / name / class 直达目标控件，跳过整棵树遍历
"""

import json
import os
import time
import ctypes
import psutil
from datetime import datetime
from typing import Any, Dict, List, Optional

import pywinauto
from pywinauto import Desktop, Application


def get_pid_from_hwnd(hwnd):
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def safe_get_attr(obj, attr, default=""):
    try:
        val = getattr(obj, attr, default)
        if val is None:
            return default
        return str(val)
    except Exception:
        return default


def census_control_tree(wrapper, depth=0, max_depth=3, max_children=15, start_time=None, timeout=30):
    """递归普查控件树，提取静态可存档信息"""
    if depth > max_depth:
        return None

    # 超时保护
    if start_time is None:
        start_time = time.time()
    if time.time() - start_time > timeout:
        return None

    try:
        info = wrapper.element_info
    except Exception:
        return None

    node = {
        "control_type": safe_get_attr(info, "control_type"),
        "class_name": safe_get_attr(info, "class_name"),
        "automation_id": safe_get_attr(info, "automation_id", ""),
        "name": "",  # 动态，仅存模式
        "name_pattern": "",  # 静态标记
        "rect": "",  # 动态，不存具体值
        "enabled": True,
        "visible": True,
        "children": [],
    }

    # 获取名称（标记是否为动态内容）
    try:
        name = wrapper.window_text()
        node["name"] = name[:100] if name else ""
        # 判断名称是否为静态标签（按钮文字、菜单名等）
        ctype = node["control_type"]
        if ctype in ("MenuItem", "Button", "TabItem", "Text", "CheckBox",
                      "RadioButton", "ListItem", "TreeItem", "Group",
                      "ToolBar", "Separator", "Menu", "TitleBar"):
            node["name_pattern"] = "static"  # 静态标签
        elif ctype in ("Edit", "Document", "DataItem", "DataGrid",
                        "Table", "List", "Tree"):
            node["name_pattern"] = "dynamic"  # 动态内容
        else:
            node["name_pattern"] = "semi"  # 半静态
    except Exception:
        pass

    # enabled / visible
    try:
        node["enabled"] = wrapper.is_enabled()
    except Exception:
        pass
    try:
        node["visible"] = wrapper.is_visible()
    except Exception:
        pass

    # 递归子控件（仅取直接子节点，depth=1）
    try:
        children = wrapper.descendants(depth=1)
        # 过滤掉自身
        children = [c for c in children if c.element_info != info]
        for child in children[:max_children]:
            if time.time() - start_time > timeout:
                node["children_truncated"] = True
                break
            child_node = census_control_tree(child, depth + 1, max_depth, max_children, start_time, timeout)
            if child_node:
                node["children"].append(child_node)
    except Exception:
        pass

    return node


def census_window(pid, exe_name):
    """普查一个进程的顶层窗口控件树"""
    try:
        app = Application(backend="uia").connect(process=pid, timeout=5)
        top_win = app.top_window()
    except Exception as e:
        return {"error": str(e)[:200]}

    # 获取顶层窗口信息
    try:
        title = top_win.window_text()
        cls = top_win.element_info.class_name
        auto_id = safe_get_attr(top_win.element_info, "automation_id", "")
    except Exception:
        return {"error": "Cannot read top window info"}

    # 普查控件树（浅层遍历+超时保护）
    tree = census_control_tree(top_win, depth=0, max_depth=3, max_children=15, timeout=20)

    # 统计
    stats = count_controls(tree) if tree else {}

    return {
        "title": title[:100],
        "class_name": cls,
        "automation_id": auto_id,
        "control_tree": tree,
        "stats": stats,
    }


def count_controls(node):
    """统计控件类型分布"""
    counts = {}
    _count_recursive(node, counts)
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _count_recursive(node, counts):
    if not node or not isinstance(node, dict):
        return
    ct = node.get("control_type", "Unknown")
    counts[ct] = counts.get(ct, 0) + 1
    for child in node.get("children", []):
        _count_recursive(child, counts)


def build_quick_index(tree, path=""):
    """构建快速索引：automation_id → 路径, name → 路径"""
    index = {"by_auto_id": {}, "by_static_name": {}, "by_class": {}}
    _build_index(tree, path, index)
    return index


def _build_index(node, path, index):
    if not node or not isinstance(node, dict):
        return
    ct = node.get("control_type", "")
    aid = node.get("automation_id", "")
    name = node.get("name", "")
    cls = node.get("class_name", "")
    name_pat = node.get("name_pattern", "")
    current_path = f"{path}/{ct}" + (f"[{aid}]" if aid else f"[{name}]" if name and name_pat == "static" else "")

    if aid:
        index["by_auto_id"][aid] = {
            "path": current_path,
            "control_type": ct,
            "class_name": cls,
        }
    if name and name_pat == "static":
        key = f"{ct}:{name}"
        index["by_static_name"][key] = {
            "path": current_path,
            "automation_id": aid,
            "class_name": cls,
        }
    if cls and ct:
        key = f"{ct}:{cls}"
        if key not in index["by_class"]:
            index["by_class"][key] = {
                "path": current_path,
                "automation_id": aid,
                "name": name,
            }

    for child in node.get("children", []):
        _build_index(child, current_path, index)


def main():
    print("=" * 70)
    print("  Desktop Control Census - 控件普查存档")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 获取所有可见窗口
    desktop = Desktop(backend="win32")
    windows = desktop.windows()
    visible = [w for w in windows if w.is_visible() and w.window_text()]

    # 按 PID 去重（同一进程只普查一次顶层窗口）
    seen_pids = set()
    apps = []
    for w in visible:
        hwnd = w.element_info.handle
        pid = get_pid_from_hwnd(hwnd)
        if pid in seen_pids:
            continue
        seen_pids.add(pid)

        try:
            proc = psutil.Process(pid)
            exe = proc.name()
        except Exception:
            exe = "unknown"

        title = w.window_text()
        cls = w.element_info.class_name
        apps.append({
            "pid": pid,
            "exe": exe,
            "title": title[:100],
            "class_name": cls,
        })

    print(f"\nFound {len(apps)} unique application processes\n")

    # 普查每个应用
    archive = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_apps": len(apps),
            "description": "Desktop control census - static info for quick reconnect. PID/HWND are reference-only (change on reboot). Use exe name + auto_id/static_name for runtime lookup.",
        },
        "applications": {},
    }

    for i, app_info in enumerate(apps):
        pid = app_info["pid"]
        exe = app_info["exe"]
        title = app_info["title"]

        print(f"[{i+1}/{len(apps)}] Census: {exe} (PID={pid}) — {title[:50]}")

        result = census_window(pid, exe)
        result["pid"] = pid
        result["exe"] = exe
        result["title"] = title

        # 构建快速索引
        if result.get("control_tree"):
            result["quick_index"] = build_quick_index(result["control_tree"])
        else:
            result["quick_index"] = {"by_auto_id": {}, "by_static_name": {}, "by_class": {}}

        # Key by exe name (PID changes on reboot, exe name is stable)
        # If multiple instances of same exe, append title hint
        app_key = exe
        if app_key in archive["applications"]:
            # Multiple instances: differentiate by title keyword
            title_hint = title.split(" - ")[0].split(" ")[0][:20]
            app_key = f"{exe}__{title_hint}"
        result["pid_at_census"] = pid  # Reference only, changes on reboot
        archive["applications"][app_key] = result

        stats = result.get("stats", {})
        if stats:
            top3 = list(stats.items())[:3]
            total = sum(stats.values())
            print(f"    → {total} controls, top: {top3}")
        elif result.get("error"):
            print(f"    → Error: {result['error'][:60]}")

    # 保存存档
    output_path = os.path.join(os.path.dirname(__file__), "desktop_control_archive.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'=' * 70}")
    print(f"  Archive saved: {output_path}")

    # 打印摘要
    total_controls = 0
    total_auto_ids = 0
    total_static_names = 0
    for app_key, app_data in archive["applications"].items():
        stats = app_data.get("stats", {})
        total_controls += sum(stats.values())
        qi = app_data.get("quick_index", {})
        total_auto_ids += len(qi.get("by_auto_id", {}))
        total_static_names += len(qi.get("by_static_name", {}))

    print(f"\n  📊 Census Summary:")
    print(f"     Applications: {len(archive['applications'])}")
    print(f"     Total controls: {total_controls}")
    print(f"     Automation IDs (直达锚点): {total_auto_ids}")
    print(f"     Static names (快捷定位): {total_static_names}")
    print(f"\n  💡 Usage: 运行时按 automation_id 或 static name 直达控件")
    print(f"     无需重新遍历整棵控件树")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
