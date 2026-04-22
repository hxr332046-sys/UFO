#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探测当前浏览器 session 状态，不做任何登录操作"""
import json, time, requests, websocket

CDP_PORT = 9225

def main():
    tabs = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3).json()
    target = None
    for t in tabs:
        if t.get("type") == "page" and not t.get("url", "").startswith("devtools"):
            target = t
            break
    if not target:
        print("无可用 tab"); return

    print(f"当前 tab: {target['url'][:80]}")
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
    _id = [0]

    def send_cmd(method, params=None):
        _id[0] += 1
        mid = _id[0]
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == mid:
                return msg.get("result", {})

    def ev(expr):
        r = send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 10000})
        return r.get("result", {}).get("value")

    send_cmd("Network.enable")

    # 1. 当前 URL
    href = ev("location.href") or ""
    print(f"\n当前URL: {href}")

    # 2. Cookies
    cookies = send_cmd("Network.getAllCookies").get("cookies", [])
    print(f"\n=== 相关 Cookies ({len(cookies)} total) ===")
    for c in cookies:
        d = c.get("domain", "")
        if any(k in d for k in ["scjdglj", "zwfw", "mohrss", "tyrz"]):
            print(f"  {c['name']}={c['value'][:25]}... domain={d} path={c.get('path','/')}")

    # 3. localStorage (当前 origin)
    print("\n=== localStorage (当前 origin) ===")
    auth = ev("localStorage.getItem('Authorization') || '<empty>'") or ""
    top = ev("localStorage.getItem('top-token') || '<empty>'") or ""
    print(f"  Authorization: {auth[:30]}")
    print(f"  top-token: {top[:30]}")

    # 4. 页面 body 概要
    body = ev("document.body ? document.body.innerText.substring(0, 300) : '<no body>'") or ""
    print(f"\n=== 页面内容 ===")
    print(f"  {body[:200]}")

    # 5. 测试 /sso/ 路径能否在浏览器中访问
    print("\n=== 测试 tyrz /sso/ 可达性 ===")
    # 用 fetch API 在浏览器里发请求
    sso_test = ev("""
    (async function(){
        try {
            var r = await fetch('https://tyrz.zwfw.gxzf.gov.cn/sso/oauth2/authorize?response_type=code&client_id=test', {
                method: 'GET',
                redirect: 'manual',
                credentials: 'include'
            });
            return 'status=' + r.status + ' type=' + r.type;
        } catch(e) {
            return 'error: ' + e.message;
        }
    })()
    """)
    # fetch 返回 Promise，需要等一下
    time.sleep(2)
    sso_test = ev("""window._sso_test_result || '<pending>'""")
    # 用另一种方式：XHR
    ev("""
    (function(){
        var xhr = new XMLHttpRequest();
        xhr.open('GET', 'https://tyrz.zwfw.gxzf.gov.cn/sso/oauth2/authorize?response_type=code&client_id=test', true);
        xhr.onload = function(){ window._sso_xhr = 'status=' + xhr.status + ' body=' + xhr.responseText.substring(0,100); };
        xhr.onerror = function(){ window._sso_xhr = 'error'; };
        xhr.send();
    })()
    """)
    time.sleep(3)
    xhr_result = ev("window._sso_xhr || '<pending>'") or ""
    print(f"  XHR to /sso/: {xhr_result[:100]}")

    # 6. 测试 6087 authLogin
    ev("""
    (function(){
        var xhr = new XMLHttpRequest();
        xhr.open('GET', 'https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/sso/authLogin?authType=zwfw_guangxi', true);
        xhr.onload = function(){ window._6087_result = 'status=' + xhr.status + ' url=' + xhr.responseURL + ' body=' + xhr.responseText.substring(0,100); };
        xhr.onerror = function(){ window._6087_result = 'error'; };
        xhr.send();
    })()
    """)
    time.sleep(3)
    r6087 = ev("window._6087_result || '<pending>'") or ""
    print(f"  6087 authLogin: {r6087[:150]}")

    ws.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
