#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deep CDP survey for 政务平台 - sidebar, iframe, SPA routes"""

import json
import websocket
import time
import requests

CDP_PORT = 9225
CDP_HTTP = f"http://127.0.0.1:{CDP_PORT}"

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

ws_url = get_ws_url()
ws = websocket.create_connection(ws_url, timeout=15)

# 1. Deep sidebar menu extraction
sidebar = cdp_eval(ws, """
(function() {
    var sidebar = document.querySelector('.sidebar') || document.querySelector('#sidebar');
    if (!sidebar) return {error: 'No sidebar found', allDivs: document.querySelectorAll('div[class*="side"]').length};
    
    // Get all menu items including nested
    var items = sidebar.querySelectorAll('[class*="menu-item"], [class*="el-menu-item"], [class*="el-submenu__title"], [class*="nav-item"], a, span[class*="title"]');
    var result = [];
    var seen = new Set();
    for (var i = 0; i < items.length; i++) {
        var el = items[i];
        var text = (el.textContent || '').trim().substring(0, 60);
        if (!text || seen.has(text) || text.length < 2) continue;
        seen.add(text);
        result.push({
            text: text,
            cls: (el.className || '').substring(0, 80),
            tag: el.tagName,
            href: el.getAttribute('href') || '',
            dataRoute: el.getAttribute('data-route') || el.getAttribute('data-path') || '',
            level: el.closest('[class*="sub"]') ? 'sub' : 'top'
        });
    }
    
    // Also get raw HTML structure of sidebar
    var html = sidebar.innerHTML.substring(0, 3000);
    
    return {itemCount: result.length, items: result.slice(0, 50), htmlSnippet: html};
})()
""", msg_id=1)
print("=== SIDEBAR MENU ===")
if sidebar and not sidebar.get("error"):
    print(f"Items found: {sidebar.get('itemCount', 0)}")
    for item in sidebar.get("items", []):
        print(f"  [{item.get('level','')}] {item.get('text','')[:40]} | cls={item.get('cls','')[:50]} | href={item.get('href','')[:40]} | route={item.get('dataRoute','')[:40]}")
    if sidebar.get("htmlSnippet"):
        print("\n--- Sidebar HTML snippet ---")
        print(sidebar["htmlSnippet"][:2000])
else:
    print(f"Error or no sidebar: {sidebar}")

# 2. Explore iframe-header content (navigation might be there)
ws.send(json.dumps({
    "id": 3,
    "method": "Runtime.evaluate",
    "params": {
        "expression": """
(function() {
    var iframe = document.getElementById('iframe-header');
    if (!iframe) return {error: 'No iframe-header found'};
    try {
        var doc = iframe.contentDocument || iframe.contentWindow.document;
        var links = doc.querySelectorAll('a, [role="menuitem"], [class*="nav-item"], [class*="menu-item"]');
        var items = [];
        var seen = new Set();
        for (var i = 0; i < links.length; i++) {
            var l = links[i];
            var text = (l.textContent || '').trim().substring(0, 50);
            if (!text || seen.has(text)) continue;
            seen.add(text);
            items.push({
                text: text,
                href: l.getAttribute('href') || '',
                cls: (l.className || '').substring(0, 60)
            });
        }
        var title = doc.title || '';
        var bodyText = (doc.body ? doc.body.innerText : '').substring(0, 500);
        return {title: title, linkCount: items.length, links: items.slice(0, 40), bodySnippet: bodyText};
    } catch(e) {
        return {error: 'Cannot access iframe: ' + e.message};
    }
})()
""",
        "returnByValue": True,
        "timeout": 10000
    }
}))
r3 = json.loads(ws.recv())
header_info = r3.get("result", {}).get("result", {}).get("value")
print("\n=== HEADER IFRAME ===")
if header_info:
    if header_info.get("error"):
        print(f"  Error: {header_info['error']}")
    else:
        print(f"  Title: {header_info.get('title', '')}")
        print(f"  Links: {header_info.get('linkCount', 0)}")
        for link in header_info.get("links", []):
            print(f"    -> {link.get('text','')[:40]} | href={link.get('href','')[:60]}")
        if header_info.get("bodySnippet"):
            print(f"  Body: {header_info['bodySnippet'][:300]}")

# 3. Explore iframe-footer
ws.send(json.dumps({
    "id": 4,
    "method": "Runtime.evaluate",
    "params": {
        "expression": """
(function() {
    var iframe = document.getElementById('iframe-footer');
    if (!iframe) return {error: 'No iframe-footer found'};
    try {
        var doc = iframe.contentDocument || iframe.contentWindow.document;
        var links = doc.querySelectorAll('a');
        var items = [];
        for (var i = 0; i < links.length; i++) {
            items.push({text: (links[i].textContent||'').trim().substring(0,40), href: links[i].getAttribute('href')||''});
        }
        return {linkCount: items.length, links: items.slice(0, 20), bodySnippet: (doc.body?doc.body.innerText:'').substring(0,300)};
    } catch(e) {
        return {error: 'Cannot access iframe: ' + e.message};
    }
})()
""",
        "returnByValue": True,
        "timeout": 10000
    }
}))
r4 = json.loads(ws.recv())
footer_info = r4.get("result", {}).get("result", {}).get("value")
print("\n=== FOOTER IFRAME ===")
if footer_info:
    if footer_info.get("error"):
        print(f"  Error: {footer_info['error']}")
    else:
        for link in footer_info.get("links", []):
            print(f"    -> {link.get('text','')[:40]} | href={link.get('href','')[:60]}")

# 4. Vue router - extract all registered routes
routes = cdp_eval(ws, """
(function() {
    var app = document.getElementById('app');
    if (!app || !app.__vue__) return {error: 'No Vue instance'};
    var vm = app.__vue__;
    var router = vm.$router;
    if (!router) return {error: 'No Vue router found', vueKeys: Object.keys(vm.$options).join(',')};
    var routeList = [];
    try {
        var routes = router.options.routes || [];
        function extractRoutes(rs, prefix) {
            for (var i = 0; i < rs.length; i++) {
                var r = rs[i];
                routeList.push({
                    path: (prefix || '') + r.path,
                    name: r.name || '',
                    component: r.component ? (r.component.name || 'anonymous') : '',
                    children: r.children ? r.children.length : 0,
                    redirect: r.redirect || ''
                });
                if (r.children) {
                    extractRoutes(r.children, (prefix || '') + r.path + '/');
                }
            }
        }
        extractRoutes(routes, '');
        return {totalRoutes: routeList.length, routes: routeList.slice(0, 80)};
    } catch(e) {
        return {error: e.message};
    }
})()
""", msg_id=5)
print("\n=== VUE ROUTER ROUTES ===")
if routes and not routes.get("error"):
    print(f"Total routes: {routes.get('totalRoutes', 0)}")
    for r in routes.get("routes", []):
        children = f" (+{r.get('children',0)}children)" if r.get('children',0) else ""
        redirect = f" -> {r.get('redirect','')}" if r.get('redirect','') else ""
        print(f"  {r.get('path','')}{redirect}{children}  [{r.get('name','')}]")
else:
    print(f"  Error: {routes}")

# 5. Current page content area
content = cdp_eval(ws, """
(function() {
    var main = document.querySelector('.main-content') || document.querySelector('.content') || document.querySelector('#app > div');
    if (!main) return {error: 'No main content found'};
    
    // Get visible text sections
    var sections = main.querySelectorAll('[class*="card"], [class*="panel"], [class*="section"], [class*="block"], [class*="zone"], [class*="area"], [class*="module"]');
    var result = [];
    for (var i = 0; i < sections.length; i++) {
        var s = sections[i];
        var text = (s.textContent || '').trim().substring(0, 100);
        if (text.length < 3) continue;
        result.push({
            cls: (s.className || '').substring(0, 80),
            tag: s.tagName,
            textPreview: text.substring(0, 80)
        });
    }
    return {sectionCount: result.length, sections: result.slice(0, 30), mainHTML: main.innerHTML.substring(0, 2000)};
})()
""", msg_id=6)
print("\n=== MAIN CONTENT SECTIONS ===")
if content and not content.get("error"):
    print(f"Sections: {content.get('sectionCount', 0)}")
    for s in content.get("sections", []):
        print(f"  [{s.get('tag','')}] cls={s.get('cls','')[:50]}")
        print(f"    text: {s.get('textPreview','')[:70]}")
    if content.get("mainHTML"):
        print("\n--- Main HTML snippet ---")
        print(content["mainHTML"][:1500])

# 6. All clickable elements with Vue @click handlers
click_handlers = cdp_eval(ws, """
(function() {
    var all = document.querySelectorAll('*');
    var result = [];
    var seen = new Set();
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        var listeners = typeof getEventListeners === 'function' ? getEventListeners(el) : null;
        // Check for vue click via __vue__ data
        var vnode = el.__vue__;
        if (!vnode) continue;
        var text = (el.textContent || '').trim().substring(0, 40);
        if (!text || seen.has(text)) continue;
        seen.add(text);
        var hasClick = false;
        try {
            hasClick = vnode.$listeners && vnode.$listeners.click;
        } catch(e) {}
        if (hasClick || el.onclick || el.getAttribute('data-action')) {
            result.push({
                tag: el.tagName,
                text: text,
                cls: (el.className || '').substring(0, 60),
                hasClick: !!hasClick
            });
        }
    }
    return result.slice(0, 40);
})()
""", msg_id=7)
print("\n=== CLICKABLE ELEMENTS (Vue @click) ===")
if click_handlers:
    for c in click_handlers:
        print(f"  [{c.get('tag','')}] {c.get('text','')[:30]} | cls={c.get('cls','')[:40]} | click={c.get('hasClick',False)}")

ws.close()
print("\n=== DEEP SURVEY COMPLETE ===")
