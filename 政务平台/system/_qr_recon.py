#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""侦察 tyrz 扫码登录的网络请求，找出 QR 生成/轮询接口"""
import json, time, websocket, requests

CDP_PORT = 9225

def main():
    # 找到页签
    tabs = requests.get(f"http://127.0.0.1:{CDP_PORT}/json").json()
    target = None
    for t in tabs:
        if t.get("type") == "page" and not t.get("url","").startswith("devtools"):
            target = t
            break
    if not target:
        print("No tab found"); return
    
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
    _id = [0]
    captured = []

    def send_cmd(method, params=None):
        _id[0] += 1
        mid = _id[0]
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            # 收集网络事件
            m = msg.get("method", "")
            if m in ("Network.requestWillBeSent", "Network.responseReceived"):
                captured.append(msg)
            if msg.get("id") == mid:
                return msg.get("result", {})

    def ev(expr):
        r = send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 15000})
        return r.get("result", {}).get("value")

    # 启用 Network
    send_cmd("Network.enable")
    
    # 导航到 tyrz 登录页
    print("导航到 tyrz 登录页...")
    # 构造一个简单的 tyrz URL（enterprise-zone SSO 入口）
    TYRZ_URL = "https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?service=initService"
    send_cmd("Page.navigate", {"url": TYRZ_URL})
    time.sleep(5)

    href = ev("location.href") or ""
    print(f"当前URL: {href[:100]}")

    # 清空已捕获的请求
    captured.clear()

    # 点击「扫码登录」tab
    print("\n点击扫码登录 tab...")
    ev("""(function(){
        var tabs = document.querySelectorAll('.login_header li, .tab-item, [class*="tab"]');
        var clicked = false;
        tabs.forEach(function(t){
            if (t.innerText && t.innerText.includes('扫码')) { t.click(); clicked = true; }
        });
        if (!clicked) {
            // 尝试更广泛的选择器
            document.querySelectorAll('a, span, div, li').forEach(function(el){
                if (el.innerText && el.innerText.trim() === '扫码登录' && el.offsetParent) {
                    el.click(); clicked = true;
                }
            });
        }
        return clicked ? 'clicked' : 'not found';
    })()""")
    
    time.sleep(3)

    # 再点「法人扫码」
    print("点击法人扫码...")
    ev("""(function(){
        var items = document.querySelectorAll('span, div, a, button, li');
        for (var i = 0; i < items.length; i++) {
            if (items[i].innerText && items[i].innerText.trim() === '法人扫码' && items[i].offsetParent) {
                items[i].click();
                return 'clicked';
            }
        }
        return 'not found';
    })()""")
    time.sleep(3)

    # 打印捕获的网络请求
    print(f"\n=== 捕获 {len(captured)} 个网络事件 ===")
    for evt in captured:
        m = evt.get("method", "")
        p = evt.get("params", {})
        if m == "Network.requestWillBeSent":
            req = p.get("request", {})
            url = req.get("url", "")
            method = req.get("method", "")
            if "tyrz" in url or "qr" in url.lower() or "scan" in url.lower() or "code" in url.lower():
                print(f"\n  >>> REQUEST: {method} {url}")
                if req.get("postData"):
                    print(f"      body: {req['postData'][:200]}")
                headers = req.get("headers", {})
                for k, v in headers.items():
                    if k.lower() in ("cookie", "content-type", "referer"):
                        print(f"      {k}: {v[:100]}")

    # 读取 QR 码图片信息
    print("\n=== QR 码分析 ===")
    qr_info = ev("""(function(){
        var imgs = document.querySelectorAll('img');
        var qrs = [];
        imgs.forEach(function(img){
            var src = img.src || '';
            var w = img.naturalWidth;
            if (w > 100 && w < 500 && (src.includes('qr') || src.includes('code') || src.includes('data:image') || src.includes('base64'))) {
                qrs.push({src: src.substring(0, 200), w: w, h: img.naturalHeight, cls: img.className});
            }
        });
        // 也找 canvas
        var canvases = document.querySelectorAll('canvas');
        canvases.forEach(function(c){
            if (c.width > 100 && c.width < 500) {
                qrs.push({type: 'canvas', w: c.width, h: c.height, dataUrl: c.toDataURL().substring(0, 100)});
            }
        });
        // 找所有可能的 QR 相关元素
        var qrDivs = document.querySelectorAll('[class*="qr"], [class*="code"], [id*="qr"], [id*="code"]');
        qrDivs.forEach(function(d){
            qrs.push({tag: d.tagName, cls: d.className, id: d.id, html: d.innerHTML.substring(0, 150)});
        });
        return qrs;
    })()""")
    print(json.dumps(qr_info, ensure_ascii=False, indent=2))

    # 看看页面完整结构
    print("\n=== 页面关键区域 ===")
    page_struct = ev("""(function(){
        var body = document.body.innerText.substring(0, 500);
        var scripts = [];
        document.querySelectorAll('script[src]').forEach(function(s){
            if (s.src && s.src.includes('tyrz')) scripts.push(s.src);
        });
        return {body: body, scripts: scripts, href: location.href};
    })()""")
    print(json.dumps(page_struct, ensure_ascii=False, indent=2))

    # 等几秒看有没有轮询请求
    print("\n=== 等待轮询请求 (10s) ===")
    captured.clear()
    ws.settimeout(2)
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
            m = msg.get("method", "")
            if m == "Network.requestWillBeSent":
                req = msg.get("params", {}).get("request", {})
                url = req.get("url", "")
                if "tyrz" in url and ("/json" in url or "status" in url or "qr" in url.lower() or "poll" in url.lower() or "check" in url.lower() or "scan" in url.lower()):
                    print(f"  POLL: {req.get('method','')} {url}")
                    if req.get("postData"):
                        print(f"        body: {req['postData'][:200]}")
        except:
            continue

    ws.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
