"""CDP 劫持 - 让浏览器为我们新办件加载 member-base-info 页，监听真实 API 流量。

策略：
1. Python 纯协议跑 phase2 step 1-15 → 拿 establish_busiId + 新 signInfo
2. CDP 连 core.html tab
3. Network.enable 监听所有 /icpsp-api/ 请求（含 request + response + body）
4. Runtime.evaluate 设 Vuex store.flow 状态为新办件 + router.push('/flow/base/member-base-info')
5. 等 Vue 页面 load 完（自动触发 MBI load API）
6. 抓到完整的浏览器真实 MBI load request 和响应
7. 若加载成功，再找 UI 保存按钮 click 触发 MBI save → 抓真实 save request
8. 对比浏览器真实 request 和我们 Python 发的，找差异
"""
from __future__ import annotations
import json
import sys
import time
import threading
import urllib.request
from pathlib import Path

import websocket  # type: ignore

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))

CDP_HTTP = "http://127.0.0.1:9225/json"
OUT_DIR = Path("dashboard/data/records/cdp_probe_mbi")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def pick_core_tab():
    tabs = json.loads(urllib.request.urlopen(CDP_HTTP, timeout=5).read())
    for t in tabs:
        if t.get("type") == "page" and "core.html" in t.get("url", ""):
            return t
    raise SystemExit("未找到 core.html tab")


def cdp(ws, method, params=None, mid=None, timeout=10):
    if mid is None:
        mid = int(time.time() * 10000) % 1000000
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    ws.settimeout(timeout)
    while True:
        try:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result") or m.get("error") or {}
            # 其他事件忽略
        except websocket.WebSocketTimeoutException:
            return {"_err": "timeout"}


def ev(ws, expr, await_p=False, timeout=10):
    r = cdp(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "awaitPromise": await_p
    }, timeout=timeout)
    if r.get("exceptionDetails"):
        return {"_exc": str(r["exceptionDetails"])[:500]}
    return (r.get("result") or {}).get("value")


# 收集到的 API 流
api_flow: list = []
requests_by_id: dict = {}


def network_listener(ws, duration_sec: int):
    """后台监听 Network 事件。"""
    deadline = time.time() + duration_sec
    ws.settimeout(1.0)
    while time.time() < deadline:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            break
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
                "headers": dict(req.get("headers") or {}),
                "postData": req.get("postData"),
                "ts": time.time(),
            }

        elif method == "Network.responseReceived":
            rid = params.get("requestId")
            if rid in requests_by_id:
                resp = params.get("response") or {}
                requests_by_id[rid]["status"] = resp.get("status")
                requests_by_id[rid]["resp_headers"] = dict(resp.get("headers") or {})

        elif method == "Network.loadingFinished":
            rid = params.get("requestId")
            if rid not in requests_by_id:
                continue
            # 获取响应 body（需要同步发 Network.getResponseBody）
            try:
                ws.send(json.dumps({
                    "id": 900000 + len(api_flow),
                    "method": "Network.getResponseBody",
                    "params": {"requestId": rid},
                }))
                # 等响应（短超时）
                start = time.time()
                while time.time() - start < 3:
                    raw2 = ws.recv()
                    m2 = json.loads(raw2)
                    if m2.get("id") == 900000 + len(api_flow):
                        body_str = (m2.get("result") or {}).get("body") or ""
                        try:
                            requests_by_id[rid]["resp_body"] = json.loads(body_str)
                        except Exception:
                            requests_by_id[rid]["resp_body"] = body_str[:500]
                        break
            except Exception:
                pass
            api_flow.append(requests_by_id[rid])


def run_phase2_to_step15():
    """Python 纯协议跑到 step 15 拿新办件 establish_busiId。"""
    print("=" * 60)
    print("[Phase A] Python 纯协议推进新办件到 step 15")
    print("=" * 60)
    from icpsp_api_client import ICPSPClient  # type: ignore
    import phase2_protocol_driver as drv  # type: ignore

    CASE = json.load(open("docs/case_有为诚.json", encoding="utf-8"))
    BUSI_ID = "2047533149403086848"
    NAME_ID = "2047533981928857602"

    client = ICPSPClient()
    ctx = drv.Phase2Context(case=CASE, busi_id=BUSI_ID, ent_type="4540")
    ctx.name_id = NAME_ID
    ctx.snapshot["nameId"] = NAME_ID

    drv.step12_establish_location(client, ctx)
    time.sleep(0.4)
    try: drv.step13_ybb_select(client, ctx)
    except Exception: pass
    time.sleep(0.4)
    drv.step14_basicinfo_load(client, ctx)
    time.sleep(0.4)
    r15 = drv.step15_basicinfo_save(client, ctx)
    ebid = ctx.snapshot.get("establish_busiId")
    sig = ctx.snapshot.get("basicinfo_signInfo") or ctx.snapshot.get("last_sign_info")
    assert r15.get("code") == "00000" and ebid, f"step 15 failed: {r15}"
    print(f"  establish_busiId = {ebid}")
    print(f"  signInfo = {sig}")
    return {"ebid": ebid, "nameId": NAME_ID, "entType": "4540", "busiType": "02",
            "signInfo": sig}


def main():
    info = run_phase2_to_step15()

    print("\n" + "=" * 60)
    print("[Phase B] CDP 劫持浏览器 core.html tab → 加载新办件 MBI 页")
    print("=" * 60)

    tab = pick_core_tab()
    print(f"  tab url: {tab['url'][:70]}...")
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)
    cdp(ws, "Runtime.enable")
    cdp(ws, "Network.enable", {"maxPostDataSize": 65536})
    cdp(ws, "Page.enable")

    # 启动后台监听线程
    listener = threading.Thread(
        target=network_listener, args=(ws, 45), daemon=True
    )
    listener.start()
    time.sleep(0.5)

    print(f"\n[B-1] 设置 Vuex store.flow + router.push 到 member-base-info")
    setup_js = f"""
    (function(){{
        try {{
            var app = document.querySelector('#app').__vue__;
            var st = app.$store.state;

            // 重置 flow 模块为我们的新办件
            if (!st.flow) st.flow = {{}};
            app.$set(st.flow, 'busiId', '{info["ebid"]}');
            app.$set(st.flow, 'nameId', '{info["nameId"]}');
            app.$set(st.flow, 'entType', '{info["entType"]}');
            app.$set(st.flow, 'busiType', '{info["busiType"]}');
            app.$set(st.flow, 'currCompUrl', 'MemberPost');
            app.$set(st.flow, 'status', '10');
            app.$set(st.flow, 'ywlbSign', '1');

            // 触发 router push
            app.$router.push({{
                path: '/flow/base/member-base-info',
                query: {{busiId: '{info["ebid"]}', nameId: '{info["nameId"]}'}}
            }}).catch(function(e){{ return 'router_err: ' + e.message; }});

            return JSON.stringify({{
                store_flow: st.flow,
                route_after: app.$router.currentRoute.path,
            }});
        }} catch(e) {{
            return 'ERR: ' + String(e);
        }}
    }})()
    """
    r = ev(ws, setup_js, timeout=15)
    print(f"  setup result: {r}")

    # 等 10s 让 Vue 加载 member-base-info 页（会触发 MBI load API）
    print(f"\n[B-2] 等待 15s 让 Vue 加载 MBI 页 + 监听 API 流量...")
    time.sleep(15)

    # 查看当前路由 + Vue 组件
    r = ev(ws, """(function(){
        try {
            var app = document.querySelector('#app').__vue__;
            var names = new Set();
            var all = document.querySelectorAll('*');
            for (var i=0; i<all.length; i++) {
                var v = all[i].__vue__;
                if (v && v.$options && v.$options.name) names.add(v.$options.name);
            }
            return JSON.stringify({
                cur_route: app.$router.currentRoute.path,
                comps: Array.from(names).filter(n=>/member|base|post|pool/i.test(n)),
            });
        } catch(e) { return 'ERR: ' + String(e); }
    })()""")
    print(f"  page state: {r}")

    # 如果 member-base-info 页已加载，找 vue 实例 + 试触发"保存"
    r = ev(ws, """(function(){
        try {
            var all = document.querySelectorAll('*');
            var mbi = null;
            for (var i=0; i<all.length; i++) {
                var v = all[i].__vue__;
                if (v && v.$options && v.$options.name === 'member-base-info') {
                    mbi = v; break;
                }
            }
            if (!mbi) return 'no_mbi_vm';
            var out = {
                name: mbi.$options.name,
                methods: Object.keys(mbi.$options.methods || {}).filter(k=>/save|submit|next|handle/i.test(k)).slice(0,20),
                data_keys: Object.keys(mbi._data || {}).slice(0, 40),
            };
            window.__mbiVm = mbi;
            return JSON.stringify(out);
        } catch(e) { return 'ERR: ' + String(e); }
    })()""")
    print(f"\n[B-3] member-base-info vm: {r}")

    # 再等 15s 监听可能发生的 API
    print(f"\n[B-4] 继续监听 15s... （若 UI 里有保存按钮会自动触发 MBI save）")
    time.sleep(15)

    # 停止监听（listener 会自然结束）
    listener.join(timeout=2)

    # 存下抓到的流量
    print(f"\n[B-5] 抓到 {len(api_flow)} 个 /icpsp-api/ 请求")
    out_file = OUT_DIR / f"cdp_hijack_flow_{int(time.time())}.json"
    out_file.write_text(json.dumps(api_flow, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  存到: {out_file}")

    # 简要汇总
    print(f"\n=== 抓到的 API 调用顺序 ===")
    for i, ev_ in enumerate(api_flow):
        tag = ev_["url"].split("/icpsp-api/")[-1][:70]
        code = ""
        rb = ev_.get("resp_body")
        if isinstance(rb, dict):
            code = rb.get("code", "")
        ope = comp = ""
        if ev_.get("postData"):
            try:
                b = json.loads(ev_["postData"])
                ope = (b.get("linkData") or {}).get("opeType", "")
                comp = (b.get("linkData") or {}).get("compUrl", "")
            except Exception:
                pass
        print(f"  {i+1:2d}. [{code}] {comp}/{ope:<8} | {tag}")

    # 把 MBI load/save 的 request + response 单独提取出来
    mbi_items = [e for e in api_flow if "MemberBaseInfo" in e["url"]]
    if mbi_items:
        print(f"\n=== 抓到 {len(mbi_items)} 个 MemberBaseInfo 请求 ===")
        for i, e in enumerate(mbi_items):
            single = OUT_DIR / f"cdp_mbi_{i+1}_{int(time.time())}.json"
            single.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  存到: {single}")

    ws.close()


if __name__ == "__main__":
    main()
