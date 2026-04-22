#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CDP website survey for 政务平台"""

import json
import websocket
import time
import requests

CDP_PORT = 9225
CDP_HTTP = f"http://127.0.0.1:{CDP_PORT}"
GOV_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Flogin%2FauthPage&busiType=02_4&merge=Y"

def get_ws_url():
    pages = requests.get(f"{CDP_HTTP}/json", timeout=5).json()
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

# Get current page
ws_url = get_ws_url()
if not ws_url:
    print("ERROR: No CDP page found")
    exit(1)
print(f"Connecting: {ws_url}")
ws = websocket.create_connection(ws_url, timeout=15)

# 1. Page basic info
info = cdp_eval(ws, """
(function() {
    return {
        title: document.title,
        url: location.href,
        hostname: location.hostname,
        hash: location.hash,
        readyState: document.readyState
    };
})()
""")
print("=== PAGE INFO ===")
print(json.dumps(info, ensure_ascii=False, indent=2))

# 2. All navigation / menu / sidebar elements
navs = cdp_eval(ws, """
(function() {
    var selectors = 'nav, [class*="nav"], [class*="menu"], [class*="sidebar"], [class*="tab-bar"], [role="navigation"], [role="tablist"], [role="menubar"], [class*="header"], [class*="footer"]';
    var els = document.querySelectorAll(selectors);
    var result = [];
    for (var i = 0; i < Math.min(els.length, 20); i++) {
        var el = els[i];
        var links = el.querySelectorAll('a, [role="menuitem"], [role="tab"], [class*="menu-item"], [class*="nav-item"], [class*="tab-item"], li');
        var items = [];
        var seen = new Set();
        for (var j = 0; j < Math.min(links.length, 80); j++) {
            var l = links[j];
            var txt = (l.textContent || '').trim().substring(0, 50);
            if (!txt || seen.has(txt)) continue;
            seen.add(txt);
            items.push({
                text: txt,
                href: l.getAttribute('href') || l.getAttribute('data-href') || l.getAttribute('data-url') || '',
                cls: (l.className || '').substring(0, 60)
            });
        }
        result.push({
            tag: el.tagName,
            cls: (el.className || '').substring(0, 80),
            id: el.id || '',
            itemCount: items.length,
            items: items.slice(0, 30)
        });
    }
    return result;
})()
""")
print("\n=== NAVIGATION STRUCTURE ===")
if navs:
    for nav in navs:
        print(f"  [{nav.get('tag','')}] cls={nav.get('cls','')[:60]} id={nav.get('id','')} items={nav.get('itemCount',0)}")
        for item in nav.get("items", [])[:20]:
            href = item.get("href", "")
            if href and href.startswith("#"):
                href = "#" + href[1:40]
            elif href:
                href = href[:60]
            print(f"    -> {item.get('text','')[:40]} | href={href}")

# 3. All visible buttons and interactive elements
buttons = cdp_eval(ws, """
(function() {
    var btns = document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"], [class*="btn"]');
    var result = [];
    var seen = new Set();
    for (var i = 0; i < btns.length; i++) {
        var b = btns[i];
        var txt = (b.textContent || b.value || b.getAttribute('aria-label') || '').trim().substring(0, 40);
        if (!txt || seen.has(txt)) continue;
        seen.add(txt);
        result.push({
            text: txt,
            cls: (b.className || '').substring(0, 60),
            tag: b.tagName,
            type: b.type || ''
        });
    }
    return result.slice(0, 40);
})()
""")
print("\n=== BUTTONS & INTERACTIVE ELEMENTS ===")
if buttons:
    for b in buttons:
        print(f"  [{b.get('tag','')}] {b.get('text','')[:30]} | type={b.get('type','')} | cls={b.get('cls','')[:40]}")

# 4. Form elements
forms = cdp_eval(ws, """
(function() {
    var inputs = document.querySelectorAll('input, select, textarea');
    var result = [];
    for (var i = 0; i < Math.min(inputs.length, 50); i++) {
        var inp = inputs[i];
        result.push({
            tag: inp.tagName,
            type: inp.type || '',
            name: inp.name || '',
            id: inp.id || '',
            placeholder: inp.placeholder || '',
            cls: (inp.className || '').substring(0, 50)
        });
    }
    return result;
})()
""")
print("\n=== FORM ELEMENTS ===")
if forms:
    for f in forms:
        label = f.get("placeholder") or f.get("name") or f.get("id") or ""
        print(f"  [{f.get('tag','')}] type={f.get('type','')} name={f.get('name','')[:20]} id={f.get('id','')[:20]} placeholder={label[:30]}")

# 5. SPA routes (hash-based or history-based)
routes = cdp_eval(ws, """
(function() {
    var links = document.querySelectorAll('a[href]');
    var hrefs = new Set();
    for (var i = 0; i < links.length; i++) {
        var h = links[i].getAttribute('href');
        if (h && h !== '#' && h !== 'javascript:void(0)' && !h.startsWith('http')) {
            hrefs.add(h);
        }
    }
    return Array.from(hrefs).slice(0, 50);
})()
""")
print("\n=== INTERNAL ROUTES ===")
if routes:
    for r in routes:
        print(f"  {r}")

# 6. Framework detection
framework = cdp_eval(ws, """
(function() {
    var fw = [];
    if (window.Vue) fw.push('Vue ' + (Vue.version || ''));
    if (window.__VUE__) fw.push('Vue3');
    if (window.React) fw.push('React');
    if (window.__NEXT_DATA__) fw.push('Next.js');
    if (window.angular) fw.push('Angular');
    if (document.querySelector('[ng-app],[ng-controller],[data-ng-app]')) fw.push('AngularJS');
    if (window.__NUXT__) fw.push('Nuxt');
    if (document.querySelector('[data-reactroot],[data-reactid]')) fw.push('React-DOM');
    if (document.querySelector('#app')) fw.push('has-#app');
    if (document.querySelector('[data-v-]')) fw.push('Vue-scoped');
    var elApp = document.getElementById('app');
    var appInfo = '';
    if (elApp && elApp.__vue__) appInfo = 'Vue2-instance';
    if (elApp && elApp.__vue_app__) appInfo = 'Vue3-instance';
    return {frameworks: fw, appInfo: appInfo, hasJQuery: !!window.$, hasAxios: !!window.axios};
})()
""")
print("\n=== FRAMEWORK DETECTION ===")
print(json.dumps(framework, ensure_ascii=False, indent=2))

# 7. Page structure overview (top-level sections)
structure = cdp_eval(ws, """
(function() {
    var body = document.body;
    var topEls = body.children;
    var result = [];
    for (var i = 0; i < Math.min(topEls.length, 15); i++) {
        var el = topEls[i];
        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'LINK') continue;
        result.push({
            tag: el.tagName,
            id: el.id || '',
            cls: (el.className || '').substring(0, 80),
            childCount: el.children.length
        });
    }
    return result;
})()
""")
print("\n=== PAGE TOP-LEVEL STRUCTURE ===")
if structure:
    for s in structure:
        print(f"  <{s.get('tag','')}> id={s.get('id','')[:30]} cls={s.get('cls','')[:50]} children={s.get('childCount',0)}")

ws.close()
print("\n=== SURVEY COMPLETE ===")
