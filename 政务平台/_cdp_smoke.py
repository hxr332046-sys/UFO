"""最小 smoke test：验证 CDP evaluate + fetch 在 core.html tab 能否工作。"""
from __future__ import annotations
import json
import time
import urllib.request

import websocket  # type: ignore

CDP_HTTP = "http://127.0.0.1:9225/json"


def main():
    tabs = json.loads(urllib.request.urlopen(CDP_HTTP, timeout=5).read())
    tab = next(t for t in tabs if t.get("type") == "page" and "core.html" in t.get("url", ""))
    print(f"TAB: {tab['url'][:70]}")
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)

    def call(method, params=None, mid=1):
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        ws.settimeout(20)
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                raw = ws.recv()
            except Exception as e:
                return {"_err": str(e)}
            try:
                m = json.loads(raw)
            except Exception:
                continue
            if m.get("id") == mid:
                return m
        return {"_err": "timeout waiting for id " + str(mid)}

    print(call("Runtime.enable", mid=1))

    # 1. 最简单 evaluate
    r = call("Runtime.evaluate", {
        "expression": "1+2", "returnByValue": True
    }, mid=2)
    print(f"[1] 1+2 = {r}")

    # 2. location.href
    r = call("Runtime.evaluate", {
        "expression": "location.href", "returnByValue": True
    }, mid=3)
    print(f"[2] location = {(r.get('result') or {}).get('result') or {}}")

    # 3. localStorage Authorization
    r = call("Runtime.evaluate", {
        "expression": "(localStorage.getItem('Authorization') || '').slice(0,10)",
        "returnByValue": True
    }, mid=4)
    print(f"[3] auth(10) = {((r.get('result') or {}).get('result') or {}).get('value')}")

    # 4. 一个简单 async fetch（带 awaitPromise）
    print("[4] 发起一个简单 fetch (async + awaitPromise)...")
    t0 = time.time()
    r = call("Runtime.evaluate", {
        "expression": """
        (async function(){
            try {
                var r = await fetch('/', {method: 'HEAD'});
                return 'ok status=' + r.status;
            } catch(e) { return 'ERR: ' + String(e); }
        })()
        """,
        "returnByValue": True,
        "awaitPromise": True,
    }, mid=5)
    print(f"    elapsed: {time.time()-t0:.1f}s")
    print(f"    result: {r}")

    # 5. POST fetch 到 /icpsp-api/
    print("[5] POST fetch /icpsp-api/ (带 Authorization)...")
    t0 = time.time()
    r = call("Runtime.evaluate", {
        "expression": """
        (async function(){
            try {
                var auth = localStorage.getItem('Authorization');
                var body = {flowData:{}, linkData:{compUrl:'MemberPost', opeType:'load', compUrlPaths:['MemberPost'], busiCompUrlPaths:'%5B%5D', token:''}, itemId:''};
                var r = await fetch('/icpsp-api/v4/pc/register/establish/component/MemberPost/loadBusinessDataInfo?t='+Date.now(), {
                    method:'POST',
                    headers:{'Authorization':auth, 'Content-Type':'application/json;charset=UTF-8', 'language':'CH'},
                    body: JSON.stringify(body),
                    credentials:'include',
                });
                var j = await r.json();
                return 'code=' + j.code + ' msg=' + (j.msg||'').slice(0,60);
            } catch(e) { return 'ERR: ' + String(e); }
        })()
        """,
        "returnByValue": True,
        "awaitPromise": True,
    }, mid=6)
    print(f"    elapsed: {time.time()-t0:.1f}s")
    print(f"    result: {r}")

    ws.close()


if __name__ == "__main__":
    main()
