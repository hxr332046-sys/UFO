#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通过 CDP 抓取政务平台的认证机制
- Cookie 结构
- 请求头 Token 模式
- API 基础路径
- 认证流程
"""

import json
import time
import requests
import websocket
import os

CDP_PORT = 9225
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "survey")


def get_ws_url():
    pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    return None


def cdp_eval(ws, js, msg_id=1, timeout=15):
    ws.send(json.dumps({
        "id": msg_id,
        "method": "Runtime.evaluate",
        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}
    }))
    while True:
        result = json.loads(ws.recv())
        if result.get("id") == msg_id:
            return result.get("result", {}).get("result", {}).get("value")


def main():
    ws_url = get_ws_url()
    if not ws_url:
        print("ERROR: No CDP page found")
        return
    ws = websocket.create_connection(ws_url, timeout=15)

    # 1. Cookies
    ws.send(json.dumps({"id": 1, "method": "Network.getCookies"}))
    cookies_result = json.loads(ws.recv())
    cookies = cookies_result.get("result", {}).get("cookies", [])
    print(f"=== COOKIES ({len(cookies)}) ===")
    auth_cookies = []
    for c in cookies:
        print(f"  {c.get('name','')}={c.get('value','')[:40]}... domain={c.get('domain','')} path={c.get('path','')} httpOnly={c.get('httpOnly',False)} secure={c.get('secure',False)}")
        if any(kw in c.get('name', '').lower() for kw in ['token', 'auth', 'session', 'sid', 'jsession', 'ticket', 'user', 'login', 'access']):
            auth_cookies.append(c)

    # 2. localStorage auth data
    local_storage = cdp_eval(ws, """
        (function() {
            var result = {};
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                var val = localStorage.getItem(key);
                result[key] = val.substring(0, 200);
            }
            return result;
        })()
    """, msg_id=2)
    print(f"\n=== LOCALSTORAGE ({len(local_storage) if local_storage else 0}) ===")
    auth_storage = {}
    if local_storage:
        for k, v in local_storage.items():
            print(f"  {k}={v[:80]}")
            if any(kw in k.lower() for kw in ['token', 'auth', 'user', 'login', 'ticket', 'session', 'info', 'name', 'id']):
                auth_storage[k] = v

    # 3. sessionStorage auth data
    session_storage = cdp_eval(ws, """
        (function() {
            var result = {};
            for (var i = 0; i < sessionStorage.length; i++) {
                var key = sessionStorage.key(i);
                var val = sessionStorage.getItem(key);
                result[key] = val.substring(0, 200);
            }
            return result;
        })()
    """, msg_id=3)
    print(f"\n=== SESSIONSTORAGE ({len(session_storage) if session_storage else 0}) ===")
    if session_storage:
        for k, v in session_storage.items():
            print(f"  {k}={v[:80]}")

    # 4. Vuex store auth state
    vuex_state = cdp_eval(ws, """
        (function() {
            var app = document.getElementById('app');
            if (!app || !app.__vue__ || !app.__vue__.$store) return null;
            var state = app.__vue__.$store.state;
            var result = {};
            var keys = Object.keys(state);
            for (var i = 0; i < keys.length; i++) {
                var k = keys[i];
                var v = state[k];
                if (typeof v === 'object' && v !== null) {
                    var subKeys = Object.keys(v);
                    result[k] = {};
                    for (var j = 0; j < subKeys.length; j++) {
                        var sk = subKeys[j];
                        var sv = v[sk];
                        if (typeof sv === 'object' && sv !== null) {
                            result[k][sk] = Object.keys(sv);
                        } else {
                            result[k][sk] = String(sv).substring(0, 100);
                        }
                    }
                } else {
                    result[k] = String(v).substring(0, 100);
                }
            }
            return result;
        })()
    """, msg_id=4)
    print(f"\n=== VUEX STATE ===")
    if vuex_state:
        print(json.dumps(vuex_state, ensure_ascii=False, indent=2))

    # 5. Axios default headers (auth tokens in request interceptor)
    axios_config = cdp_eval(ws, """
        (function() {
            var app = document.getElementById('app');
            if (!app || !app.__vue__) return {error: 'No Vue instance'};
            var vm = app.__vue__;

            // Try to find axios instance
            var axios = vm.$axios || window.axios;
            if (!axios) return {error: 'No axios found'};

            var config = {};
            try { config.defaults = { headers: axios.defaults.headers }; } catch(e) {}
            try { config.interceptors = { request: axios.interceptors.request.handlers ? axios.interceptors.request.handlers.length : 0, response: axios.interceptors.response.handlers ? axios.interceptors.response.handlers.length : 0 }; } catch(e) {}

            // Check Vue prototype
            var protoKeys = Object.keys(vm.$options.proto || {});
            try {
                var $http = vm.$http || vm.$axios;
                if ($http && $http.defaults) {
                    config.httpDefaults = { headers: $http.defaults.headers };
                }
            } catch(e) {}

            return config;
        })()
    """, msg_id=5)
    print(f"\n=== AXIOS CONFIG ===")
    if axios_config:
        print(json.dumps(axios_config, ensure_ascii=False, indent=2))

    # 6. Check for auth token patterns in cookies/localStorage
    auth_analysis = cdp_eval(ws, """
        (function() {
            var result = {
                hasCookieAuth: false,
                hasBearerToken: false,
                hasJwtToken: false,
                authMethods: []
            };

            // Check cookies
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var parts = cookies[i].trim().split('=');
                var name = parts[0];
                var val = parts[1] || '';
                if (/token|auth|session|sid|ticket/i.test(name)) {
                    result.hasCookieAuth = true;
                    result.authMethods.push('cookie: ' + name);
                    if (/^eyJ/i.test(val)) result.hasJwtToken = true;
                    if (/^Bearer /i.test(val)) result.hasBearerToken = true;
                }
            }

            // Check localStorage
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                var val = localStorage.getItem(key) || '';
                if (/token|auth|ticket|user/i.test(key)) {
                    result.authMethods.push('localStorage: ' + key);
                    if (/^eyJ/i.test(val)) result.hasJwtToken = true;
                }
            }

            // Check meta tags for auth info
            var metaTags = document.querySelectorAll('meta');
            for (var i = 0; i < metaTags.length; i++) {
                var name = metaTags[i].getAttribute('name') || '';
                if (/csrf|token|auth/i.test(name)) {
                    result.authMethods.push('meta: ' + name + '=' + (metaTags[i].getAttribute('content') || '').substring(0, 40));
                }
            }

            return result;
        })()
    """, msg_id=6)
    print(f"\n=== AUTH ANALYSIS ===")
    if auth_analysis:
        print(json.dumps(auth_analysis, ensure_ascii=False, indent=2))

    # 7. Capture recent XHR requests by enabling Network and reading HAR-like data
    # First enable Network
    ws.send(json.dumps({"id": 7, "method": "Network.enable", "params": {}}))
    _ = json.loads(ws.recv())

    # Navigate to trigger some API calls
    cdp_eval(ws, """
        var app = document.getElementById('app');
        if (app && app.__vue__) {
            app.__vue__.$router.push('/index/page');
        }
    """, msg_id=8)

    # Collect network requests for 5 seconds
    api_requests = []
    ws.settimeout(1)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
            method = msg.get("method", "")
            if method == "Network.requestWillBeSent":
                req = msg.get("params", {}).get("request", {})
                url = req.get("url", "")
                if "zhjg.scjdglj" in url and not url.endswith((".js", ".css", ".png", ".jpg", ".ico", ".woff", ".svg")):
                    api_requests.append({
                        "url": url,
                        "method": req.get("method", ""),
                        "headers": dict(list(req.get("headers", {}).items())[:15]),
                        "hasRequestBody": bool(req.get("postData"))
                    })
        except:
            continue

    print(f"\n=== API REQUESTS CAPTURED ({len(api_requests)}) ===")
    for r in api_requests[:20]:
        print(f"  {r['method']} {r['url'][:100]}")
        auth_headers = {k: v[:50] for k, v in r.get("headers", {}).items() if any(kw in k.lower() for kw in ['auth', 'token', 'cookie', 'session', 'x-'])}
        if auth_headers:
            print(f"    auth headers: {json.dumps(auth_headers, ensure_ascii=False)}")

    ws.close()

    # Save all results
    result = {
        "cookies": cookies,
        "auth_cookies": auth_cookies,
        "local_storage": local_storage,
        "auth_storage": auth_storage,
        "session_storage": session_storage,
        "vuex_state": vuex_state,
        "axios_config": axios_config,
        "auth_analysis": auth_analysis,
        "api_requests": api_requests[:30]
    }

    out_path = os.path.join(OUT_DIR, "auth_analysis.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nAuth analysis saved to {out_path}")


if __name__ == "__main__":
    main()
