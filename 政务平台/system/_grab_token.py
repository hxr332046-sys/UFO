#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用现有浏览器 session 获取 9087 token，不做任何登录"""
import json, time, requests, websocket

CDP_PORT = 9225
SSO_ENTSERVICE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"

def main():
    tabs = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3).json()
    target = [t for t in tabs if t.get("type") == "page" and not t.get("url", "").startswith("devtools")][0]
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
        r = send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
        return r.get("result", {}).get("value")

    # 先到 6087 portal（确保 origin 是 6087）
    print("[1] 导航到 6087 portal...")
    send_cmd("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(5)
    href = ev("location.href") or ""
    print(f"    当前: {href[:80]}")

    # 检查 6087 top-token
    top = ev("localStorage.getItem('top-token') || '<empty>'") or ""
    print(f"    6087 top-token: {top[:30]}")

    # 导航到 entservice
    print("\n[2] 导航到 entservice...")
    send_cmd("Page.navigate", {"url": SSO_ENTSERVICE})
    time.sleep(8)

    href = ev("location.href") or ""
    print(f"    entservice 后: {href[:100]}")

    # 检查 9087 token
    auth = ev("localStorage.getItem('Authorization') || '<empty>'") or ""
    top2 = ev("localStorage.getItem('top-token') || '<empty>'") or ""
    print(f"    Authorization: {auth[:40]}")
    print(f"    top-token: {top2[:30]}")

    if auth and auth != "<empty>" and len(auth) >= 16:
        print(f"\n✓ Token 获取成功: {auth[:8]}... (len={len(auth)})")
    else:
        # 多等几次
        for i in range(8):
            time.sleep(2)
            auth = ev("localStorage.getItem('Authorization') || '<empty>'") or ""
            href = ev("location.href") or ""
            if auth and auth != "<empty>" and len(auth) >= 16:
                print(f"\n✓ Token 获取成功: {auth[:8]}... (len={len(auth)})")
                break
            print(f"    [{i+1}] waiting... href={href[:60]} auth={auth[:20]}")
        else:
            print("\n✗ 未获取到 token")

    ws.close()

if __name__ == "__main__":
    main()
