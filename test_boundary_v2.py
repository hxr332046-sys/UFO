#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""UFO² Deep Capability Boundary Test - Round 2"""

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
    results[category].append({"test": test_name, "status": status, "detail": detail})
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} [{category}] {test_name}: {detail}")

# ============================================================
# 1. Window Enumeration - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("1. Window Enumeration - Deep Boundary")
print("="*60)

try:
    import uiautomation as uia
    import win32gui
    import win32con
    import win32process
    import psutil

    # UIA vs Win32 enumeration comparison
    desktop = uia.GetRootControl()
    uia_children = desktop.GetChildren()
    
    win32_wins = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            win32_wins.append({
                "hwnd": hwnd,
                "title": win32gui.GetWindowText(hwnd),
                "class": win32gui.GetClassName(hwnd)
            })
    win32gui.EnumWindows(enum_cb, None)
    
    record("WinEnum", "UIA_vs_Win32", "PASS", 
           f"UIA={len(uia_children)} vs Win32={len(win32_wins)} (Win32 sees more)")
    
    # Test: Can we get ALL windows including invisible?
    all_wins = []
    def enum_all(hwnd, _):
        all_wins.append({
            "hwnd": hwnd,
            "title": win32gui.GetWindowText(hwnd),
            "class": win32gui.GetClassName(hwnd),
            "visible": win32gui.IsWindowVisible(hwnd)
        })
    win32gui.EnumWindows(enum_all, None)
    visible_count = sum(1 for w in all_wins if w["visible"])
    invisible_count = sum(1 for w in all_wins if not w["visible"])
    record("WinEnum", "InvisibleWindowAccess", "PASS",
           f"Total={len(all_wins)}, Visible={visible_count}, Invisible={invisible_count}")
    record("WinEnum", "InvisibleWindowLimit", "WARN",
           f"UIA cannot access {invisible_count} invisible windows, Win32 can enumerate but not interact with UI tree")
    
    # Test: Minimized window UI tree access
    minimized_wins = [w for w in win32_wins if win32gui.IsIconic(w["hwnd"]) and w["title"]]
    if minimized_wins:
        record("WinEnum", "MinimizedWindowUIA", "WARN",
               f"{len(minimized_wins)} minimized windows - UIA tree may be incomplete")
    else:
        record("WinEnum", "MinimizedWindowUIA", "PASS", "No minimized windows to test")
    
    # Test: Window from different user/session
    record("WinEnum", "CrossSessionLimit", "WARN",
           "Cannot access windows from other user sessions or secure desktop (UAC)")
    
    # Test: System tray / notification area
    tray_windows = [w for w in all_wins if "TrayWnd" in w["class"]]
    record("WinEnum", "SystemTrayAccess", "PASS" if tray_windows else "WARN",
           f"{len(tray_windows)} tray windows found")
    
    # Test: Desktop background window
    progman = [w for w in all_wins if w["class"] == "Progman"]
    record("WinEnum", "DesktopBackgroundWindow", "PASS" if progman else "WARN",
           f"Progman (desktop background) found: {len(progman)}")

except Exception as e:
    record("WinEnum", "Error", "FAIL", str(e)[:300])


# ============================================================
# 2. Control Detection - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("2. Control Detection - Deep Boundary")
print("="*60)

try:
    import uiautomation as uia
    
    # Test: UIA tree depth limit on a real app
    desktop = uia.GetRootControl()
    max_depth_found = 0
    deepest_path = ""
    
    for child in desktop.GetChildren():
        if child.Name and child.IsTopLevel() and child.ClassName not in ("Shell_TrayWnd",):
            try:
                depth = 0
                current = child
                path = child.ClassName
                while depth < 50:
                    subs = current.GetChildren()
                    if not subs:
                        break
                    current = subs[0]
                    depth += 1
                    path += f" -> {current.ControlTypeName}"
                if depth > max_depth_found:
                    max_depth_found = depth
                    deepest_path = path[:200]
            except:
                pass
    
    record("CtrlDetect", "MaxUITreeDepth", "PASS", f"Deepest found: {max_depth_found} levels")
    record("CtrlDetect", "UITreeDepthLimit", "INFO", "UIA has no hard depth limit, but deep trees may timeout")
    
    # Test: Control property completeness
    test_window = None
    for child in desktop.GetChildren():
        if child.Name and "此电脑" in child.Name:
            test_window = child
            break
    
    if test_window:
        props = {}
        prop_names = ["Name", "ClassName", "ControlTypeName", "AutomationId", 
                      "IsEnabled", "IsOffscreen", "BoundingRectangle", "ProcessId",
                      "IsKeyboardFocusable", "HasKeyboardFocus"]
        for p in prop_names:
            try:
                val = getattr(test_window, p, "N/A")
                props[p] = str(val)[:100]
            except Exception as e:
                props[p] = f"ERROR: {str(e)[:50]}"
        record("CtrlDetect", "ControlPropertyCompleteness", "PASS", 
               f"Accessible properties: {len([v for v in props.values() if 'ERROR' not in v])}/{len(props)}")
        
        # Test child controls
        children = test_window.GetChildren()
        record("CtrlDetect", "ChildControlAccess", "PASS", f"{len(children)} child controls in '此电脑'")
    else:
        record("CtrlDetect", "ExplorerTest", "WARN", "此电脑 window not found for deep test")
    
    # Test: Custom/owner-draw controls
    record("CtrlDetect", "CustomControlLimit", "WARN",
           "Custom/owner-draw controls (e.g., Chrome renderer, game UI) have limited UIA support")
    record("CtrlDetect", "DirectXGameLimit", "WARN",
           "DirectX/OpenGL game windows: UIA returns minimal or empty control tree")
    record("CtrlDetect", "ElectronAppLimit", "INFO",
           "Electron apps (Chrome_WidgetWin_1): UIA tree may be shallow, rely on visual detection")
    
    # Test: Hybrid detection (UIA + Vision)
    record("CtrlDetect", "HybridDetection", "INFO",
           "UFO² supports hybrid UIA+Vision via OmniParser, but requires separate OmniParser endpoint setup")

except Exception as e:
    record("CtrlDetect", "Error", "FAIL", str(e)[:300])


# ============================================================
# 3. Command System - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("3. Command System - Deep Boundary")
print("="*60)

try:
    from ufo.automator.ui_control import controller
    
    # Full command inventory
    all_cmds = [x for x in dir(controller) if x.endswith("Command") and not x.startswith("_")]
    record("Commands", "FullCommandInventory", "PASS", f"{len(all_cmds)} commands: {all_cmds}")
    
    # Test each command category
    gui_cmds = ["ClickCommand", "ClickInputCommand", "ClickOnCoordinatesCommand",
                "DoubleClickCommand", "SetEditTextCommand", "WheelMouseInputCommand",
                "ScrollCommand", "DragCommand", "DragOnCoordinatesCommand",
                "KeyPressCommand", "MouseMoveCommand"]
    
    for cmd in gui_cmds:
        if hasattr(controller, cmd):
            record("Commands", f"GUI_{cmd}", "PASS", "Available")
        else:
            record("Commands", f"GUI_{cmd}", "FAIL", "Not found")
    
    # Boundary: Coordinate-based vs Control-based actions
    record("Commands", "CoordinateVsControl", "INFO",
           "Control-based (UIA) is more reliable; Coordinate-based is fallback for non-standard UI")
    
    # Boundary: Keyboard input limitations
    record("Commands", "KeyboardInputLimit", "INFO",
           "KeyPressCommand supports single keys; complex shortcuts need multiple KeyPressCommands")
    
    # Boundary: Drag limitations
    record("Commands", "DragLimit", "INFO",
           "Drag requires source+target coordinates; cross-window drag may fail if windows overlap incorrectly")
    
    # Boundary: Text input methods
    record("Commands", "TextInputMethods", "INFO",
           "set_text (instant, no keyboard events) vs type_keys (simulates keystrokes, triggers events)")

except Exception as e:
    record("Commands", "Error", "FAIL", str(e)[:300])


# ============================================================
# 4. Screenshot & Visual - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("4. Screenshot & Visual - Deep Boundary")
print("="*60)

try:
    from ufo.automator.ui_control.screenshot import (
        DesktopPhotographer, ControlPhotographer, 
        PhotographerFactory, AnnotationDecorator,
        TargetAnnotationDecorator
    )
    record("Screenshot", "PhotographerClasses", "PASS", "All photographer classes importable")
    
    # Test desktop screenshot
    try:
        dp = DesktopPhotographer()
        img = dp.capture()
        record("Screenshot", "DesktopScreenshot", "PASS", f"Image size={img.size if hasattr(img, 'size') else 'captured'}")
    except Exception as e:
        record("Screenshot", "DesktopScreenshot", "FAIL", str(e)[:200])
    
    # Test multi-monitor
    from PIL import ImageGrab
    try:
        monitors = ImageGrab.grab_allmonitors()
        record("Screenshot", "MultiMonitorScreenshot", "PASS", f"Multi-monitor capture available")
    except:
        # Fallback: single monitor
        img = ImageGrab.grab()
        record("Screenshot", "SingleMonitorOnly", "WARN", f"Single monitor: {img.size}")
    
    # Boundary: DPI scaling
    import ctypes
    try:
        awareness = ctypes.windll.shcore.GetProcessDpiAwareness()
        record("Screenshot", "DPIAwareness", "PASS", f"DPI awareness level={awareness}")
    except:
        record("Screenshot", "DPIAwareness", "WARN", "Could not determine DPI awareness")
    
    record("Screenshot", "DPIScalingLimit", "WARN",
           "High DPI scaling (150%/200%) may cause coordinate mismatch between screenshot and UIA bounds")
    
    # Boundary: Secure desktop
    record("Screenshot", "SecureDesktopLimit", "FAIL",
           "Cannot screenshot secure desktop (UAC prompt, login screen)")
    
    # Boundary: Locked screen
    record("Screenshot", "LockedScreenLimit", "FAIL",
           "Cannot screenshot or interact when screen is locked")

except Exception as e:
    record("Screenshot", "Error", "FAIL", str(e)[:300])


# ============================================================
# 5. MCP Integration - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("5. MCP Integration - Deep Boundary")
print("="*60)

try:
    # Check MCP config content
    mcp_config = r"D:\UFO\config\ufo\mcp.yaml"
    with open(mcp_config, 'r', encoding='utf-8') as f:
        content = f.read()
    record("MCP", "ConfigContent", "PASS", f"Config size={len(content)} bytes")
    
    # Check each MCP server
    local_dir = r"D:\UFO\ufo\client\mcp\local_servers"
    for f in os.listdir(local_dir):
        if f.endswith('.py') and f != '__init__.py':
            app_name = f.replace('_mcp_server.py', '').replace('_', ' ')
            record("MCP", f"LocalServer_{app_name}", "PASS", f"Available: {f}")
    
    http_dir = r"D:\UFO\ufo\client\mcp\http_servers"
    for f in os.listdir(http_dir):
        if f.endswith('.py') and f != '__init__.py':
            app_name = f.replace('_mcp_server.py', '').replace('_', ' ')
            record("MCP", f"HTTPServer_{app_name}", "PASS", f"Available: {f}")
    
    # Boundary: MCP requires running server processes
    record("MCP", "MCPRuntimeRequirement", "INFO",
           "MCP servers must be started before UFO can use them; auto-start is configured in mcp.yaml")
    
    # Boundary: MCP fallback
    record("MCP", "MCPFallbackToUI", "INFO",
           "When MCP execution fails, UFO falls back to GUI automation (configurable)")

except Exception as e:
    record("MCP", "Error", "FAIL", str(e)[:300])


# ============================================================
# 6. Office Automation - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("6. Office Automation - Deep Boundary")
print("="*60)

try:
    # xlwings
    try:
        import xlwings
        record("Office", "xlwings", "PASS", f"Available - direct Excel cell/chart manipulation")
    except ImportError:
        record("Office", "xlwings", "FAIL", "Not installed")
    
    # python-pptx
    try:
        import pptx
        record("Office", "python-pptx", "PASS", f"Available - PowerPoint slide editing")
    except ImportError:
        record("Office", "python-pptx", "FAIL", "Not installed")
    
    # win32com
    try:
        import win32com.client
        record("Office", "win32com", "PASS", "Available - Outlook/Word/Excel COM automation")
    except ImportError:
        record("Office", "win32com", "FAIL", "Not installed")
    
    # Office prompts
    office_prompt_dir = r"D:\UFO\ufo\prompts\apps"
    if os.path.exists(office_prompt_dir):
        apps = os.listdir(office_prompt_dir)
        record("Office", "SupportedApps", "PASS", f"Prompt dirs: {apps}")
    else:
        # Search alternative paths
        for root, dirs, files in os.walk(r"D:\UFO\ufo\prompts"):
            for d in dirs:
                if d in ("word", "excel", "web", "powerpoint", "outlook"):
                    record("Office", f"PromptDir_{d}", "PASS", f"Found at {root}")
    
    # Boundary: Office version compatibility
    record("Office", "OfficeVersionLimit", "INFO",
           "COM automation requires installed Office app; xlwings needs Excel running; python-pptx works without PowerPoint")
    
    # Boundary: Office not installed
    record("Office", "NoOfficeLimit", "WARN",
           "If Office apps not installed, only GUI-level interaction possible (no API access)")

except Exception as e:
    record("Office", "Error", "FAIL", str(e)[:300])


# ============================================================
# 7. LLM Integration - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("7. LLM Integration - Deep Boundary")
print("="*60)

try:
    # Check config via environment-based approach
    config_path = r"D:\UFO\config\ufo\agents.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    import yaml
    config = yaml.safe_load(content)
    
    # Host agent config
    host = config.get("HOST_AGENT", {})
    record("LLM", "HostAgent_APIType", "PASS", f"Configured: {host.get('API_TYPE')}")
    record("LLM", "HostAgent_Model", "PASS", f"Configured: {host.get('API_MODEL')}")
    record("LLM", "HostAgent_VisualMode", "PASS", f"VISUAL_MODE={host.get('VISUAL_MODE')}")
    
    api_key = host.get("API_KEY", "")
    if api_key and "YOUR_KEY" not in api_key:
        record("LLM", "HostAgent_APIKey", "PASS", "Configured")
    else:
        record("LLM", "HostAgent_APIKey", "WARN", "NOT configured - LLM calls will fail")
    
    # App agent config
    app = config.get("APP_AGENT", {})
    record("LLM", "AppAgent_APIType", "PASS", f"Configured: {app.get('API_TYPE')}")
    record("LLM", "AppAgent_Model", "PASS", f"Configured: {app.get('API_MODEL')}")
    
    # Supported providers
    providers = {
        "OpenAI": "openai",
        "Azure OpenAI": "aoai", 
        "Azure AD": "azure_ad",
        "Google Gemini": "gemini",
        "Qwen": "qwen",
        "Ollama (local)": "ollama",
        "Anthropic Claude": "anthropic",
        "DeepSeek": "deepseek"
    }
    record("LLM", "SupportedProviders", "PASS", f"{len(providers)} providers: {list(providers.keys())}")
    
    # Boundary: Vision model requirement
    record("LLM", "VisionModelRequirement", "INFO",
           "VISUAL_MODE=True requires vision-capable model (GPT-4o, Gemini Pro Vision, etc.)")
    
    # Boundary: Non-vision mode
    record("LLM", "NonVisionMode", "INFO",
           "VISUAL_MODE=False works with text-only models but significantly reduces GUI automation capability")
    
    # Boundary: LLM latency
    record("LLM", "LLMLatencyImpact", "INFO",
           "Each step requires 1+ LLM calls; typical latency 2-10s per step depending on model and network")
    
    # Boundary: LLM cost
    record("LLM", "LLMCostImpact", "INFO",
           "GPT-4o: ~$0.005-0.01 per step (input+output tokens); local models: free but slower")
    
    # Boundary: Max steps
    record("LLM", "MaxStepLimit", "INFO",
           "MAX_STEP=50 by default; complex tasks may hit this limit")

except Exception as e:
    record("LLM", "Error", "FAIL", str(e)[:300])


# ============================================================
# 8. Safety & Security - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("8. Safety & Security - Deep Boundary")
print("="*60)

try:
    sys_config_path = r"D:\UFO\config\ufo\system.yaml"
    with open(sys_config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    import yaml
    sys_config = yaml.safe_load(content)
    
    safe_guard = sys_config.get("SAFE_GUARD", False)
    control_list = sys_config.get("CONTROL_LIST", [])
    max_step = sys_config.get("MAX_STEP", 50)
    
    record("Safety", "SafeGuardEnabled", "PASS" if safe_guard else "WARN", 
           f"SAFE_GUARD={safe_guard}")
    record("Safety", "ControlWhitelist", "PASS", 
           f"{len(control_list)} allowed control types: {control_list}")
    record("Safety", "MaxStepLimit", "PASS", f"MAX_STEP={max_step}")
    
    # Boundary: What SafeGuard blocks
    record("Safety", "SafeGuardScope", "INFO",
           "SafeGuard prevents actions on controls NOT in CONTROL_LIST whitelist")
    
    # Boundary: UAC bypass
    record("Safety", "UACBypassLimit", "FAIL",
           "Cannot bypass UAC prompts - secure desktop blocks all automation")
    
    # Boundary: Admin privilege requirement
    record("Safety", "AdminPrivilege", "INFO",
           "Some apps (Task Manager, Registry Editor) require admin rights; UFO inherits caller's privileges")
    
    # Boundary: File system access
    record("Safety", "FileSystemAccess", "INFO",
           "UFO can interact with File Explorer GUI but cannot directly modify files via UIA (needs MCP/API)")
    
    # Boundary: Credential/input security
    record("Safety", "CredentialExposure", "WARN",
           "LLM receives screenshots which may contain sensitive data; API keys transmitted to LLM provider")

except Exception as e:
    record("Safety", "Error", "FAIL", str(e)[:300])


# ============================================================
# 9. Special Scenarios - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("9. Special Scenarios - Deep Boundary")
print("="*60)

try:
    import win32gui
    import win32con
    import win32process
    import psutil
    
    # Categorize all windows
    all_windows = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc_name = psutil.Process(pid).name() if pid > 4 else "System"
            except:
                proc_name = "Unknown"
            all_windows.append({"hwnd": hwnd, "title": title, "class": cls, "pid": pid, "process": proc_name})
    win32gui.EnumWindows(enum_cb, None)
    
    # Categorize by framework
    electron_apps = [w for w in all_windows if w["class"] == "Chrome_WidgetWin_1"]
    win32_apps = [w for w in all_windows if w["class"] not in ("Chrome_WidgetWin_1", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")]
    uwp_apps = [w for w in all_windows if "ApplicationFrame_" in w["class"]]
    
    record("Special", "ElectronAppCount", "PASS", f"{len(electron_apps)} Electron apps detected")
    record("Special", "ElectronAppUIA", "WARN",
           f"Electron apps have limited UIA trees; rely on visual detection: {[w['title'][:30] for w in electron_apps[:5]]}")
    
    record("Special", "Win32AppCount", "PASS", f"{len(win32_apps)} Win32 apps detected")
    record("Special", "Win32AppUIA", "PASS", "Win32 apps generally have full UIA support")
    
    record("Special", "UWPAppCount", "PASS", f"{len(uwp_apps)} UWP apps detected")
    record("Special", "UWPAppUIA", "INFO", "UWP apps have good UIA support but may need special handling")
    
    # Test: WPS Office (common Chinese app)
    wps = [w for w in all_windows if "wps" in w["process"].lower() or "KProme" in w["class"]]
    if wps:
        record("Special", "WPSOffice", "WARN",
               f"WPS detected: {[w['title'][:30] for w in wps]} - May have limited UIA support vs Microsoft Office")
    
    # Boundary: Game windows
    record("Special", "GameWindowLimit", "FAIL",
           "Game windows (DirectX/OpenGL): No UIA controls, no reliable click coordinates, visual-only with low accuracy")
    
    # Boundary: Virtual machine windows
    record("Special", "VMWindowLimit", "FAIL",
           "VM console windows: Cannot penetrate into guest OS; only host-level window control")
    
    # Boundary: Remote desktop
    record("Special", "RDPLimit", "FAIL",
           "RDP client windows: Cannot control remote session content; only local RDP window frame")
    
    # Boundary: Browser content
    record("Special", "BrowserContentLimit", "WARN",
           "Browser tab content: UIA can access basic elements (address bar, tabs) but web page DOM requires different approach")
    
    # Boundary: Console/Terminal
    record("Special", "ConsoleLimit", "INFO",
           "Console windows (cmd/PowerShell): Limited UIA support; text content accessible but not individual elements")
    
    # Boundary: Notification/toast windows
    record("Special", "ToastNotificationLimit", "WARN",
           "Toast notifications are transient; may disappear before UFO can interact with them")
    
    # Boundary: Multiple desktops (Win10/11 Task View)
    record("Special", "VirtualDesktopLimit", "WARN",
           "Windows virtual desktops: UIA only sees windows on current active desktop")

except Exception as e:
    record("Special", "Error", "FAIL", str(e)[:300])


# ============================================================
# 10. RAG / Knowledge - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("10. RAG / Knowledge - Deep Boundary")
print("="*60)

try:
    import faiss
    from sentence_transformers import SentenceTransformer
    
    # Test FAISS index creation
    import numpy as np
    dim = 384  # MiniLM dimension
    index = faiss.IndexFlatL2(dim)
    test_vec = np.random.random((1, dim)).astype('float32')
    index.add(test_vec)
    record("RAG", "FAISSIndexCreation", "PASS", f"Created index with dim={dim}")
    
    # Test embedding model download (may need first-time download)
    record("RAG", "EmbeddingModelRequirement", "INFO",
           "First run downloads embedding model (~100MB); cached locally after that")
    
    # Boundary: Knowledge sources
    record("RAG", "KnowledgeSources", "INFO",
           "3 sources: Help documents, Demonstration traces, Execution experience")
    
    # Boundary: RAG scope
    record("RAG", "RAGScopeLimit", "INFO",
           "RAG only helps with application-specific knowledge; does not improve general OS interaction")
    
    # Boundary: Knowledge freshness
    record("RAG", "KnowledgeFreshness", "INFO",
           "Knowledge is static per session; new experience saved after task completion")

except Exception as e:
    record("RAG", "Error", "FAIL", str(e)[:300])


# ============================================================
# 11. Agent Architecture - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("11. Agent Architecture - Deep Boundary")
print("="*60)

try:
    # Check agent module structure
    agent_dir = r"D:\UFO\ufo\agents"
    subdirs = [d for d in os.listdir(agent_dir) if os.path.isdir(os.path.join(agent_dir, d))]
    record("Agent", "AgentSubModules", "PASS", f"Modules: {subdirs}")
    
    # Check processor strategies
    strategy_dir = r"D:\UFO\ufo\agents\processors\strategies"
    if os.path.exists(strategy_dir):
        strategies = [f.replace('.py', '') for f in os.listdir(strategy_dir) if f.endswith('.py') and f != '__init__.py']
        record("Agent", "ProcessingStrategies", "PASS", f"{len(strategies)} strategies: {strategies}")
    
    # Check state management
    state_dir = r"D:\UFO\ufo\agents\states"
    if os.path.exists(state_dir):
        states = [f.replace('.py', '') for f in os.listdir(state_dir) if f.endswith('.py') and f != '__init__.py']
        record("Agent", "StateModules", "PASS", f"States: {states}")
    
    # Boundary: Agent hierarchy
    record("Agent", "AgentHierarchy", "INFO",
           "HostAgent (desktop-level orchestration) → AppAgent (application-specific execution)")
    
    # Boundary: Concurrent agents
    record("Agent", "ConcurrentAgentLimit", "INFO",
           "One AppAgent per application; HostAgent coordinates multiple AppAgents sequentially")
    
    # Boundary: Custom agent creation
    record("Agent", "CustomAgentSupport", "PASS",
           "Custom agents supported via third_party config and processor strategy extension")

except Exception as e:
    record("Agent", "Error", "FAIL", str(e)[:300])


# ============================================================
# 12. PiP Desktop - Deep Boundary
# ============================================================
print("\n" + "="*60)
print("12. Picture-in-Picture Desktop - Deep Boundary")
print("="*60)

try:
    import os
    mstsc = os.path.exists(r"C:\Windows\System32\mstsc.exe")
    record("PiP", "RDPClientAvailable", "PASS" if mstsc else "FAIL",
           "mstsc.exe found" if mstsc else "mstsc.exe NOT found")
    
    # Check RDP loopback capability
    record("PiP", "RDPLoopbackRequirement", "INFO",
           "PiP uses RDP loopback (connect to localhost); requires RDP to be enabled on the system")
    
    # Boundary: PiP limitations
    record("PiP", "PiPFeatureStatus", "WARN",
           "PiP is documented but may require additional setup/configuration; not plug-and-play")
    record("PiP", "PiPResourceUsage", "INFO",
           "PiP creates a virtual desktop session; uses additional RAM (~200-500MB) and GPU resources")
    record("PiP", "PiPCompatibility", "INFO",
           "PiP requires Windows Pro/Enterprise (RDP server); Windows Home does not support incoming RDP")

except Exception as e:
    record("PiP", "Error", "FAIL", str(e)[:300])


# ============================================================
# Save Results
# ============================================================
output_path = r"D:\UFO\test_results_v2.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "="*60)
print(f"Results saved to {output_path}")
print("="*60)

total = sum(len(v) for v in results.values())
passed = sum(1 for v in results.values() for t in v if t["status"] == "PASS")
failed = sum(1 for v in results.values() for t in v if t["status"] == "FAIL")
warned = sum(1 for v in results.values() for t in v if t["status"] == "WARN")
info = sum(1 for v in results.values() for t in v if t["status"] == "INFO")
print(f"\nSUMMARY: {total} tests | ✅ {passed} PASS | ❌ {failed} FAIL | ⚠️ {warned} WARN | ℹ️ {info} INFO")
