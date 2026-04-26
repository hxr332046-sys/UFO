#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP v3 - 最简策略:
1. 导航到 portal 我的事项页 (authenticated)
2. 找到目标办件，点击"继续办理" (window.open → 新标签)
3. 连接新标签的 CDP
4. 启用 Fetch 拦截 ComplementInfo save
5. JS 自动填写并触发保存
6. 捕获请求体
"""
import json, time, sys, threading, pickle
from pathlib import Path
import requests, websocket

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

CDP_PORT  = 9225
NAME_ID   = "2047910192228147201"
PHASE1_ID = "2047910067700891648"   # matters search 用
BASE      = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
PKL       = ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"
AUTH_J    = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
OUT       = ROOT / "packet_lab" / "out" / "complement_info_save_body.json"

PORTAL_MATTERS = BASE + "/icpsp-web-pc/portal.html#/company/my-space/selecthandle-progress"

# ── 工具 ─────────────────────────────────────────────────────────────────

def all_tabs():
    return requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()

def page_tabs():
    return [p for p in all_tabs() if p.get("type") == "page"]

def connect_tab(tab):
    ws = websocket.WebSocket()
    ws.connect(tab["webSocketDebuggerUrl"], timeout=30)
    ws.settimeout(60)
    return ws

def send_msg(ws, method, params=None, mid=1):
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid:
            return r

def js_eval(ws, expr, mid=1):
    r = send_msg(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "timeout": 25000}, mid=mid)
    return (r.get("result") or {}).get("result") or {}

def load_auth():
    auth = json.loads(open(AUTH_J, encoding="utf-8").read()).get("Authorization", "")
    jar  = pickle.load(open(PKL, "rb"))
    cks  = [{"name": c.name, "value": c.value, "domain": c.domain,
              "path": c.path, "secure": c.secure, "httpOnly": False}
            for c in jar]
    return auth, cks

def inject_cookies(ws, cks, mid_start=100):
    mid = mid_start
    for ck in cks:
        try:
            send_msg(ws, "Network.setCookie", ck, mid=mid); mid += 1
        except Exception:
            pass
    return mid

# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    auth, cks = load_auth()
    print(f"[auth] token={auth[:8]}... cookies={len(cks)}")

    # 找当前页签 (browser already open from previous run)
    tabs = page_tabs()
    if not tabs:
        print("[!] 没找到页签，请先启动浏览器"); return
    tab = tabs[0]
    print(f"[tab] 连接: {tab['url'][:70]}")
    ws = connect_tab(tab)
    mid = 1

    send_msg(ws, "Network.enable", {}, mid=mid); mid += 1
    mid = inject_cookies(ws, cks, mid_start=mid)
    js_eval(ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid); mid += 1

    # Step 1: 导航到 portal 我的办件页
    print(f"[nav] 导航到我的办件页...")
    send_msg(ws, "Page.navigate", {"url": PORTAL_MATTERS}, mid=mid); mid += 1
    time.sleep(12)  # 等 SPA 渲染列表

    cur = js_eval(ws, "window.location.href", mid=mid); mid += 1
    print(f"[nav] 当前: {cur.get('value','')[:80]}")

    if "tyrz" in (cur.get("value","")) or "login" in (cur.get("value","")):
        print("[!] 仍在 SSO 页 — session 无效。请手动在浏览器中登录后按 Enter...")
        input("按 Enter 继续...")
        ws.close()
        tabs = page_tabs()
        ws = connect_tab(tabs[0]); mid = 1
        send_msg(ws, "Network.enable", {}, mid=mid); mid += 1

    # 注入 Authorization 到 localStorage
    js_eval(ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid); mid += 1

    # Step 2: 在我的办件列表中找到目标并点击"继续办理"
    print("[find] 查找目标办件的继续办理按钮...")
    # 记录现有标签页数量
    pre_tabs = {t["id"] for t in page_tabs()}

    find_and_click_js = f"""
(function() {{
    // 找包含 nameId 或特定企业名的 继续办理 按钮
    var btns = Array.from(document.querySelectorAll('button, .el-button, a'));
    var items = Array.from(document.querySelectorAll('[class*="item"], [class*="card"], [class*="row"], tr, li'));
    var nameId = '{NAME_ID}';
    var phase1Id = '{PHASE1_ID}';
    var found = null;

    // 方法1: 直接找"继续办理"按钮（如果只有一个或第一个）
    var continueBtn = btns.find(b => (b.innerText||'').includes('继续办理'));
    if (continueBtn) {{
        continueBtn.click();
        return '点击了继续办理按钮: ' + (continueBtn.innerText||'').trim();
    }}

    // 方法2: 找包含企业名或nameId的容器内的按钮
    for (var i=0; i<items.length; i++) {{
        var itemText = items[i].innerText || '';
        var itemHtml = items[i].innerHTML || '';
        if (itemText.indexOf('美裕盈') >= 0 || itemHtml.indexOf(nameId) >= 0 ||
            itemHtml.indexOf(phase1Id) >= 0) {{
            var btn = items[i].querySelector('button, .el-button');
            if (btn && (btn.innerText||'').indexOf('继续') >= 0) {{
                btn.click();
                return '找到并点击: ' + btn.innerText;
            }}
        }}
    }}

    // 方法3: 找所有按钮文本
    var allBtnTexts = btns.map(b=>(b.innerText||'').trim()).filter(t=>t).slice(0,20).join(' | ');
    return '未找到继续办理, 现有按钮: ' + allBtnTexts + ', items数: ' + items.length;
}})()
"""
    result = js_eval(ws, find_and_click_js, mid=mid); mid += 1
    print(f"[click] {result.get('value','')}")
    time.sleep(5)

    # Step 3: 检测新标签页是否出现
    post_tabs = page_tabs()
    new_tab_ids = {t["id"] for t in post_tabs} - pre_tabs
    print(f"[tabs] 原有: {len(pre_tabs)}, 新出现: {len(new_tab_ids)}")

    target_ws = None
    if new_tab_ids:
        new_tab = next(t for t in post_tabs if t["id"] in new_tab_ids)
        print(f"[new_tab] {new_tab.get('url','')[:80]}")
        target_ws = connect_tab(new_tab)
    else:
        # 没有新标签，可能在当前页
        target_ws = ws
        print("[no_new_tab] 没有新标签，使用当前页签")

    # Step 4: 在目标页签上等待 core.html / ComplementInfo 加载
    time.sleep(15)
    mid2 = 1
    cur2 = js_eval(target_ws, "window.location.href", mid=mid2); mid2 += 1
    print(f"[target] URL: {cur2.get('value','')[:100]}")

    # 注入 Authorization
    js_eval(target_ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid2); mid2 += 1

    # Step 5: 启用 Fetch 拦截
    send_msg(target_ws, "Fetch.enable", {
        "patterns": [{"urlPattern": "*ComplementInfo/operationBusinessDataInfo*",
                       "requestStage": "Request"}]
    }, mid=mid2); mid2 += 1
    print("[fetch] 拦截已启用")

    # 后台监听
    captured = {"body": None, "done": False}
    def listen_loop():
        lws = connect_tab(page_tabs()[-1])  # 连接最新页签
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
                        print(f"\n✅ 捕获! ({len(body_str)} bytes)")
                        try:
                            captured["body"] = json.loads(body_str)
                        except Exception:
                            captured["body"] = body_str
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
    threading.Thread(target=listen_loop, daemon=True).start()

    # Step 6: JS 自动填写并点击保存
    print("[wait] 等待表单加载 (15s)...")
    time.sleep(15)

    fill_js = """
(function() {
    var res = [];
    // 单选: 找带"否"的 label 下面的 radio
    var labels = Array.from(document.querySelectorAll('label'));
    var noLabels = labels.filter(l => (l.innerText||'').trim() === '否');
    noLabels.forEach(function(l) {
        var inp = l.querySelector('input[type=radio]') ||
                  (l.previousElementSibling && l.previousElementSibling.querySelector('input'));
        if (inp) { inp.click(); inp.dispatchEvent(new Event('change',{bubbles:true})); }
    });
    res.push('否 labels clicked: ' + noLabels.length);

    // 也直接尝试 value=2 的 radio
    document.querySelectorAll('input[type=radio][value="2"]').forEach(function(r) {
        r.click(); r.dispatchEvent(new Event('change',{bubbles:true}));
    });

    // 党员人数 input
    document.querySelectorAll('input').forEach(function(inp) {
        var ctx = '';
        var p = inp.parentElement;
        for (var j=0; j<8&&p; j++) { ctx += p.innerText||''; p=p.parentElement; }
        if (ctx.indexOf('党员') >= 0 || (inp.placeholder||'').indexOf('党员')>=0) {
            inp.value = '0';
            inp.dispatchEvent(new Event('input',{bubbles:true}));
            inp.dispatchEvent(new Event('change',{bubbles:true}));
            res.push('党员 input set 0');
        }
    });
    return res.join('; ');
})()
"""
    fr = js_eval(target_ws, fill_js, mid=mid2); mid2 += 1
    print(f"[fill] {fr.get('value','')}")
    time.sleep(2)

    click_js = """
(function() {
    var btns = Array.from(document.querySelectorAll('button,.el-button'));
    var sb = btns.find(b => {
        var t = (b.innerText||b.textContent||'').trim();
        return t.includes('保存') || t.includes('下一步');
    });
    if (sb) { sb.click(); return '点击: '+sb.innerText.trim(); }
    return '未找到 ('+btns.length+'个按钮)';
})()
"""
    cr = js_eval(target_ws, click_js, mid=mid2); mid2 += 1
    print(f"[click_save] {cr.get('value','')}")

    # 等待捕获
    print("\n⏳ 等待请求 (90s)... 如未捕获请在浏览器操作")
    for i in range(90):
        if captured["done"]: break
        time.sleep(1)
        if i % 20 == 19:
            js_eval(target_ws, click_js, mid=mid2); mid2 += 1
            print(f"  ... {i+1}s 重试")

    captured["done"] = True
    if captured["body"]:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(captured["body"], f, ensure_ascii=False, indent=2)
        body = captured["body"] if isinstance(captured["body"], dict) else {}
        print(f"\n✅ 已保存: {OUT}")
        print(f"  keys: {list(body.keys())}")
        pd = body.get("partyBuildDto","无")
        print(f"  partyBuildDto: {json.dumps(pd, ensure_ascii=False)[:250]}")
        print(f"  signInfo: {body.get('signInfo')}")
    else:
        print("\n❌ 未捕获 - 请在浏览器手动保存后重跑")

if __name__ == "__main__":
    main()
