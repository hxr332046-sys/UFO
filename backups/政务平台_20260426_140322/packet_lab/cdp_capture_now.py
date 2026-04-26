#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接连接 complement-info tab，填写 党员人数=0，点保存，捕获请求体
"""
import json, time, sys, threading
from pathlib import Path
import requests, websocket

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "packet_lab" / "out" / "complement_info_save_body.json"

CDP_PORT = 9225

def all_tabs():
    return requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()

def find_complement_tab():
    for p in all_tabs():
        if p.get("type") == "page" and "complement-info" in p.get("url",""):
            return p
    for p in all_tabs():
        if p.get("type") == "page" and "core.html" in p.get("url",""):
            return p
    return None

def connect_ws(url):
    ws = websocket.WebSocket()
    ws.connect(url, timeout=30)
    ws.settimeout(5)
    return ws

def send_c(ws, method, params=None, mid=1):
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r
        except websocket.WebSocketTimeoutException:
            continue
    raise TimeoutError(f"timeout: {method}")

def jse(ws, expr, mid=1):
    r = send_c(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "timeout": 15000}, mid=mid)
    return (r.get("result") or {}).get("result") or {}

def main():
    tab = find_complement_tab()
    if not tab:
        print("[!] 未找到 complement-info tab")
        print("当前所有 tabs:")
        for p in all_tabs():
            print(f"  [{p.get('type')}] {p.get('url','')[:80]}")
        return

    print(f"[tab] 连接: {tab['url'][:80]}")
    ws = connect_ws(tab["webSocketDebuggerUrl"])
    mid = 1

    # 检查当前页面状态
    send_c(ws, "Network.enable", {}, mid=mid); mid += 1
    cur = jse(ws, "window.location.href", mid=mid); mid += 1
    print(f"[url] {cur.get('value','')[:80]}")

    # 启用 Fetch 拦截
    send_c(ws, "Fetch.enable", {
        "patterns": [{"urlPattern": "*ComplementInfo/operationBusinessDataInfo*",
                       "requestStage": "Request"}]
    }, mid=mid); mid += 1
    print("[fetch] 拦截已启用")

    captured = {"body": None, "done": False}

    def listen_fn():
        lws = connect_ws(tab["webSocketDebuggerUrl"])
        while not captured["done"]:
            try:
                raw = lws.recv()
                msg = json.loads(raw)
                if msg.get("method") == "Fetch.requestPaused":
                    p = msg.get("params", {})
                    req = p.get("request", {})
                    url = req.get("url", "")
                    body_str = req.get("postData") or ""
                    rid = p.get("requestId")
                    if "ComplementInfo/operationBusinessDataInfo" in url and body_str:
                        print(f"\n✅ 捕获! {len(body_str)} bytes")
                        try: captured["body"] = json.loads(body_str)
                        except: captured["body"] = body_str
                        captured["done"] = True
                    if rid:
                        lws.send(json.dumps({"id": 9000, "method": "Fetch.continueRequest",
                                              "params": {"requestId": rid}}))
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                if not captured["done"]:
                    print(f"[listen] {e}")
                break

    threading.Thread(target=listen_fn, daemon=True).start()

    # 填写 党员人数 = 0
    fill_js = """
(function() {
    var res = [];
    // 找党员人数输入框
    var inputs = Array.from(document.querySelectorAll('input'));
    for (var inp of inputs) {
        var ctx = '';
        var p = inp.parentElement;
        for (var i=0; i<8&&p; i++) { ctx += (p.innerText||''); p=p.parentElement; }
        if (ctx.includes('党员人数') || (inp.placeholder||'').includes('党员')) {
            inp.value = '0';
            inp.dispatchEvent(new Event('input', {bubbles:true}));
            inp.dispatchEvent(new Event('change', {bubbles:true}));
            // 也触发 blur
            inp.dispatchEvent(new Event('blur', {bubbles:true}));
            res.push('党员人数 input → 0 (placeholder=' + inp.placeholder + ')');
        }
    }
    // 同时确保所有"否"单选都选中
    var radios = Array.from(document.querySelectorAll('input[type=radio]'));
    var noRadios = radios.filter(r => {
        var lbl = r.closest('label') || r.parentElement || {};
        return (lbl.innerText||'').trim() === '否' || r.value === '2';
    });
    noRadios.forEach(function(r) {
        if (!r.checked) {
            r.click();
            r.dispatchEvent(new Event('change', {bubbles:true}));
        }
    });
    res.push('否单选: ' + noRadios.length + '个');
    res.push('全部radio数: ' + radios.length);

    // 描述表单状态
    var checkedVals = radios.filter(r=>r.checked).map(r=>r.value||r.name);
    res.push('已选radio值: ' + checkedVals.join(','));
    return res.join(' | ');
})()
"""
    fr = jse(ws, fill_js, mid=mid); mid += 1
    print(f"[fill] {fr.get('value','')}")
    time.sleep(2)

    # 点击保存
    save_js = """
(function() {
    var btns = Array.from(document.querySelectorAll('button, .el-button'));
    var sb = btns.find(b => {
        var t = (b.innerText||b.textContent||'').trim();
        return t.includes('保存') || t.includes('下一步');
    });
    if (sb) {
        sb.click();
        return '✅ 点击: ' + sb.innerText.trim();
    }
    var allTxts = btns.map(b=>(b.innerText||'').trim()).filter(t=>t);
    return '未找到保存按钮, 现有: [' + allTxts.slice(0,10).join(',') + ']';
})()
"""
    sr = jse(ws, save_js, mid=mid); mid += 1
    print(f"[save] {sr.get('value','')}")

    print("\n⏳ 等待捕获 (120s)... 可在浏览器手动点保存")
    for i in range(120):
        if captured["done"]: break
        time.sleep(1)
        if i % 20 == 19:
            r2 = jse(ws, save_js, mid=mid); mid += 1
            print(f"  ... {i+1}s 重试: {r2.get('value','')[:50]}")

    captured["done"] = True
    if captured["body"]:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(captured["body"], f, ensure_ascii=False, indent=2)
        body = captured["body"] if isinstance(captured["body"], dict) else {}
        print(f"\n✅ 已保存: {OUT}")
        print(f"  keys: {list(body.keys())}")
        pd = body.get("partyBuildDto", "无")
        print(f"  partyBuildDto: {json.dumps(pd, ensure_ascii=False)[:400]}")
        pf = body.get("partyBuildFlag","无")
        print(f"  partyBuildFlag(顶层): {pf}")
        print(f"  signInfo: {body.get('signInfo')}")
        fd = body.get("flowData",{})
        print(f"  flowData.currCompUrl: {fd.get('currCompUrl')}")
    else:
        print("\n❌ 未捕获，请手动在浏览器点保存后重跑此脚本")

if __name__ == "__main__":
    main()
