"""CDP 探查当前 core.html tab 状态（用于规划 step 16 自动攻击路径）。"""
from __future__ import annotations
import json
import time
import urllib.request

import websocket  # type: ignore

CDP_HTTP = "http://127.0.0.1:9225/json"


def pick_core_tab():
    tabs = json.loads(urllib.request.urlopen(CDP_HTTP, timeout=5).read())
    for t in tabs:
        if t.get("type") == "page" and "core.html" in t.get("url", ""):
            return t
    raise SystemExit("未找到 core.html tab")


def cdp(ws, method, params=None, mid=None):
    if mid is None:
        mid = int(time.time() * 10000) % 1000000
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    ws.settimeout(10)
    while True:
        try:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result") or m.get("error") or {}
        except Exception:
            return {"_err": "to"}


def ev(ws, expr):
    r = cdp(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "awaitPromise": True
    })
    if r.get("exceptionDetails"):
        return {"_exc": str(r["exceptionDetails"])[:500]}
    return (r.get("result") or {}).get("value")


def main():
    tab = pick_core_tab()
    print(f"TAB: {tab['title']}")
    print(f"URL: {tab['url']}")
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)
    cdp(ws, "Runtime.enable")

    # 1. 当前 URL + localStorage.Authorization
    r = ev(ws, """(function(){
        return JSON.stringify({
            url: location.href,
            hash: location.hash,
            auth: (localStorage.getItem('Authorization') || '').slice(0,8) + '...',
            auth_len: (localStorage.getItem('Authorization') || '').length,
        });
    })()""")
    print(f"\n[1] 基本状态: {r}")

    # 2. Vuex store 核心 state
    r = ev(ws, """(function(){
        try {
            var app = document.querySelector('#app').__vue__;
            var st = app.$store.state;
            var out = {modules: Object.keys(st)};
            if (st.flow) out.flow = {
                busiId: st.flow.busiId, nameId: st.flow.nameId,
                currCompUrl: st.flow.currCompUrl,
                entType: st.flow.entType, busiType: st.flow.busiType,
                status: st.flow.status,
            };
            if (st.basicInfo) out.bi_busiId = st.basicInfo.busiId;
            if (st.memberPost) out.mp = {
                board: st.memberPost.board,
                boardSup: st.memberPost.boardSup,
                personList_len: (st.memberPost.personList || []).length,
            };
            return JSON.stringify(out, null, 2);
        } catch(e) { return 'ERR: ' + String(e); }
    })()""")
    print(f"\n[2] Vuex store:\n{r}")

    # 3. 当前页面组件（判断是否在 member-post 附近）
    r = ev(ws, """(function(){
        var seen = new Set();
        var names = [];
        var all = document.querySelectorAll('*');
        for (var i=0; i<all.length; i++) {
            var v = all[i].__vue__;
            if (!v || !v.$options || seen.has(v)) continue;
            seen.add(v);
            if (v.$options.name) names.push(v.$options.name);
        }
        return JSON.stringify({
            total: names.length,
            unique: Array.from(new Set(names)).sort(),
        });
    })()""")
    print(f"\n[3] 活跃 Vue 组件名:\n{r}")

    # 4. 看能否 route.push 到 member-post（探测路由）
    r = ev(ws, """(function(){
        try {
            var app = document.querySelector('#app').__vue__;
            var router = app.$router;
            var routes = router.options.routes || [];
            var flow_routes = [];
            function walk(rts, prefix) {
                rts.forEach(function(r){
                    var p = (prefix||'') + '/' + (r.path || '');
                    if (r.path && (r.path.indexOf('member') >= 0 || r.path.indexOf('base') >= 0 || r.path.indexOf('flow') >= 0)) {
                        flow_routes.push(p + ' [' + (r.name||'') + ']');
                    }
                    if (r.children) walk(r.children, p);
                });
            }
            walk(routes, '');
            return JSON.stringify(flow_routes.slice(0, 30));
        } catch(e) { return 'ERR: ' + String(e); }
    })()""")
    print(f"\n[4] 路由表（含 flow/base/member 关键词）:\n{r}")

    ws.close()


if __name__ == "__main__":
    main()
