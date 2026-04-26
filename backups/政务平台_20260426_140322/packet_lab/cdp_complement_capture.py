#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ruff: noqa
"""
CDP 自动化：
1. 启动/连接 Edge Dev (CDP 9225)
2. 导航到目标 ComplementInfo 页面
3. 拦截 operationBusinessDataInfo 请求，捕获真实 body
4. 用 JS 注入自动填写"否"并点击保存
5. 保存捕获的 body 到文件供协议固化

用法: .\.venv-portal\Scripts\python.exe packet_lab\cdp_complement_capture.py
"""
import json, time, sys, subprocess, os, threading
from pathlib import Path
import requests, websocket

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

import pickle

CDP_PORT    = 9225
BUSI_ID     = "2047910256739598337"
NAME_ID     = "2047910192228147201"
ENT_TYPE    = "4540"
BASE_URL    = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
EDGE_EXE    = r"C:\Program Files (x86)\Microsoft\Edge Dev\Application\msedge.exe"
USER_DATA   = r"C:\Temp\EdgeDevCDP"
OUT_FILE    = ROOT / "packet_lab" / "out" / "complement_info_save_body.json"
COOKIE_PKL  = ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"
AUTH_JSON   = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"

TARGET_URL  = (
    f"{BASE_URL}/icpsp-web-pc/core.html#/flow/base"
    f"?fromProject=core&busiType=02_4&entType=4540"
    f"&nameId={NAME_ID}&visaFree=true"
)

# ─── CDP 工具 ──────────────────────────────────────────────────────────────

def _browser_running():
    try:
        r = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def _launch_browser():
    print("[CDP] 启动 Edge Dev …")
    args = [
        EDGE_EXE,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir={USER_DATA}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-web-security",
        BASE_URL + "/icpsp-web-pc/portal.html",
    ]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(1)
        if _browser_running():
            print("[CDP] 浏览器就绪")
            return True
    print("[CDP] ❌ 浏览器启动超时")
    return False

def _get_page_ws(prefer_9087=False):
    pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    if prefer_9087:
        for p in pages:
            if p.get("type") == "page" and "9087" in p.get("url",""):
                return p["webSocketDebuggerUrl"]
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    return None

def _load_auth():
    """从 pkl 和 json 加载 session cookies 和 Authorization."""
    auth = ""
    cookies = []
    try:
        with open(AUTH_JSON, encoding="utf-8") as f:
            hdr = json.load(f)
        auth = hdr.get("Authorization", "")
        print(f"[auth] Authorization={auth[:8]}...{auth[-4:]}")
    except Exception as e:
        print(f"[auth] 读取 AUTH_JSON 失败: {e}")
    try:
        with open(COOKIE_PKL, "rb") as f:
            jar = pickle.load(f)
        for c in jar:
            cookies.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "secure": c.secure,
                "httpOnly": False,
            })
        print(f"[auth] 加载 {len(cookies)} 个 cookies")
    except Exception as e:
        print(f"[auth] 读取 COOKIE_PKL 失败: {e}")
    return auth, cookies

def _inject_session(ws, auth, cookies, mid_start=100):
    """向 CDP 浏览器注入 cookies 和 localStorage Authorization."""
    mid = mid_start
    injected = 0
    for ck in cookies:
        try:
            _send(ws, "Network.setCookie", ck, msg_id=mid)
            mid += 1
            injected += 1
        except Exception as e:
            print(f"  [cookie] {ck['name']} 注入失败: {e}")
    print(f"[auth] 注入 {injected} 个 cookies")
    if auth:
        js = f"localStorage.setItem('Authorization',{json.dumps(auth)}); 'ok'"
        _eval(ws, js, msg_id=mid); mid += 1
        print(f"[auth] Authorization 注入到 localStorage")
    return mid

def _send(ws, method, params=None, msg_id=1):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.time() + 30
    while time.time() < deadline:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get("id") == msg_id:
            return msg
    raise TimeoutError(f"CDP {method} timeout")

def _eval(ws, js, msg_id=1, await_promise=False, timeout_ms=20000):
    r = _send(ws, "Runtime.evaluate", {
        "expression": js,
        "returnByValue": True,
        "awaitPromise": await_promise,
        "timeout": timeout_ms,
    }, msg_id=msg_id)
    return (r.get("result") or {}).get("result") or {}

def _navigate(ws, url, msg_id=1):
    _send(ws, "Page.navigate", {"url": url}, msg_id=msg_id)
    # wait for load
    time.sleep(5)

# ─── 核心流程 ──────────────────────────────────────────────────────────────

def main():
    if not _browser_running():
        if not _launch_browser():
            sys.exit(1)
    else:
        print("[CDP] 检测到已运行的浏览器")

    ws_url = _get_page_ws()
    if not ws_url:
        print("[CDP] ❌ 找不到可用页签")
        sys.exit(1)

    print(f"[CDP] 连接 {ws_url}")
    ws = websocket.WebSocket()
    ws.connect(ws_url, timeout=30)
    ws.settimeout(5)

    mid = 1
    auth, cookies = _load_auth()

    # 先注入 session 到当前页
    _send(ws, "Network.enable", {}, msg_id=mid); mid += 1
    mid = _inject_session(ws, auth, cookies, mid_start=mid)

    # 导航到 ComplementInfo 页面
    print(f"[CDP] 导航到 ComplementInfo 页面…")
    _send(ws, "Page.navigate", {"url": TARGET_URL}, msg_id=mid); mid += 1
    print("[CDP] 等待 SPA 加载（15s）…")
    time.sleep(15)

    # 导航后需要重新连接 WebSocket（页面可能变了）
    try:
        ws.close()
    except Exception:
        pass
    ws_url2 = _get_page_ws()
    if not ws_url2:
        print("[CDP] ❌ 导航后找不到页签")
        sys.exit(1)
    print(f"[CDP] 重连 {ws_url2[:80]}")
    ws = websocket.WebSocket()
    ws.connect(ws_url2, timeout=30)
    ws.settimeout(5)
    mid = 1

    # 检查当前 URL
    cur_url = _eval(ws, "window.location.href", msg_id=mid)
    mid += 1
    print(f"[CDP] 当前 URL: {cur_url.get('value', '?')[:100]}")

    # 再次注入 Authorization（新页面的 localStorage 为空）
    _send(ws, "Network.enable", {}, msg_id=mid); mid += 1
    if auth:
        _eval(ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", msg_id=mid)
        mid += 1
    time.sleep(3)

    # 启用 Fetch 拦截
    _send(ws, "Fetch.enable", {
        "patterns": [{"urlPattern": "*ComplementInfo/operationBusinessDataInfo*",
                      "requestStage": "Request"}]
    }, msg_id=mid); mid += 1
    print("[CDP] Fetch 拦截已启用")

    # 后台监听
    captured = {"body": None, "done": False}
    def _listen():
        while not captured["done"]:
            try:
                raw = ws.recv()
                msg = json.loads(raw)
                m = msg.get("method", "")
                if m == "Fetch.requestPaused":
                    params = msg.get("params", {})
                    req = params.get("request", {})
                    url = req.get("url", "")
                    body_str = req.get("postData") or ""
                    rid = params.get("requestId")
                    if "ComplementInfo/operationBusinessDataInfo" in url and body_str:
                        print(f"\n✅ 捕获 ComplementInfo save ({len(body_str)} bytes)")
                        try:
                            captured["body"] = json.loads(body_str)
                        except Exception:
                            captured["body"] = body_str
                        captured["done"] = True
                    if rid:
                        ws.send(json.dumps({"id": 9999, "method": "Fetch.continueRequest",
                                            "params": {"requestId": rid}}))
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                if not captured["done"]:
                    print(f"[listen] {type(e).__name__}: {e}")
                break

    t = threading.Thread(target=_listen, daemon=True)
    t.start()

    # 等待页面加载，尝试 JS 自动填写并保存
    print("[CDP] 尝试 JS 自动填写 partyBuildDto 并点击保存…")
    js_fill_and_save = r"""
(function() {
    try {
        // 找所有 Vue 实例
        function findVueInstance(selector) {
            var els = document.querySelectorAll(selector);
            for (var i = 0; i < els.length; i++) {
                var k = Object.keys(els[i]).find(k => k.startsWith('__vue'));
                if (k) return els[i][k];
            }
            return null;
        }

        // 尝试找 partyBuildFlag 相关的单选按钮并点击"否"
        var radios = document.querySelectorAll('input[type="radio"]');
        var clicked = 0;
        for (var i = 0; i < radios.length; i++) {
            var v = radios[i].value;
            // 常见的"否"值
            if (['2','否','false','0','no','NO','N'].indexOf(v) >= 0) {
                radios[i].click();
                clicked++;
            }
        }

        // 找党员人数输入框，输入0
        var inputs = document.querySelectorAll('input[type="text"], input[type="number"]');
        for (var i = 0; i < inputs.length; i++) {
            var ph = (inputs[i].placeholder || '').toLowerCase();
            var lb = '';
            // 找最近的 label
            var p = inputs[i].parentElement;
            for (var j = 0; j < 5 && p; j++) {
                lb += p.innerText || '';
                p = p.parentElement;
            }
            if (lb.indexOf('党员') >= 0 || ph.indexOf('党员') >= 0) {
                inputs[i].value = '0';
                inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
                inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
            }
        }

        return 'auto-fill attempted, radios clicked=' + clicked;
    } catch(e) {
        return 'error: ' + e.message;
    }
})()
"""
    val = _eval(ws, js_fill_and_save, msg_id=mid)
    mid += 1
    print(f"[CDP] 自动填写结果: {val.get('value', val)}")
    time.sleep(2)

    # 尝试点击"保存并下一步"按钮
    js_click_save = r"""
(function() {
    var btns = document.querySelectorAll('button, .el-button');
    var found = null;
    for (var i = 0; i < btns.length; i++) {
        var txt = btns[i].innerText || btns[i].textContent || '';
        if (txt.indexOf('保存') >= 0 || txt.indexOf('下一步') >= 0) {
            found = btns[i];
        }
    }
    if (found) {
        found.click();
        return '已点击: ' + (found.innerText || '').trim();
    }
    return '未找到保存按钮，共有buttons: ' + btns.length;
})()
"""
    val2 = _eval(ws, js_click_save, msg_id=mid)
    mid += 1
    print(f"[CDP] 点击保存结果: {val2.get('value', val2)}")

    # 等待捕获（最多60秒）
    print("[CDP] 等待服务端请求捕获（最多60秒）…如有弹窗/验证，脚本会继续等待…")
    for i in range(60):
        if captured["done"]:
            break
        time.sleep(1)
        if i % 10 == 9:
            print(f"  … 已等待 {i+1}s，尚未捕获")

    if captured["body"]:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(captured["body"], f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已保存到: {OUT_FILE}")
        # 打印关键字段
        body = captured["body"] if isinstance(captured["body"], dict) else {}
        pd = body.get("partyBuildDto", "未找到")
        print(f"  partyBuildDto: {json.dumps(pd, ensure_ascii=False)[:300]}")
        fl = body.get("flowData", {})
        print(f"  flowData.currCompUrl: {fl.get('currCompUrl')}")
        print(f"  signInfo: {body.get('signInfo')}")
        pf = body.get("partyBuildFlag", "未找到")
        print(f"  partyBuildFlag (顶层): {pf}")
        print(f"\n  body 顶层 keys: {list(body.keys())}")
    else:
        print("\n❌ 60秒内未捕获到请求")
        print("  → 请在浏览器中手动选择'否'并点击保存，脚本会自动抓包")

    captured["done"] = True
    ws.close()


if __name__ == "__main__":
    main()
