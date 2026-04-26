#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP v4 — 彻底清除浏览器旧 cookie → 注入新 session → portal 我的办件 → 继续办理
"""
import json, time, sys, threading, pickle
from pathlib import Path
import requests, websocket

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

CDP_PORT  = 9225
NAME_ID   = "2047910192228147201"
PHASE1_ID = "2047910067700891648"
BASE      = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
PKL       = ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"
AUTH_J    = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
OUT       = ROOT / "packet_lab" / "out" / "complement_info_save_body.json"

PORTAL_URL     = BASE + "/icpsp-web-pc/portal.html"
MATTERS_HASH   = "#/company/my-space/selecthandle-progress"

# ── 工具 ─────────────────────────────────────────────────────────────────

def all_tabs():
    return requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()

def page_tabs():
    return [p for p in all_tabs() if p.get("type") == "page"]

def connect_ws(url):
    ws = websocket.WebSocket()
    ws.connect(url, timeout=30)
    ws.settimeout(60)
    return ws

def send_c(ws, method, params=None, mid=1):
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid:
            return r

def jse(ws, expr, mid=1, await_p=False):
    r = send_c(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True,
        "awaitPromise": await_p, "timeout": 20000}, mid=mid)
    return (r.get("result") or {}).get("result") or {}

def load_auth():
    auth = json.loads(open(AUTH_J, encoding="utf-8").read()).get("Authorization", "")
    jar  = pickle.load(open(PKL, "rb"))
    cks  = [{"name": c.name, "value": c.value, "domain": c.domain,
              "path": c.path, "secure": c.secure, "httpOnly": False}
            for c in jar]
    print(f"[auth] token={auth[:8]}... cookies: {[(c['name'],c['domain']) for c in cks]}")
    return auth, cks

# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    auth, cks = load_auth()
    tabs = page_tabs()
    if not tabs:
        print("[!] 无页签"); return
    ws = connect_ws(tabs[0]["webSocketDebuggerUrl"])
    mid = 1

    # ① 清除所有浏览器 cookie，消除旧 session 干扰
    print("[clean] 清除所有浏览器 cookie...")
    send_c(ws, "Network.enable", {}, mid=mid); mid += 1
    send_c(ws, "Network.clearBrowserCookies", {}, mid=mid); mid += 1
    print("[clean] 完成")

    # ② 注入新 session cookie
    for ck in cks:
        try:
            send_c(ws, "Network.setCookie", ck, mid=mid); mid += 1
        except Exception as e:
            print(f"  [ck] {ck['name']}@{ck['domain']} 失败: {e}")
    print(f"[inject] 注入 {len(cks)} 个 cookies")

    # ③ 导航到空白页（刷新 cookie 生效）
    send_c(ws, "Page.navigate", {"url": "about:blank"}, mid=mid); mid += 1
    time.sleep(2)

    # ④ 再次注入（避免 about:blank 时 localStorage 问题）
    for ck in cks:
        try:
            send_c(ws, "Network.setCookie", ck, mid=mid); mid += 1
        except Exception:
            pass

    # ⑤ 导航到 portal
    print("[nav] 导航到 portal...")
    send_c(ws, "Page.navigate", {"url": PORTAL_URL}, mid=mid); mid += 1
    time.sleep(12)

    cur = jse(ws, "window.location.href", mid=mid); mid += 1
    print(f"[nav] URL: {cur.get('value','')[:100]}")

    if "tyrz" in (cur.get("value","")) or "login" in (cur.get("value","")):
        print("[!] portal 跳 SSO — session 不足。请在浏览器中登录后按 Enter...")
        input("按 Enter 继续: ")
        # 重连
        ws.close()
        ws = connect_ws(page_tabs()[0]["webSocketDebuggerUrl"]); mid = 1
        send_c(ws, "Network.enable", {}, mid=mid); mid += 1

    # ⑥ 注入 Authorization 到 localStorage
    jse(ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid); mid += 1
    print("[auth] localStorage 注入完成")

    # ⑦ 导航到我的办件（SPA hash 路由）
    print("[nav] 跳转到我的办件...")
    jse(ws, f"window.location.hash = '{MATTERS_HASH}'", mid=mid); mid += 1
    time.sleep(10)

    cur2 = jse(ws, "window.location.href", mid=mid); mid += 1
    print(f"[nav] matters URL: {cur2.get('value','')[:100]}")

    # ⑧ 检查列表项并点击继续办理
    pre_tab_ids = {t["id"] for t in page_tabs()}

    click_js = f"""
(function() {{
    var allText = document.body.innerText || '';
    var btns = Array.from(document.querySelectorAll('button,.el-button,a[class*="btn"]'));
    var btnTexts = btns.slice(0,30).map(b=>(b.innerText||'').trim()).filter(t=>t);

    // 找"继续办理"
    var contBtn = btns.find(b => (b.innerText||b.textContent||'').includes('继续'));
    if (contBtn) {{
        contBtn.click();
        return '✅ 点击继续办理: ' + (contBtn.innerText||'').trim();
    }}

    // 找"美裕盈"或 nameId 容器内的按钮
    var rows = document.querySelectorAll('[class*="table"] tr, [class*="list"] [class*="item"]');
    for (var row of rows) {{
        if ((row.innerText||'').includes('美裕盈') || (row.innerHTML||'').includes('{NAME_ID}')) {{
            var rb = row.querySelector('button,.el-button');
            if (rb) {{ rb.click(); return '✅ 行内按钮: ' + (rb.innerText||''); }}
        }}
    }}

    return '未找到按钮. 按钮列表: [' + btnTexts.join(', ') + '] 页面文本片段: ' +
           allText.substring(0, 200);
}})()
"""
    r = jse(ws, click_js, mid=mid); mid += 1
    print(f"[click] {r.get('value','')}")

    # 等新标签页出现
    time.sleep(5)
    post_tabs = page_tabs()
    new_ids = {t["id"] for t in post_tabs} - pre_tab_ids
    print(f"[tabs] 新标签: {len(new_ids)}")

    # 选择目标 ws
    if new_ids:
        nt = next(t for t in post_tabs if t["id"] in new_ids)
        print(f"[new_tab] {nt.get('url','')[:80]}")
        target_ws = connect_ws(nt["webSocketDebuggerUrl"])
    else:
        print("[!] 没有新标签，在当前页继续")
        target_ws = ws

    time.sleep(15)  # 等 core.html SPA 加载
    mid3 = 1
    cur3 = jse(target_ws, "window.location.href", mid=mid3); mid3 += 1
    print(f"[core] URL: {cur3.get('value','')[:100]}")

    # 注入 Authorization
    jse(target_ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid3); mid3 += 1

    # ⑨ 启用 Fetch 拦截
    send_c(target_ws, "Fetch.enable", {
        "patterns": [{"urlPattern": "*ComplementInfo/operationBusinessDataInfo*",
                       "requestStage": "Request"}]
    }, mid=mid3); mid3 += 1
    print("[fetch] 拦截启用")

    captured = {"body": None, "done": False}

    def listen_fn(lws):
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
                        except Exception: captured["body"] = body_str
                        captured["done"] = True
                    if rid:
                        lws.send(json.dumps({"id": 8888, "method": "Fetch.continueRequest",
                                              "params": {"requestId": rid}}))
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                if not captured["done"]:
                    print(f"[listen] {e}")
                break

    listen_ws = connect_ws(page_tabs()[-1]["webSocketDebuggerUrl"])
    threading.Thread(target=lambda: listen_fn(listen_ws), daemon=True).start()

    # ⑩ 等待 ComplementInfo 表单并自动填写
    print("[wait] 等表单加载 (15s)...")
    time.sleep(15)

    fill_js = """
(function() {
    var res = [];
    // 点所有"否"值的单选
    document.querySelectorAll('input[type=radio]').forEach(function(r) {
        var parent = r.closest('label') || r.parentElement || {};
        var txt = (parent.innerText||'');
        if (r.value==='2' || txt.includes('否')) {
            r.click(); r.dispatchEvent(new Event('change',{bubbles:true}));
            res.push('radio val=' + r.value);
        }
    });
    // 设置党员人数
    document.querySelectorAll('input[type=text],input[type=number]').forEach(function(inp) {
        var ctx = '';
        var p = inp; for(var i=0;i<6;i++){p=p&&p.parentElement;ctx+=(p&&p.innerText||'');}
        if(ctx.includes('党员')||(inp.placeholder||'').includes('党员')) {
            inp.value='0';
            inp.dispatchEvent(new Event('input',{bubbles:true}));
            inp.dispatchEvent(new Event('change',{bubbles:true}));
            res.push('numParM=0');
        }
    });
    return res.length ? res.join('; ') : '无表单元素 (共radio:'+
        document.querySelectorAll('input[type=radio]').length+')';
})()
"""
    fr = jse(target_ws, fill_js, mid=mid3); mid3 += 1
    print(f"[fill] {fr.get('value','')}")
    time.sleep(2)

    save_js = """
(function() {
    var btns = Array.from(document.querySelectorAll('button,.el-button'));
    var sb = btns.find(b => {
        var t = (b.innerText||b.textContent||'').trim();
        return t.includes('保存') || t.includes('下一步');
    });
    if (sb) { sb.click(); return '点击: ' + sb.innerText.trim(); }
    return '未找到 (' + btns.length + '个)';
})()
"""
    sr = jse(target_ws, save_js, mid=mid3); mid3 += 1
    print(f"[save] {sr.get('value','')}")

    print("\n⏳ 等待捕获 (120s)...如需手动，请在浏览器中操作")
    for i in range(120):
        if captured["done"]: break
        time.sleep(1)
        if i % 25 == 24:
            jse(target_ws, save_js, mid=mid3); mid3 += 1
            print(f"  ... {i+1}s 重试保存")

    captured["done"] = True
    if captured["body"]:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(captured["body"], f, ensure_ascii=False, indent=2)
        body = captured["body"] if isinstance(captured["body"], dict) else {}
        print(f"\n✅ 保存完成: {OUT}")
        print(f"  keys: {list(body.keys())}")
        pd = body.get("partyBuildDto","无")
        print(f"  partyBuildDto: {json.dumps(pd, ensure_ascii=False)[:300]}")
        print(f"  signInfo: {body.get('signInfo')}")
    else:
        print("\n❌ 未捕获")

if __name__ == "__main__":
    main()
