#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP 自动滑块验证登录。

流程：
  1) 通过 CDP 连接已打开的浏览器
  2) 导航到 SSO 登录页
  3) 探测登录页结构（账号密码 / 滑块 / 扫码）
  4) 如果已在 9087 业务页且 token 有效 → 直接同步 token
  5) 如果在登录页：填入账号密码 → 自动识别并拖动滑块 → 点击登录
  6) 等待回调完成 → 同步新 token

关键技术：
  - ddddocr 检测滑块缺口位置
  - CDP Input.dispatchMouseEvent 模拟类人拖拽
  - 自动从 localStorage 提取 Authorization

用法：
  python system/cdp_auto_slider_login.py
  python system/cdp_auto_slider_login.py --username 450921198812051251@123 --password YOUR_PWD
  python system/cdp_auto_slider_login.py --dry-run  # 只探测不操作

退出码：
  0 — 登录成功，token 已同步
  1 — 登录失败（滑块验证失败/凭证错误）
  2 — 环境错误（CDP 不可用/浏览器未打开）
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
import websocket

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

BROWSER_CFG = ROOT / "config" / "browser.json"
RUNTIME_AUTH = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
CREDENTIALS_FILE = ROOT / "config" / "credentials.json"  # 可选：存储加密凭证

LOGIN_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"
LOGIN_URL_FALLBACK = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage"
SSO_HOST = "tyrz.zwfw.gxzf.gov.cn"


def _cdp_port() -> int:
    with BROWSER_CFG.open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ── CDP 工具函数 ──

class CDPSession:
    """封装一个 CDP WebSocket 连接"""

    def __init__(self, ws_url: str, timeout: float = 20):
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self._id = 0

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass

    def send(self, method: str, params: Optional[Dict] = None) -> Dict:
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(msg))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == self._id:
                return resp.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
            "timeout": 30000,
        })
        inner = result.get("result", {})
        if inner.get("type") == "undefined":
            return None
        return inner.get("value")

    def navigate(self, url: str):
        self.send("Page.navigate", {"url": url})

    def screenshot(self, clip: Optional[Dict] = None) -> bytes:
        """截取页面截图，返回 PNG bytes"""
        params = {"format": "png"}
        if clip:
            params["clip"] = clip
        result = self.send("Page.captureScreenshot", params)
        return base64.b64decode(result.get("data", ""))

    def mouse_move(self, x: float, y: float):
        self.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y
        })

    def mouse_down(self, x: float, y: float, button: str = "left"):
        self.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": button, "clickCount": 1
        })

    def mouse_up(self, x: float, y: float, button: str = "left"):
        self.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": button, "clickCount": 1
        })

    def type_text(self, text: str, delay_ms: int = 80):
        """逐字符输入"""
        for ch in text:
            self.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "text": ch,
            })
            time.sleep(delay_ms / 1000 * (0.7 + random.random() * 0.6))
            self.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "text": ch,
            })

    def click_element(self, selector: str) -> bool:
        """点击指定 CSS 选择器的元素"""
        pos = self.evaluate(f"""(function(){{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            var r = el.getBoundingClientRect();
            return {{x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height}};
        }})()""")
        if not pos:
            return False
        x, y = pos["x"], pos["y"]
        self.mouse_move(x, y)
        time.sleep(0.1)
        self.mouse_down(x, y)
        time.sleep(0.05)
        self.mouse_up(x, y)
        return True


def _find_cdp_target(port: int) -> Optional[str]:
    """找到可用的 CDP 页签 WebSocket URL"""
    try:
        pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
    except Exception:
        return None
    # 优先找 9087 页
    for p in pages:
        if p.get("type") == "page" and "9087" in (p.get("url") or ""):
            return p.get("webSocketDebuggerUrl")
    # fallback: 任意非 devtools 页
    for p in pages:
        if p.get("type") == "page" and not (p.get("url") or "").startswith("devtools://"):
            return p.get("webSocketDebuggerUrl")
    return None


# ── 滑块验证核心 ──

def detect_slider_gap(bg_bytes: bytes, slider_bytes: bytes) -> int:
    """用 OpenCV 模板匹配检测滑块缺口 x 坐标（左上角 x）。
    
    优先使用带 alpha mask 的匹配（适配非矩形拼图块，如五边形、圆形等）。
    """
    import cv2
    import numpy as np

    bg_arr = np.frombuffer(bg_bytes, dtype=np.uint8)
    block_arr = np.frombuffer(slider_bytes, dtype=np.uint8)
    bg = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
    block_rgba = cv2.imdecode(block_arr, cv2.IMREAD_UNCHANGED)

    if bg is None or block_rgba is None:
        print("    [cv2] 图片解码失败")
        return 0

    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)

    # 带 alpha mask 的模板匹配（最精准）
    if block_rgba.ndim == 3 and block_rgba.shape[2] == 4:
        block_gray = cv2.cvtColor(block_rgba[:, :, :3], cv2.COLOR_BGR2GRAY)
        mask = block_rgba[:, :, 3]
        result = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCORR_NORMED, mask=mask)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        print(f"    [cv2] masked TM_CCORR_NORMED → x={max_loc[0]} conf={max_val:.4f}")
        if max_val > 0.5:
            return int(max_loc[0])

    # Fallback: Canny 边缘匹配
    block_bgr = block_rgba[:, :, :3] if block_rgba.ndim == 3 else block_rgba
    block_gray = cv2.cvtColor(block_bgr, cv2.COLOR_BGR2GRAY)
    bg_edges = cv2.Canny(bg_gray, 100, 200)
    block_edges = cv2.Canny(block_gray, 100, 200)
    result2 = cv2.matchTemplate(bg_edges, block_edges, cv2.TM_CCOEFF_NORMED)
    _, max_val2, _, max_loc2 = cv2.minMaxLoc(result2)
    print(f"    [cv2] Canny edge → x={max_loc2[0]} conf={max_val2:.4f}")
    if max_val2 > 0.1:
        return int(max_loc2[0])

    return 0


def human_like_drag_path(start_x: float, end_x: float, y: float,
                          steps: int = 30) -> List[Tuple[float, float]]:
    """生成类人的拖拽轨迹（加速→减速 + 微抖动）"""
    path = []
    dist = end_x - start_x
    for i in range(steps + 1):
        t = i / steps
        # 缓动函数：先快后慢
        ease = 1 - (1 - t) ** 3
        x = start_x + dist * ease
        # Y 轴微抖动
        jitter_y = y + random.uniform(-2, 2)
        # X 轴微抖动
        jitter_x = x + random.uniform(-1, 1)
        path.append((jitter_x, jitter_y))
    # 最后确保精确到位
    path.append((end_x, y))
    return path


def auto_slide(cdp: CDPSession, max_attempts: int = 3) -> bool:
    """自动识别并拖动 tyrz SSO 滑块验证码。
    
    tyrz 页面结构：
      - 背景图: img.backImg (695x196, base64)
      - 滑块图: img.bock-backImg (73x70, base64)  (注意拼写 bock 不是 block)
      - 滑块按钮: div.verify-move-block
      - 滑块轨道: div.verify-bar-area (宽 585px)
      - 验证成功: p.slider_success (visible 时表示成功)
    """
    for attempt in range(max_attempts):
        print(f"  [slider] 尝试 {attempt+1}/{max_attempts}...")

        # Step 1: 找到可见滑块 + 强制显示图片面板 + 读取图片
        info = cdp.evaluate("""(function(){
            var visibleBar = null;
            document.querySelectorAll('.verify-bar-area').forEach(function(el){
                if (el.offsetParent !== null && el.getBoundingClientRect().width > 100) visibleBar = el;
            });
            if (!visibleBar) return {found: false, reason: 'no visible verify-bar-area'};
            var slider = visibleBar.closest('.slider') || visibleBar.parentElement;
            while (slider && !slider.querySelector('img.backImg')) {
                slider = slider.parentElement;
                if (!slider || slider === document.body) return {found: false, reason: 'no slider container'};
            }
            var bgImg = slider.querySelector('img.backImg');
            var blockImg = slider.querySelector('img.bock-backImg');
            var moveBlock = slider.querySelector('.verify-move-block');
            if (!bgImg || !blockImg || !moveBlock)
                return {found: false, reason: 'missing elements'};
            // 强制显示图片面板（tyrz 滑块库的 display:none 隐藏）
            var imgOut = slider.querySelector('.verify-img-out');
            if (imgOut) {
                imgOut.style.display = 'block';
                imgOut.style.position = 'absolute';
                imgOut.style.bottom = '65px';
                imgOut.style.zIndex = '99999';
            }
            var barRect = visibleBar.getBoundingClientRect();
            var moveRect = moveBlock.getBoundingClientRect();
            // 等渲染后再读 bgImg display size
            var bgRect = bgImg.getBoundingClientRect();
            return {
                found: true,
                bgSrc: bgImg.src,
                blockSrc: blockImg.src,
                bgW: bgImg.naturalWidth,
                bgDisplayW: bgRect.width,
                barW: barRect.width,
                startX: moveRect.x + moveRect.width/2,
                startY: moveRect.y + moveRect.height/2,
            };
        })()""")

        if not info or not info.get("found"):
            print(f"  [slider] 未检测到可见滑块: {info}")
            if attempt < max_attempts - 1:
                cdp.evaluate("""(function(){
                    document.querySelectorAll('.verify-refresh').forEach(function(r){ r.click(); });
                    var bars = document.querySelectorAll('.verify-bar-area');
                    bars.forEach(function(b){ b.click(); });
                })()""")
                time.sleep(4)
            continue

        bar_w = info.get("barW", 585)
        bg_w = info.get("bgW", 695)
        bg_disp_w = info.get("bgDisplayW", 0)
        start_x = info.get("startX", 847)
        start_y = info.get("startY", 419)
        print(f"  [slider] bar_w={bar_w:.0f} bg={bg_w} bgDisp={bg_disp_w:.0f}")

        # Step 2: 读取图片 + OpenCV 检测缺口
        bg_bytes = _data_url_to_bytes(info.get("bgSrc", ""))
        block_bytes = _data_url_to_bytes(info.get("blockSrc", ""))
        if not bg_bytes or not block_bytes:
            print("  [slider] 图片数据获取失败")
            continue

        gap_x = detect_slider_gap(bg_bytes, block_bytes)
        if gap_x <= 0:
            print("  [slider] 未检测到缺口")
            continue

        # Step 3: 计算拖拽距离
        scale = bg_disp_w / bg_w if bg_w > 0 and bg_disp_w > 0 else bar_w / bg_w
        drag_px = gap_x * scale + random.uniform(-2, 2)
        drag_px = max(10, min(drag_px, bar_w - 10))
        print(f"  [slider] gap_x={gap_x} scale={scale:.3f} drag={drag_px:.0f}px")

        # Step 4: 通过 JS 事件模拟完整拖拽流程
        # tyrz 滑块库的 mousedown handler 不响应 CDP Input 事件，
        # 但通过 element.dispatchEvent(new MouseEvent(...)) 可以触发
        cdp.evaluate(f"""(function(){{
            var bars = document.querySelectorAll('.verify-bar-area');
            var bar = null;
            bars.forEach(function(el){{ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; }});
            var slider = bar.closest('.slider') || bar.parentElement;
            while (slider && !slider.querySelector('.verify-move-block')) slider = slider.parentElement;
            var mb = slider.querySelector('.verify-move-block');
            var r = mb.getBoundingClientRect();
            var evt = new MouseEvent('mousedown', {{
                bubbles: true, cancelable: true,
                clientX: r.x + r.width/2, clientY: r.y + r.height/2,
                button: 0, buttons: 1, view: window
            }});
            mb.dispatchEvent(evt);
        }})()""")
        time.sleep(0.3 + random.random() * 0.2)

        # Step 5: 逐步 mousemove（在 document 上分发）
        steps = 35 + random.randint(0, 10)
        for i in range(steps + 1):
            t = i / steps
            ease = t * t * (3 - 2 * t)  # ease-in-out
            x = start_x + drag_px * ease + random.uniform(-1.2, 1.2)
            y = start_y + random.uniform(-1.5, 1.5)
            cdp.evaluate(f"""(function(){{
                document.dispatchEvent(new MouseEvent('mousemove', {{
                    bubbles:true, cancelable:true,
                    clientX:{x}, clientY:{y},
                    button:0, buttons:1, view:window
                }}));
            }})()""")
            time.sleep(0.015 + random.random() * 0.025)

        # Step 6: mouseup
        end_x = start_x + drag_px
        time.sleep(0.05 + random.random() * 0.1)
        cdp.evaluate(f"""(function(){{
            document.dispatchEvent(new MouseEvent('mouseup', {{
                bubbles:true, cancelable:true,
                clientX:{end_x}, clientY:{start_y},
                button:0, view:window
            }}));
        }})()""")
        print(f"  [slider] 拖拽完成 drag={drag_px:.0f}px")

        # Step 7: 检查验证结果
        time.sleep(2)
        success = cdp.evaluate("""(function(){
            var s = document.querySelectorAll('.slider_success');
            for (var i = 0; i < s.length; i++) {
                if (s[i].offsetParent !== null) return true;
            }
            return false;
        })()""")
        if success:
            print("  [slider] ✓ 验证成功!")
            return True
        else:
            print("  [slider] 验证未通过，刷新重试...")
            # 隐藏之前强制显示的面板
            cdp.evaluate("""(function(){
                document.querySelectorAll('.verify-img-out').forEach(function(el){ el.style.display = ''; });
            })()""")
            time.sleep(1.5)
            cdp.evaluate("""(function(){
                document.querySelectorAll('.verify-refresh').forEach(function(r){ r.click(); });
            })()""")
            time.sleep(3)

    print("  [slider] 所有尝试均失败")
    return False


def _slide_by_screenshot(cdp: CDPSession, slider_info: Dict) -> bool:
    """备用方案：通过页面截图识别缺口"""
    print("  [slider] 尝试截图方式识别...")
    container_rect = slider_info.get("containerRect", {})
    if not container_rect:
        return False

    # 截取验证码区域
    clip = {
        "x": container_rect.get("x", 0),
        "y": container_rect.get("y", 0),
        "width": container_rect.get("width", 350),
        "height": container_rect.get("height", 200),
        "scale": 1,
    }
    screenshot_bytes = cdp.screenshot(clip)
    # 保存截图供调试
    debug_path = ROOT / "dashboard" / "data" / "records" / "slider_screenshot.png"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_bytes(screenshot_bytes)
    print(f"  [slider] 截图已保存: {debug_path}")
    print(f"  [slider] 截图方式需要进一步调试，当前返回 False")
    return False


def _data_url_to_bytes(data_url: str) -> Optional[bytes]:
    """将 data:image/png;base64,... 转为 bytes"""
    if not data_url:
        return None
    if data_url.startswith("data:"):
        _, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)
    elif data_url.startswith("http"):
        try:
            r = requests.get(data_url, timeout=10, verify=False)
            return r.content
        except Exception:
            return None
    return None


def _execute_drag(cdp: CDPSession, start_x: float, start_y: float,
                  end_x: float, end_y: float) -> bool:
    """执行类人拖拽"""
    print(f"  [slider] 拖拽: ({start_x:.0f},{start_y:.0f}) → ({end_x:.0f},{end_y:.0f})")

    # 移到起点
    cdp.mouse_move(start_x, start_y)
    time.sleep(0.2 + random.random() * 0.3)

    # 按下
    cdp.mouse_down(start_x, start_y)
    time.sleep(0.1 + random.random() * 0.1)

    # 生成轨迹并执行
    path = human_like_drag_path(start_x, end_x, start_y, steps=25)
    for x, y in path:
        cdp.mouse_move(x, y)
        time.sleep(0.01 + random.random() * 0.02)

    # 松开
    time.sleep(0.05 + random.random() * 0.1)
    cdp.mouse_up(end_x, end_y)
    print("  [slider] 拖拽完成")

    # 等待验证结果
    time.sleep(2.0)
    return True


# ── 主登录流程 ──

def probe_page_state(cdp: CDPSession) -> Dict[str, Any]:
    """探测当前页面状态"""
    return cdp.evaluate("""(function(){
        var auth = '';
        try { auth = localStorage.getItem('Authorization') || ''; } catch(e) {}
        var top = '';
        try { top = localStorage.getItem('top-token') || ''; } catch(e) {}
        // Vuex store fallback
        if (!auth) {
            try {
                var app = document.getElementById('app');
                var vm = app && app.__vue__;
                var store = vm && vm.$store;
                if (store && store.state && store.state.common) {
                    auth = store.state.common.token || store.state.common.Authorization || '';
                }
            } catch(e2) {}
        }
        var href = location.href;
        var title = document.title || '';
        var body = (document.body && document.body.innerText) || '';
        var isLogin = /登录|注册|验证/.test(body) || /login|authPage/.test(href);
        var isSso = /tyrz/.test(href) || /统一认证/.test(title) || /am\/auth\/login/.test(href);
        var is9087 = /9087/.test(href) && /icpsp/.test(href);
        return {
            href: href,
            title: title,
            authorization: auth,
            topToken: top,
            isLogin: isLogin,
            isSso: isSso,
            is9087: is9087,
            hasSlider: !!document.querySelector('[class*="slider"],[class*="slide-verify"],[class*="verify"],[class*="captcha"]'),
            hasLoginForm: !!document.querySelector('input[type="password"],input[name="password"]'),
            bodyPreview: body.substring(0, 200),
        };
    })()""")


def login_flow(cdp: CDPSession, username: str = "", password: str = "",
               dry_run: bool = False, ws_url: str = "") -> bool:
    """完整的自动登录流程"""

    # Step 1: 探测当前页面
    state = probe_page_state(cdp)
    if not state:
        print("[login] 无法探测页面状态")
        return False

    print(f"[login] 当前页面: {state.get('href', '')[:100]}")
    print(f"[login] is9087={state.get('is9087')} isLogin={state.get('isLogin')} "
          f"isSso={state.get('isSso')} hasSlider={state.get('hasSlider')}")

    auth = state.get("authorization", "")

    # Case 1: 已在 9087 且 token 有效
    if state.get("is9087") and len(auth) == 32:
        print(f"[login] 已有 token: {auth[:8]}... 验证中...")
        # 写入 runtime_auth
        _sync_token(auth, state.get("topToken", ""))
        # 验证
        from auth_keepalive_service import check_token_health
        status = check_token_health()
        if status.alive:
            print(f"[login] Token 有效! user={status.user_name}")
            return True
        else:
            print("[login] Token 无效，需要重新登录")

    if dry_run:
        print("[login] dry-run 模式，不执行登录操作")
        return False

    # Case 2: 清除所有 auth 状态，通过 enterprise-zone 触发完整 SSO 链
    # 必须走 9087 enterprise-zone 入口（而非直接到 tyrz），因为 9087 服务端需要记录 SSO 上下文
    if not state.get("isSso") and not state.get("hasLoginForm"):
        print("[login] 清除所有 auth 状态，通过 enterprise-zone 触发 SSO...")
        # 彻底清除所有相关域的 cookies 和 storage（防止旧 SESSION/token 干扰）
        try:
            cdp.send("Network.enable")
            all_cookies = cdp.send("Network.getAllCookies")
            for c in all_cookies.get("cookies", []):
                d = c.get("domain", "")
                if "scjdglj" in d or "zwfw" in d or "mohrss" in d:
                    cdp.send("Network.deleteCookies", {
                        "name": c["name"], "domain": d, "path": c.get("path", "/")
                    })
            # 清除 6087/9087 的 localStorage（无需导航到对应域）
            for origin in [
                "https://zhjg.scjdglj.gxzf.gov.cn:6087",
                "https://zhjg.scjdglj.gxzf.gov.cn:9087",
            ]:
                cdp.send("Storage.clearDataForOrigin", {
                    "origin": origin,
                    "storageTypes": "local_storage,session_storage",
                })
        except Exception:
            pass

        # 先跳 about:blank 清空 SPA，再走 enterprise-zone 完整 SSO 链
        print("[login] about:blank → enterprise-zone 全量跳转...")
        cdp.navigate("about:blank")
        time.sleep(1.5)
        cdp.navigate(LOGIN_URL)
        # 等待 SSO 重定向（enterprise-zone → tyrz.zwfw.gxzf.gov.cn）
        for wait_i in range(15):
            time.sleep(3)
            try:
                state = probe_page_state(cdp)
            except Exception:
                print(f"  [{wait_i+1}/15] (页面跳转中...)")
                continue
            href = state.get('href', '') if state else ''
            print(f"  [{wait_i+1}/15] {href[:80]}")
            if state and (state.get('isSso') or state.get('hasLoginForm')):
                break
        print(f"[login] 落地页: {state.get('href', '')[:100]}")

    # Case 3: 在 SSO 登录页
    if state.get("isSso") or state.get("hasLoginForm"):
        print("[login] 在 SSO 登录页")
        if not username or not password:
            print("[login] ERROR: 未提供用户名/密码，无法自动登录")
            print("[login] 请通过 --username 和 --password 参数传入")
            return False

        # tyrz SSO 页面：#username / #password / .form_button
        # 用 JS 直接设值 + 触发 input 事件（确保 Vue/React 感知到）
        print("[login] 填入凭证...")
        cdp.evaluate(f"""(function(){{
            var u = document.querySelector('#username');
            if (!u) {{ var inputs = document.querySelectorAll('input[type="text"]'); for(var i=0;i<inputs.length;i++) if(inputs[i].offsetParent) {{ u=inputs[i]; break; }} }}
            if (u) {{
                u.focus();
                u.value = '';
                u.dispatchEvent(new Event('input', {{bubbles:true}}));
            }}
        }})()""")
        time.sleep(0.3)
        cdp.type_text(username, delay_ms=60)
        time.sleep(0.5)

        cdp.evaluate("""(function(){
            var p = document.querySelector('#password');
            if (!p) { var inputs = document.querySelectorAll('input[type="password"]'); for(var i=0;i<inputs.length;i++) if(inputs[i].offsetParent) { p=inputs[i]; break; } }
            if (p) {
                p.focus();
                p.value = '';
                p.dispatchEvent(new Event('input', {bubbles:true}));
            }
        })()""")
        time.sleep(0.3)
        cdp.type_text(password, delay_ms=60)
        time.sleep(0.8)

        # 滑块验证
        print("[login] 自动滑块验证...")
        slide_ok = auto_slide(cdp, max_attempts=5)
        if not slide_ok:
            print("[login] 滑块自动识别失败，可能需要手动完成")
            return False
        time.sleep(1)

        # 关键：在点击登录前启用 Fetch 拦截，把 ssc.mohrss.gov.cn 的请求重定向到 6087 portal
        # 原理：tyrz 登录成功后，6087/TopIP/sso/oauth2 设置 SESSION cookie 后 302 到 ssc。
        #       ssc 是社保卡扫码页（需手动扫码），但 6087 session 此时已激活，ssc 非必要。
        #       拦截 ssc 请求并 302 回 6087 portal，再走 entservice 取 9087 token。
        #
        # 实现：关闭 CDPSession，用全新 raw WS 做 Fetch（避免 cdp.send() 吞 Fetch 事件）
        cdp.close()
        time.sleep(0.3)

        _ws = websocket.create_connection(ws_url, timeout=60)
        _raw_id = [200]
        def _raw_send(method, params=None):
            _raw_id[0] += 1
            mid = _raw_id[0]
            _ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(_ws.recv())
                if msg.get("method") == "Fetch.requestPaused":
                    req = msg.get("params", {})
                    url = req.get("request", {}).get("url", "")
                    rid = req.get("requestId", "")
                    if "ssc.mohrss" in url:
                        _raw_id[0] += 1
                        _ws.send(json.dumps({"id": _raw_id[0], "method": "Fetch.failRequest",
                            "params": {"requestId": rid, "reason": "BlockedByClient"}}))
                    else:
                        _raw_id[0] += 1
                        _ws.send(json.dumps({"id": _raw_id[0], "method": "Fetch.continueRequest",
                            "params": {"requestId": rid}}))
                    continue
                if msg.get("id") == mid:
                    return msg.get("result", {})
        def _raw_ev(expr):
            r = _raw_send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
            return r.get("result", {}).get("value")

        print("[login] 启用 Fetch 拦截 ssc.mohrss.gov.cn...")
        _raw_send("Fetch.enable", {"patterns": [
            {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"},
        ]})

        # 点击登录按钮（通过 JS）
        print("[login] 点击登录...")
        btn_result = _raw_ev("""(function(){
            var btn = document.querySelector('.form_button');
            if (!btn) btn = document.querySelector('button[type="submit"]');
            if (btn) { btn.click(); return 'clicked'; }
            return 'not found';
        })()""")
        if btn_result != "clicked":
            print(f"[login] 未找到登录按钮: {btn_result}")
            try: _raw_send("Fetch.disable")
            except Exception: pass
            _ws.close()
            return False

        # 等待 ssc 拦截
        print("[login] 等待 ssc 拦截...")
        ssc_intercepted = False
        deadline = time.time() + 40
        _ws.settimeout(5)
        while time.time() < deadline:
            try:
                msg = json.loads(_ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                print(f"  [login] WS 错误: {e}")
                break
            if msg.get("method") == "Fetch.requestPaused":
                req = msg.get("params", {})
                url = req.get("request", {}).get("url", "")
                req_id = req.get("requestId", "")
                if "ssc.mohrss" in url:
                    ssc_intercepted = True
                    print(f"[login] 拦截 ssc: {url[:70]}")
                    _raw_id[0] += 1
                    _ws.send(json.dumps({
                        "id": _raw_id[0],
                        "method": "Fetch.fulfillRequest",
                        "params": {
                            "requestId": req_id,
                            "responseCode": 302,
                            "responseHeaders": [
                                {"name": "Location", "value": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"}
                            ],
                            "body": ""
                        }
                    }))
                    print("[login] 改重定向到 6087 portal")
                    break
                else:
                    _raw_id[0] += 1
                    _ws.send(json.dumps({
                        "id": _raw_id[0],
                        "method": "Fetch.continueRequest",
                        "params": {"requestId": req_id}
                    }))

        # 关闭 Fetch（_raw_send 内联处理 paused 事件）
        _ws.settimeout(60)
        try: _raw_send("Fetch.disable")
        except Exception: pass

        # 等 6087 SPA 加载完成（设置 top-token）
        time.sleep(8)

        # 导航到 SSO entservice 取 9087 token
        print("[login] 通过 SSO entservice 获取 9087 token...")
        _raw_send("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"})
        time.sleep(10)

        href = _raw_ev("location.href") or ""
        auth = _raw_ev("localStorage.getItem('Authorization') || ''") or ""

        if auth and len(auth) >= 16:
            print(f"[login] ✓ 登录成功! token={auth[:8]}... (len={len(auth)})")
            _ws.close()
            _sync_token(auth)
            return True

        # 多等几轮
        for attempt in range(10):
            time.sleep(2)
            href = _raw_ev("location.href") or ""
            auth = _raw_ev("localStorage.getItem('Authorization') || ''") or ""
            if auth and len(auth) >= 16:
                print(f"[login] ✓ 登录成功! token={auth[:8]}... (len={len(auth)})")
                _ws.close()
                _sync_token(auth)
                return True
            if "tyrz" in href:
                print("[login] 被重定向到 tyrz，6087 session 可能无效")
                _ws.close()
                return False
            print(f"  等待中... ({attempt+1}/10) href={href[:60]}")

        _ws.close()

    print("[login] 登录流程未完成")
    return False


def _sync_token(auth: str, top_token: str = "") -> None:
    """同步 token 到 runtime_auth_headers.json"""
    RUNTIME_AUTH.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "Authorization": auth,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html",
        "User-Agent": "Mozilla/5.0",
    }
    if top_token:
        headers["top-token"] = top_token
    RUNTIME_AUTH.write_text(
        json.dumps({
            "headers": headers,
            "ts": int(time.time()),
            "created_at": _now(),
            "source": "cdp_auto_slider_login",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[sync] Token synced to {RUNTIME_AUTH}")


def main() -> int:
    ap = argparse.ArgumentParser(description="CDP 自动滑块验证登录")
    ap.add_argument("--username", "-u", default="", help="SSO 用户名（身份证号@后缀）")
    ap.add_argument("--password", "-p", default="", help="SSO 密码")
    ap.add_argument("--dry-run", action="store_true", help="只探测不执行登录")
    ap.add_argument("--sync-only", action="store_true", help="只同步当前浏览器的 token")
    args = ap.parse_args()

    # 读取凭证（如果有本地凭证文件）
    username = args.username
    password = args.password
    if not username and CREDENTIALS_FILE.exists():
        try:
            creds = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
            username = creds.get("username", "")
            password = creds.get("password", "")
            print(f"[login] 从 {CREDENTIALS_FILE.name} 读取凭证: user={username[:10]}...")
        except Exception:
            pass

    try:
        port = _cdp_port()
    except Exception:
        print("ERROR: 无法读取 CDP 端口，请确认 config/browser.json 存在")
        return 2

    ws_url = _find_cdp_target(port)
    if not ws_url:
        print(f"ERROR: CDP 端口 {port} 无可用页签，请先启动浏览器")
        return 2

    cdp = CDPSession(ws_url)
    try:
        if args.sync_only:
            state = probe_page_state(cdp)
            auth = state.get("authorization", "")
            if len(auth) == 32:
                _sync_token(auth, state.get("topToken", ""))
                print(f"Token synced: {auth[:8]}...")
                return 0
            else:
                print("No valid token in browser localStorage")
                return 1

        ok = login_flow(cdp, username, password, dry_run=args.dry_run, ws_url=ws_url)
        return 0 if ok else 1
    finally:
        cdp.close()


if __name__ == "__main__":
    raise SystemExit(main())
