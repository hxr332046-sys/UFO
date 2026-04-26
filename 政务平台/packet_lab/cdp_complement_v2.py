#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP v2: 注入已有 Python session → 浏览器打开 ComplementInfo → 拦截保存请求
"""
import json, time, sys, threading, pickle
from pathlib import Path
import requests, websocket

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

CDP_PORT = 9225
NAME_ID  = "2047910192228147201"
BASE     = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
TYRZ     = "tyrz.zwfw.gxzf.gov.cn"
PKL      = ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"
AUTH_J   = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
OUT      = ROOT / "packet_lab" / "out" / "complement_info_save_body.json"

# 最终导航目标
TARGET = (f"{BASE}/icpsp-web-pc/core.html#/flow/base"
          f"?fromProject=core&busiType=02_4&entType=4540"
          f"&nameId={NAME_ID}&visaFree=true")

# ── 工具 ──────────────────────────────────────────────────────────────────

def tabs():
    return requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()

def page_ws():
    for p in tabs():
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    return None

def load_auth():
    auth = json.loads(open(AUTH_J, encoding="utf-8").read()).get("Authorization","")
    jar  = pickle.load(open(PKL,"rb"))
    cks  = [{"name":c.name,"value":c.value,"domain":c.domain,
              "path":c.path,"secure":c.secure,"httpOnly":False}
            for c in jar]
    return auth, cks

def connect():
    ws_url = page_ws()
    if not ws_url:
        raise RuntimeError("没找到可用页签")
    ws = websocket.WebSocket()
    ws.connect(ws_url, timeout=30)
    ws.settimeout(60)   # 导航等待时间长
    return ws

def send(ws, method, params=None, mid=1):
    ws.send(json.dumps({"id":mid,"method":method,"params":params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid:
            return r

def js(ws, expr, mid=1, await_p=False):
    r = send(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True,
        "awaitPromise": await_p, "timeout": 25000}, mid=mid)
    return (r.get("result") or {}).get("result") or {}

def wait_url_contains(ws, keyword, timeout=60, poll=2):
    """等待当前页面 URL 包含指定关键字。"""
    t0 = time.time()
    while time.time()-t0 < timeout:
        r = js(ws, "window.location.href", mid=90)
        url = r.get("value","")
        print(f"  URL={url[:80]}")
        if keyword in url:
            return True
        time.sleep(poll)
    return False

# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    auth, cks = load_auth()
    print(f"[auth] token={auth[:8]}... cookies={len(cks)}")

    ws = connect()
    mid = 1
    send(ws, "Network.enable", {}, mid=mid); mid+=1

    # Step 1: 注入 cookies（所有域名）
    for ck in cks:
        try:
            send(ws, "Network.setCookie", ck, mid=mid); mid+=1
        except Exception:
            pass
    print(f"[cookies] 注入 {len(cks)} 个")

    # Step 2: 先导航到 tyrz 域确保 cookie 被接受
    print("[nav] 先访问 tyrz 域...")
    send(ws, "Page.navigate", {"url": f"https://{TYRZ}/"}, mid=mid); mid+=1
    time.sleep(3)

    # 重新注入（有时候导航会清空）
    for ck in cks:
        if TYRZ in (ck.get("domain","") or ""):
            try:
                send(ws, "Network.setCookie", ck, mid=mid); mid+=1
            except Exception:
                pass

    # Step 3: 导航到 9087 portal
    print("[nav] 导航到 9087 portal...")
    send(ws, "Page.navigate", {"url": BASE + "/icpsp-web-pc/portal.html"}, mid=mid); mid+=1
    time.sleep(10)   # 等 SPA 初始化完成

    # 检查当前 URL
    cur = js(ws, "window.location.href", mid=mid); mid+=1
    cur_url = cur.get("value","")
    print(f"[nav] portal URL: {cur_url[:100]}")

    if "tyrz" in cur_url or "login" in cur_url:
        print("[!] portal 也跳到登录页 — session 注入失败")
        print("    请手动在弹出的浏览器中扫码登录...")
        # 等待用户登录
        for _ in range(60):
            time.sleep(2)
            u = js(ws, "window.location.href", mid=mid).get("value",""); mid+=1
            if "9087" in u or "portal" in u:
                print(f"[nav] 检测到登录成功: {u[:60]}")
                break
        time.sleep(5)

    # 从 portal 内部注入 Authorization 到 localStorage
    js(ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid); mid+=1
    print("[auth] localStorage Authorization 已注入")
    time.sleep(2)

    # 从 portal 内部用 JS 跳转（不用 CDP Page.navigate，避免触发额外 SSO 检查）
    print("[nav] 从 portal 内部 JS 跳转到 core.html...")
    nav_js = f"window.location.href = {json.dumps(TARGET)}; 'ok'"
    js(ws, nav_js, mid=mid); mid+=1
    print("[nav] 等待 core.html 加载 (20s)...")
    time.sleep(20)

    # 重连（JS 导航后页面可能已刷新）
    try: ws.close()
    except Exception: pass
    ws_url3 = page_ws()
    ws = websocket.WebSocket(); ws.connect(ws_url3, timeout=30); ws.settimeout(60)
    mid = 1

    cur2 = js(ws, "window.location.href", mid=mid); mid+=1
    cur_url2 = cur2.get('value','')
    print(f"[nav] core.html URL: {cur_url2[:100]}")
    if "tyrz" in cur_url2 or "login" in cur_url2:
        print("[!] 还是跳到登录页 — 再注入再等待...")
        # 注入到 tyrz 页面的 localStorage 没用，先等用户手动操作
        print("    *** 请在浏览器中手动登录，然后按回车继续 ***")
        input()
        ws.close()
        ws = websocket.WebSocket(); ws.connect(page_ws(), timeout=30); ws.settimeout(60)
        mid = 1

    # 再次注入 Authorization
    _send_ws = ws
    js(ws, f"localStorage.setItem('Authorization',{json.dumps(auth)})", mid=mid); mid+=1
    time.sleep(5)

    # Step 4: 启用 Fetch 拦截
    send(ws, "Fetch.enable", {
        "patterns": [{"urlPattern":"*ComplementInfo/operationBusinessDataInfo*",
                      "requestStage":"Request"},
                     {"urlPattern":"*loadBusinessDataInfo*",
                      "requestStage":"Request"}]
    }, mid=mid); mid+=1
    print("[fetch] 拦截已启用，等待 ComplementInfo 请求...")

    captured = {"body": None, "done": False, "preload": None}

    def listen():
        local_ws = connect()
        while not captured["done"]:
            try:
                raw = local_ws.recv()
                msg = json.loads(raw)
                m = msg.get("method","")
                if m == "Fetch.requestPaused":
                    p = msg.get("params",{})
                    req = p.get("request",{})
                    url = req.get("url","")
                    body_str = req.get("postData") or ""
                    rid = p.get("requestId")
                    if "ComplementInfo/operationBusinessDataInfo" in url and body_str:
                        print(f"\n✅ 捕获 save body! ({len(body_str)} bytes)")
                        try:
                            captured["body"] = json.loads(body_str)
                        except Exception:
                            captured["body"] = body_str
                        captured["done"] = True
                    if rid:
                        local_ws.send(json.dumps({"id":9990+hash(rid)%100,
                            "method":"Fetch.continueRequest","params":{"requestId":rid}}))
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                print(f"[listen] {e}")
                break

    t = threading.Thread(target=listen, daemon=True)
    t.start()

    # Step 5: 等待 ComplementInfo 组件加载，然后自动填写
    print("[wait] 等待 ComplementInfo 页面加载 (15s)...")
    time.sleep(15)

    # 尝试找 Vue 实例并填写 partyBuildDto
    fill_js = """
(function() {
    var result = [];

    // 方法1: 找所有单选框，选"否"
    var radios = document.querySelectorAll('input[type="radio"]');
    var clickedRadios = 0;
    for (var i = 0; i < radios.length; i++) {
        var v = radios[i].value;
        if (['2','否','false','0','no'].indexOf(v) >= 0 ||
            radios[i].labels && radios[i].labels[0] &&
            (radios[i].labels[0].innerText || '').indexOf('否') >= 0) {
            radios[i].click();
            radios[i].dispatchEvent(new Event('change', {bubbles:true}));
            clickedRadios++;
        }
    }
    result.push('radios clicked: ' + clickedRadios);

    // 方法2: 找 numParM input 填0
    var inputs = document.querySelectorAll('input');
    for (var i = 0; i < inputs.length; i++) {
        var el = inputs[i];
        var label = '';
        var p = el.parentElement;
        for (var j=0; j<8 && p; j++) { label += (p.innerText||''); p=p.parentElement; }
        if (label.indexOf('党员') >= 0 || (el.placeholder||'').indexOf('党员') >= 0) {
            el.value = '0';
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            result.push('numParM set to 0');
        }
    }

    // 方法3: 找 Vue 实例直接设 partyBuildDto
    try {
        var allEls = document.querySelectorAll('*');
        for (var i=0; i<allEls.length; i++) {
            var vkey = Object.keys(allEls[i]).find(k => k.startsWith('__vue'));
            if (!vkey) continue;
            var vm = allEls[i][vkey];
            if (vm && vm.$data) {
                var d = vm.$data;
                if (d.partyBuildDto !== undefined) {
                    var dto = d.partyBuildDto;
                    if (dto) {
                        if (typeof dto.estParSign !== 'undefined') dto.estParSign = '2';
                        if (typeof dto.numParM !== 'undefined') dto.numParM = '0';
                        if (dto.xzDto) { dto.xzDto.estParSign='2'; dto.xzDto.numParM='0'; }
                    }
                    result.push('Vue partyBuildDto patched at ' + i);
                }
                if (d.formData !== undefined && d.formData && d.formData.partyBuildDto) {
                    d.formData.partyBuildDto.estParSign = '2';
                    result.push('Vue formData.partyBuildDto patched');
                }
            }
        }
    } catch(e) {
        result.push('Vue patch error: ' + e.message);
    }

    return result.join('; ');
})()
"""
    fill_r = js(ws, fill_js, mid=mid); mid+=1
    print(f"[fill] {fill_r.get('value','')}")
    time.sleep(2)

    # 尝试点击保存按钮
    click_js = """
(function() {
    var btns = Array.from(document.querySelectorAll('button, .el-button'));
    var saveBtn = btns.find(b => {
        var t = (b.innerText || b.textContent || '').trim();
        return t.indexOf('保存') >= 0 || t.indexOf('下一步') >= 0;
    });
    if (saveBtn) {
        saveBtn.click();
        return '点击: ' + (saveBtn.innerText||'').trim();
    }
    return '未找到保存按钮 (共' + btns.length + '个按钮)';
})()
"""
    click_r = js(ws, click_js, mid=mid); mid+=1
    print(f"[click] {click_r.get('value','')}")

    # 等待捕获
    print("\n⏳ 等待捕获请求 (最多90秒)...")
    print("   如果页面需要操作，请在打开的浏览器窗口中操作。")
    for i in range(90):
        if captured["done"]:
            break
        time.sleep(1)
        if i % 15 == 14:
            # 再试一次点击
            js(ws, click_js, mid=mid); mid+=1
            print(f"  ... {i+1}s 重试点击保存")

    ws.close()
    captured["done"] = True

    if captured["body"]:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(captured["body"], f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已保存: {OUT}")
        body = captured["body"] if isinstance(captured["body"],dict) else {}
        print(f"  顶层 keys: {list(body.keys())}")
        pd = body.get("partyBuildDto","无")
        pf = body.get("partyBuildFlag","无")
        print(f"  partyBuildDto: {json.dumps(pd,ensure_ascii=False)[:200]}")
        print(f"  partyBuildFlag(顶层): {pf}")
        print(f"  signInfo: {body.get('signInfo')}")
    else:
        print("\n❌ 未捕获到请求 — 请在浏览器里手动操作后重跑")

if __name__ == "__main__":
    main()
