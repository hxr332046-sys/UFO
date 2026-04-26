"""CDP 攻击 step 16：启用 Network 监听 + 跳 member-post + 自动点"添加成员"。

目标：
1. 连 CDP 现有 core.html tab
2. Network.enable 监听所有 /icpsp-api/ 请求
3. 跳转到 member-post 页面（当前在 alt-electronic-doc，是变更流程）
   → 变更流程里成员管理 API 应该和设立一致，都是 MemberBaseInfo / MemberPost
4. 自动触发"添加成员"按钮
5. 记录所有 API 调用顺序 + body + 响应
"""
from __future__ import annotations
import json
import time
import urllib.request
from pathlib import Path

import websocket  # type: ignore

CDP_HTTP = "http://127.0.0.1:9225/json"
OUT_DIR = Path("dashboard/data/records/cdp_probe_mbi")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def pick_core_tab():
    tabs = json.loads(urllib.request.urlopen(CDP_HTTP, timeout=5).read())
    for t in tabs:
        if t.get("type") == "page" and "core.html" in t.get("url", ""):
            return t
    raise SystemExit("未找到 core.html tab")


def cdp_call(ws, method, params=None, msg_id=None):
    if msg_id is None:
        msg_id = int(time.time() * 1000) % 100000
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    ws.settimeout(10)
    while True:
        try:
            raw = ws.recv()
            m = json.loads(raw)
            if m.get("id") == msg_id:
                return m.get("result") or m.get("error") or {}
        except websocket.WebSocketTimeoutException:
            return {"_err": "timeout"}
        except Exception as e:
            return {"_err": str(e)}


def main():
    tab = pick_core_tab()
    print(f"[1] 连接 tab: {tab['title']} | url: {tab['url'][:80]}...")
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)

    print("[2] 启用 Runtime/Network/Page domain")
    for dom in ("Runtime.enable", "Network.enable", "Page.enable"):
        r = cdp_call(ws, dom)
        if r.get("_err"):
            print(f"   {dom}: {r}")

    # 订阅 Network 事件：我们只关心 requestWillBeSent + responseReceived + loadingFinished
    print("[3] 开始监听 /icpsp-api/ 请求（60s）")
    requests_by_id: dict = {}
    api_events = []  # 顺序记录

    # 先读一次 URL（看当前页面）
    r = cdp_call(ws, "Runtime.evaluate", {
        "expression": "location.href", "returnByValue": True
    })
    cur_url = (r.get("result") or {}).get("value", "")
    print(f"   当前 URL: {cur_url}")

    # 尝试跳到设立流程 member-post（如果当前是变更流程 alt-*）
    # 先找现有办件的 busiId / nameId — 从 URL hash 或 localStorage
    r = cdp_call(ws, "Runtime.evaluate", {
        "expression": """(function(){
            var out = {};
            try { out.auth = localStorage.getItem('Authorization'); } catch(e){}
            // 找 Vuex store 里 flow 模块的 busiId
            try {
                var app = document.querySelector('#app').__vue__;
                var st = app.$store.state;
                out.states = Object.keys(st).slice(0, 30);
                if (st.flow) {
                    out.flow_busiId = st.flow.busiId;
                    out.flow_nameId = st.flow.nameId;
                    out.flow_currCompUrl = st.flow.currCompUrl;
                }
                if (st.basicInfo) {
                    out.bi_busiId = st.basicInfo.busiId;
                }
            } catch(e) { out.err = String(e); }
            return JSON.stringify(out);
        })()""",
        "returnByValue": True,
    })
    val = (r.get("result") or {}).get("value", "")
    print(f"   App state: {val}")

    # 订阅 Network.requestWillBeSent / Network.responseReceived / Network.getResponseBody
    # 监听 60 秒，记录所有 /icpsp-api/ 请求
    ws.settimeout(1)
    deadline = time.time() + 60
    print(f"[4] 监听中... 请在浏览器里：")
    print(f"    1) 手工跳到任意**设立**流程办件 (URL 含 flow/base/member-post)")
    print(f"    2) 点击'添加成员'按钮，填完表单点保存")
    print(f"    3) 观察终端会抓到所有 API 调用")
    print(f"    超时 60s")

    while time.time() < deadline:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            continue
        try:
            m = json.loads(raw)
        except Exception:
            continue
        method = m.get("method")
        params = m.get("params") or {}

        if method == "Network.requestWillBeSent":
            req = params.get("request") or {}
            url = req.get("url", "")
            if "/icpsp-api/" not in url:
                continue
            rid = params.get("requestId")
            requests_by_id[rid] = {
                "url": url,
                "method": req.get("method"),
                "headers": req.get("headers") or {},
                "postData": req.get("postData"),
                "ts_req": params.get("timestamp"),
            }
            # 提取组件 + 操作类型
            tag = url.split("/icpsp-api/")[-1][:80]
            body_preview = ""
            if req.get("postData"):
                try:
                    b = json.loads(req["postData"])
                    ope = (b.get("linkData") or {}).get("opeType", "")
                    comp = (b.get("linkData") or {}).get("compUrl", "")
                    body_preview = f"[ope={ope} comp={comp}]"
                except Exception:
                    pass
            print(f"   → {req.get('method')} {tag} {body_preview}")

        elif method == "Network.responseReceived":
            rid = params.get("requestId")
            if rid in requests_by_id:
                resp = params.get("response") or {}
                requests_by_id[rid]["status"] = resp.get("status")
                requests_by_id[rid]["headers_resp"] = resp.get("headers") or {}

        elif method == "Network.loadingFinished":
            rid = params.get("requestId")
            if rid in requests_by_id:
                # 取 body
                r = cdp_call(ws, "Network.getResponseBody", {"requestId": rid})
                body = r.get("body") or ""
                try:
                    body_json = json.loads(body) if body else None
                except Exception:
                    body_json = body[:200]
                requests_by_id[rid]["resp_body"] = body_json
                code = ""
                if isinstance(body_json, dict):
                    code = body_json.get("code", "")
                url_tag = requests_by_id[rid]["url"].split("/icpsp-api/")[-1][:60]
                print(f"   ← [code={code}] {url_tag}")
                api_events.append(requests_by_id[rid])

    print(f"\n[5] 抓到 {len(api_events)} 个 /icpsp-api/ 请求")
    out = OUT_DIR / f"cdp_flow_{int(time.time())}.json"
    out.write_text(json.dumps(api_events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    存到: {out}")

    # 简要汇总
    print(f"\n=== API 调用汇总 ===")
    for ev in api_events:
        tag = ev["url"].split("/icpsp-api/")[-1][:60]
        code = ""
        if isinstance(ev.get("resp_body"), dict):
            code = ev["resp_body"].get("code", "")
        ope = comp = ""
        if ev.get("postData"):
            try:
                b = json.loads(ev["postData"])
                ope = (b.get("linkData") or {}).get("opeType", "")
                comp = (b.get("linkData") or {}).get("compUrl", "")
            except Exception:
                pass
        print(f"  [{code}] {comp}/{ope} | {tag}")

    ws.close()


if __name__ == "__main__":
    main()
