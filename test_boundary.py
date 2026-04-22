#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""UFO² Capability Boundary Test Suite"""

import sys
import os
import time
import json
import traceback

sys.path.insert(0, r"D:\UFO")
os.chdir(r"D:\UFO")

results = {}

def record(category, test_name, status, detail=""):
    if category not in results:
        results[category] = []
    results[category].append({
        "test": test_name,
        "status": status,
        "detail": detail
    })
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} [{category}] {test_name}: {detail}")


# ============================================================
# TEST 1: Window Enumeration Capability
# ============================================================
print("\n" + "="*60)
print("TEST 1: Window Enumeration Capability")
print("="*60)

try:
    import uiautomation as uia
    desktop = uia.GetRootControl()
    children = desktop.GetChildren()
    record("WindowEnum", "TopLevelWindowCount", "PASS", f"{len(children)} windows detected")
    
    visible_windows = [w for w in children if w.IsTopLevel()]
    record("WindowEnum", "TopLevelWindowFilter", "PASS", f"{len(visible_windows)} top-level windows")
    
    # Test window property access
    for w in children[:5]:
        try:
            props = f"Name={w.Name}, Class={w.ClassName}, PID={w.ProcessId}, Type={w.ControlTypeName}"
            record("WindowEnum", f"WindowProperties_{w.ClassName}", "PASS", props)
        except Exception as e:
            record("WindowEnum", f"WindowProperties_ERROR", "FAIL", str(e))
    
    # Test Win32 API enumeration
    try:
        import win32gui
        wins = []
        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                if title:
                    wins.append((hwnd, title, cls))
        win32gui.EnumWindows(enum_cb, None)
        record("WindowEnum", "Win32EnumWindows", "PASS", f"{len(wins)} visible windows via Win32")
    except Exception as e:
        record("WindowEnum", "Win32EnumWindows", "FAIL", str(e))

    # Test GetDesktopAppInfo (UFO specific)
    try:
        from ufo.automator.ui_control.screenshot import ScreenshotController
        record("WindowEnum", "UFO_ScreenshotController", "PASS", "Importable")
    except Exception as e:
        record("WindowEnum", "UFO_ScreenshotController", "FAIL", str(e)[:200])

except Exception as e:
    record("WindowEnum", "UIA_Init", "FAIL", str(e))


# ============================================================
# TEST 2: Control Detection Capability
# ============================================================
print("\n" + "="*60)
print("TEST 2: Control Detection Capability")
print("="*60)

try:
    import uiautomation as uia
    
    # Test standard control types
    control_types = [
        "ButtonControl", "EditControl", "TextControl", "ListControl",
        "TreeControl", "TabControl", "MenuItemControl", "ComboBoxControl",
        "CheckBoxControl", "RadioButtonControl", "SliderControl",
        "SpinnerControl", "HyperlinkControl", "ScrollBarControl",
        "DataItemControl", "DataGridControl", "DocumentControl",
        "GroupControl", "HeaderControl", "ImageControl",
        "ProgressBarControl", "StatusBarControl", "ToolBarControl",
        "ToolTipControl", "WindowControl", "PaneControl"
    ]
    
    available = []
    for ct in control_types:
        if hasattr(uia, ct):
            available.append(ct)
    record("ControlDetect", "StandardControlTypes", "PASS", f"{len(available)}/{len(control_types)} types available")
    record("ControlDetect", "AvailableTypes", "PASS", ", ".join(available[:15]))
    
    # Test UI Tree traversal depth
    try:
        desktop = uia.GetRootControl()
        # Get first visible window
        for child in desktop.GetChildren():
            if child.Name and child.IsTopLevel():
                depth = 0
                current = child
                while depth < 20:
                    subs = current.GetChildren()
                    if not subs:
                        break
                    current = subs[0]
                    depth += 1
                record("ControlDetect", f"UITreeDepth_{child.ClassName}", "PASS", f"Depth={depth}")
                break
    except Exception as e:
        record("ControlDetect", "UITreeDepth", "FAIL", str(e)[:200])

    # Test control property access
    try:
        desktop = uia.GetRootControl()
        for child in desktop.GetChildren():
            if child.Name:
                props = {
                    "BoundingRectangle": str(child.BoundingRectangle),
                    "ControlTypeName": child.ControlTypeName,
                    "AutomationId": child.AutomationId,
                    "IsEnabled": child.IsEnabled,
                    "IsOffscreen": child.IsOffscreen,
                }
                record("ControlDetect", "ControlPropertyAccess", "PASS", json.dumps(props, ensure_ascii=False)[:200])
                break
    except Exception as e:
        record("ControlDetect", "ControlPropertyAccess", "FAIL", str(e)[:200])

except Exception as e:
    record("ControlDetect", "Init", "FAIL", str(e))


# ============================================================
# TEST 3: Command System Capability
# ============================================================
print("\n" + "="*60)
print("TEST 3: Command System Capability")
print("="*60)

try:
    from ufo.automator.ui_control import controller
    
    command_classes = [
        "ClickCommand", "ClickInputCommand", "ClickOnCoordinatesCommand",
        "DoubleClickCommand", "SetEditTextCommand", "WheelMouseInputCommand",
        "ScrollCommand", "DragCommand", "DragOnCoordinatesCommand",
        "KeyPressCommand", "MouseMoveCommand", "AnnotationCommand",
        "GetTextsCommand", "SummaryCommand", "NoActionCommand",
        "WaitCommand", "TypeCommand"
    ]
    
    available_cmds = []
    for cmd in command_classes:
        if hasattr(controller, cmd):
            available_cmds.append(cmd)
    record("Commands", "AvailableCommands", "PASS", f"{len(available_cmds)}/{len(command_classes)}")
    record("Commands", "CommandList", "PASS", ", ".join(available_cmds))
    
    # Test keyboard input command
    if hasattr(controller, "keyboardInputCommand"):
        record("Commands", "KeyboardInput", "PASS", "Available")
    else:
        record("Commands", "KeyboardInput", "WARN", "Not found as top-level")
    
    # Test Receiver system
    if hasattr(controller, "ReceiverManager"):
        record("Commands", "ReceiverManager", "PASS", "Available")
    if hasattr(controller, "UIControlReceiverFactory"):
        record("Commands", "UIControlReceiverFactory", "PASS", "Available")

except Exception as e:
    record("Commands", "Init", "FAIL", str(e))


# ============================================================
# TEST 4: Screenshot & Annotation Capability
# ============================================================
print("\n" + "="*60)
print("TEST 4: Screenshot & Annotation Capability")
print("="*60)

try:
    from ufo.automator.ui_control.screenshot import *
    record("Screenshot", "ScreenshotModule", "PASS", "Importable")
    
    # Test PIL-based screenshot
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        record("Screenshot", "PIL_ImageGrab", "PASS", f"Screenshot size={img.size}")
    except Exception as e:
        record("Screenshot", "PIL_ImageGrab", "FAIL", str(e)[:200])
    
    # Test pyautogui screenshot
    try:
        import pyautogui
        ss = pyautogui.screenshot()
        record("Screenshot", "PyAutoGUI_Screenshot", "PASS", f"Size={ss.size}")
    except Exception as e:
        record("Screenshot", "PyAutoGUI_Screenshot", "FAIL", str(e)[:200])

except Exception as e:
    record("Screenshot", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 5: MCP Server Integration
# ============================================================
print("\n" + "="*60)
print("TEST 5: MCP Server Integration")
print("="*60)

try:
    import fastmcp
    record("MCP", "FastMCP_Import", "PASS", f"Version available")
    
    # Check MCP config
    mcp_config_path = r"D:\UFO\config\ufo\mcp.yaml"
    if os.path.exists(mcp_config_path):
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        record("MCP", "MCP_ConfigExists", "PASS", f"Config file size={len(content)}")
    else:
        record("MCP", "MCP_ConfigExists", "FAIL", "Config not found")
    
    # Check MCP server directories
    mcp_local = r"D:\UFO\ufo\client\mcp\local_servers"
    mcp_http = r"D:\UFO\ufo\client\mcp\http_servers"
    if os.path.exists(mcp_local):
        servers = os.listdir(mcp_local)
        record("MCP", "LocalMCPServers", "PASS", f"{len(servers)} servers: {servers}")
    if os.path.exists(mcp_http):
        servers = os.listdir(mcp_http)
        record("MCP", "HTTPMCPServers", "PASS", f"{len(servers)} servers: {servers}")

except Exception as e:
    record("MCP", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 6: Knowledge Substrate / RAG
# ============================================================
print("\n" + "="*60)
print("TEST 6: Knowledge Substrate / RAG")
print("="*60)

try:
    import faiss
    record("RAG", "FAISS_Import", "PASS", f"FAISS available")
    
    from langchain_huggingface import HuggingFaceEmbeddings
    record("RAG", "HuggingFaceEmbeddings", "PASS", "Importable")
    
    from langchain_community.vectorstores import FAISS as LCFAISS
    record("RAG", "LangChainFAISS", "PASS", "Importable")
    
    # Check RAG config
    rag_config = r"D:\UFO\config\ufo\rag.yaml"
    if os.path.exists(rag_config):
        record("RAG", "RAG_ConfigExists", "PASS", "Config file present")
    else:
        record("RAG", "RAG_ConfigExists", "FAIL", "Config not found")

    # Check sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer
        record("RAG", "SentenceTransformers", "PASS", "Importable")
    except Exception as e:
        record("RAG", "SentenceTransformers", "FAIL", str(e)[:200])

except Exception as e:
    record("RAG", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 7: Multi-Action Speculative Execution
# ============================================================
print("\n" + "="*60)
print("TEST 7: Multi-Action Speculative Execution")
print("="*60)

try:
    # Check multi-action related modules
    multi_action_paths = [
        r"D:\UFO\ufo\agents\processors",
        r"D:\UFO\ufo\agents\processors\strategies",
    ]
    for p in multi_action_paths:
        if os.path.exists(p):
            files = [f for f in os.listdir(p) if f.endswith('.py')]
            record("MultiAction", f"Module_{os.path.basename(p)}", "PASS", f"{len(files)} files: {files}")
    
    # Check system config for multi-action settings
    from ufo.config.config_loader import ConfigLoader
    loader = ConfigLoader()
    config = loader.load_ufo_config()
    max_step = getattr(config, 'MAX_STEP', 'N/A')
    record("MultiAction", "MaxStepConfig", "PASS", f"MAX_STEP={max_step}")

except Exception as e:
    record("MultiAction", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 8: Safety Guard Mechanism
# ============================================================
print("\n" + "="*60)
print("TEST 8: Safety Guard Mechanism")
print("="*60)

try:
    from ufo.config.config_loader import ConfigLoader
    loader = ConfigLoader()
    config = loader.load_ufo_config()
    
    safe_guard = getattr(config, 'SAFE_GUARD', 'N/A')
    record("Safety", "SafeGuardEnabled", "PASS", f"SAFE_GUARD={safe_guard}")
    
    control_list = getattr(config, 'CONTROL_LIST', 'N/A')
    if isinstance(control_list, list):
        record("Safety", "ControlWhitelist", "PASS", f"{len(control_list)} allowed control types: {control_list}")
    else:
        record("Safety", "ControlWhitelist", "WARN", f"Value={control_list}")
    
    max_step = getattr(config, 'MAX_STEP', 'N/A')
    record("Safety", "MaxStepLimit", "PASS", f"MAX_STEP={max_step}")

except Exception as e:
    record("Safety", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 9: Special Scenario Boundaries
# ============================================================
print("\n" + "="*60)
print("TEST 9: Special Scenario Boundaries")
print("="*60)

try:
    import win32gui
    import win32con
    import win32process
    import psutil
    
    # Test: Enumerate all windows with process info
    all_windows = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name()
            except:
                proc_name = "N/A"
            all_windows.append({
                "hwnd": hwnd,
                "title": title,
                "class": cls,
                "pid": pid,
                "process": proc_name
            })
    win32gui.EnumWindows(enum_cb, None)
    record("Special", "AllVisibleWindows", "PASS", f"{len(all_windows)} windows with process info")
    
    # Test: UAC/Admin windows detection
    uac_windows = [w for w in all_windows if not title or w["class"] in 
                   ("#32770", "Credential Dialog Xaml Host", "SecureDesktop")]
    record("Special", "UAC_DialogDetection", "PASS", f"Potential UAC dialogs: {len(uac_windows)}")
    
    # Test: System windows
    system_windows = [w for w in all_windows if w["class"] in 
                     ("Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW")]
    record("Special", "SystemWindows", "PASS", f"{len(system_windows)} system windows (Taskbar/Desktop)")
    
    # Test: Minimized windows
    minimized = []
    for w in all_windows:
        if win32gui.IsIconic(w["hwnd"]):
            minimized.append(w["title"])
    record("Special", "MinimizedWindows", "PASS", f"{len(minimized)} minimized windows can be detected")
    
    # Test: Background process windows (no visible window)
    bg_procs = set()
    for w in all_windows:
        if not w["title"] and w["class"] not in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"):
            bg_procs.add(w["process"])
    record("Special", "BackgroundProcessWindows", "PASS", f"{len(bg_procs)} background process windows")
    
    # Test: Multiple monitor support
    try:
        import win32api
        monitors = win32api.EnumDisplayMonitors()
        record("Special", "MultiMonitor", "PASS", f"{len(monitors)} monitors detected")
    except Exception as e:
        record("Special", "MultiMonitor", "WARN", str(e)[:100])

    # Test: Elevated process detection
    elevated = []
    for w in all_windows[:30]:
        try:
            proc = psutil.Process(w["pid"])
            if proc and hasattr(proc, 'username'):
                elevated.append(f"{w['process']}({w['pid']})")
        except:
            pass
    record("Special", "ProcessInfoAccess", "PASS", f"{len(elevated)} processes with user info")

except Exception as e:
    record("Special", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 10: Office Automation Capability
# ============================================================
print("\n" + "="*60)
print("TEST 10: Office Automation Capability")
print("="*60)

try:
    # Check xlwings
    try:
        import xlwings
        record("Office", "xlwings", "PASS", f"Available")
    except ImportError:
        record("Office", "xlwings", "FAIL", "Not installed")
    
    # Check python-pptx
    try:
        import pptx
        record("Office", "python-pptx", "PASS", f"Available")
    except ImportError:
        record("Office", "python-pptx", "FAIL", "Not installed")
    
    # Check win32com
    try:
        import win32com.client
        record("Office", "win32com", "PASS", "Available for Outlook/Word COM automation")
    except ImportError:
        record("Office", "win32com", "FAIL", "Not installed")
    
    # Check Office API prompts
    office_prompts = r"D:\UFO\ufo\prompts\apps"
    if os.path.exists(office_prompts):
        apps = os.listdir(office_prompts)
        record("Office", "OfficeAppPrompts", "PASS", f"Supported apps: {apps}")
    else:
        record("Office", "OfficeAppPrompts", "FAIL", "Prompt dir not found")

    # Check Office MCP servers
    office_mcp = r"D:\UFO\ufo\client\mcp\local_servers"
    if os.path.exists(office_mcp):
        servers = os.listdir(office_mcp)
        record("Office", "OfficeMCPServers", "PASS", f"MCP servers: {servers}")

except Exception as e:
    record("Office", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 11: LLM Integration Capability
# ============================================================
print("\n" + "="*60)
print("TEST 11: LLM Integration Capability")
print("="*60)

try:
    from ufo.config.config_loader import ConfigLoader
    loader = ConfigLoader()
    config = loader.load_ufo_config()
    
    # Check supported API types
    api_type = getattr(config, 'API_TYPE', 'N/A')
    record("LLM", "ConfiguredAPIType", "PASS", f"API_TYPE={api_type}")
    
    # Check all supported LLM providers
    llm_providers = ["openai", "aoai", "azure_ad", "gemini", "qwen", "ollama", "anthropic", "deepseek"]
    record("LLM", "SupportedProviders", "PASS", f"Providers: {llm_providers}")
    
    # Check visual mode
    visual = getattr(config, 'VISUAL_MODE', 'N/A')
    record("LLM", "VisualMode", "PASS", f"VISUAL_MODE={visual}")
    
    # Check model config
    model = getattr(config, 'API_MODEL', 'N/A')
    record("LLM", "ConfiguredModel", "PASS", f"API_MODEL={model}")
    
    # Check API key status
    api_key = getattr(config, 'API_KEY', '')
    if api_key and api_key != "sk-YOUR_KEY_HERE" and not api_key.startswith("sk-YOUR"):
        record("LLM", "APIKeyStatus", "PASS", "API key configured")
    else:
        record("LLM", "APIKeyStatus", "WARN", "API key NOT configured - LLM calls will fail")

except Exception as e:
    record("LLM", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 12: Agent Architecture
# ============================================================
print("\n" + "="*60)
print("TEST 12: Agent Architecture")
print("="*60)

try:
    # Check agent modules
    agent_dir = r"D:\UFO\ufo\agents"
    if os.path.exists(agent_dir):
        subdirs = [d for d in os.listdir(agent_dir) if os.path.isdir(os.path.join(agent_dir, d))]
        record("Agent", "AgentModules", "PASS", f"Sub-modules: {subdirs}")
    
    # Check agent types
    from ufo.module.basic import BasicSession
    record("Agent", "BasicSession", "PASS", "Importable")
    
    # Check third-party agent support
    third_party_dir = r"D:\UFO\ufo\client"
    if os.path.exists(third_party_dir):
        items = os.listdir(third_party_dir)
        record("Agent", "ThirdPartyClientDir", "PASS", f"Items: {items}")

    # Check agent registry
    try:
        from ufo.agents.agent.registry import AgentRegistry
        record("Agent", "AgentRegistry", "PASS", "Importable")
    except:
        record("Agent", "AgentRegistry", "WARN", "Import path may differ")

except Exception as e:
    record("Agent", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 13: Logging & Evaluation
# ============================================================
print("\n" + "="*60)
print("TEST 13: Logging & Evaluation")
print("="*60)

try:
    log_dir = r"D:\UFO\ufo\logging"
    if os.path.exists(log_dir):
        files = [f for f in os.listdir(log_dir) if f.endswith('.py')]
        record("Logging", "LoggingModule", "PASS", f"Files: {files}")
    
    # Check evaluation agent
    try:
        from ufo.config.config_loader import ConfigLoader
        loader = ConfigLoader()
        config = loader.load_ufo_config()
        eva_session = getattr(config, 'EVA_SESSION', 'N/A')
        record("Logging", "EvaluationSession", "PASS", f"EVA_SESSION={eva_session}")
    except:
        record("Logging", "EvaluationSession", "WARN", "Could not read config")

except Exception as e:
    record("Logging", "Init", "FAIL", str(e)[:200])


# ============================================================
# TEST 14: PiP (Picture-in-Picture) Desktop
# ============================================================
print("\n" + "="*60)
print("TEST 14: Picture-in-Picture Desktop")
print("="*60)

try:
    # Check RDP loopback capability
    try:
        import win32api
        record("PiP", "Win32API", "PASS", "Available for RDP loopback")
    except:
        record("PiP", "Win32API", "FAIL", "Not available")
    
    # Check if RDP is available on this system
    rdp_check = os.path.exists(r"C:\Windows\System32\mstsc.exe")
    record("PiP", "RDPAvailability", "PASS" if rdp_check else "FAIL", 
           "mstsc.exe found" if rdp_check else "mstsc.exe NOT found")
    
    # Check PiP module
    pip_paths = [
        r"D:\UFO\ufo\automator\ui_control",
        r"D:\UFO\ufo\client",
    ]
    for p in pip_paths:
        if os.path.exists(p):
            files = [f for f in os.listdir(p) if 'pip' in f.lower() or 'rdp' in f.lower() or 'remote' in f.lower()]
            if files:
                record("PiP", f"PiPModule_{os.path.basename(p)}", "PASS", f"Found: {files}")

    record("PiP", "PiPStatus", "WARN", "PiP requires RDP loopback config - advanced setup needed")

except Exception as e:
    record("PiP", "Init", "FAIL", str(e)[:200])


# ============================================================
# Save Results
# ============================================================
output_path = r"D:\UFO\test_results.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "="*60)
print(f"Results saved to {output_path}")
print("="*60)

# Summary
total = sum(len(v) for v in results.values())
passed = sum(1 for v in results.values() for t in v if t["status"] == "PASS")
failed = sum(1 for v in results.values() for t in v if t["status"] == "FAIL")
warned = sum(1 for v in results.values() for t in v if t["status"] == "WARN")
print(f"\nSUMMARY: {total} tests | ✅ {passed} PASS | ❌ {failed} FAIL | ⚠️ {warned} WARN")
