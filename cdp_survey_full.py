#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Full CDP survey for 政务平台 - write results to file"""

import json
import websocket
import time
import requests
import sys

CDP_PORT = 9225
CDP_HTTP = f"http://127.0.0.1:{CDP_PORT}"
OUT_FILE = r"g:\UFO\cdp_survey_result.json"

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

survey = {}

# 1. Page info
survey["pageInfo"] = cdp_eval(ws, """
(function() {
    return {
        title: document.title,
        url: location.href,
        hostname: location.hostname,
        hash: location.hash,
        readyState: document.readyState
    };
})()
""", msg_id=1)

# 2. Sidebar menu - comprehensive extraction
survey["sidebar"] = cdp_eval(ws, """
(function() {
    var sidebar = document.querySelector('.sidebar') || document.querySelector('#sidebar');
    if (!sidebar) return {error: 'No sidebar found'};
    
    // Get all el-menu items (Element UI menu)
    var menuItems = sidebar.querySelectorAll('.el-menu-item, .el-submenu__title, .el-menu-item-group__title');
    var items = [];
    for (var i = 0; i < menuItems.length; i++) {
        var el = menuItems[i];
        var text = (el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 60);
        var isSubmenu = el.classList.contains('el-submenu__title');
        var isActive = el.classList.contains('is-active');
        var parent = el.closest('.el-submenu');
        var parentText = parent ? (parent.querySelector('.el-submenu__title') || {}).textContent || '' : '';
        items.push({
            text: text,
            isSubmenu: isSubmenu,
            isActive: isActive,
            parentMenu: parentText.trim().replace(/\\s+/g, ' ').substring(0, 40),
            cls: (el.className || '').substring(0, 100),
            index: el.getAttribute('data-index') || el.getAttribute('index') || ''
        });
    }
    
    // Also get sec-menu (secondary menu)
    var secMenu = document.querySelector('.sec-menu');
    var secItems = [];
    if (secMenu) {
        var secEls = secMenu.querySelectorAll('.el-menu-item, .el-submenu__title');
        for (var i = 0; i < secEls.length; i++) {
            var el = secEls[i];
            secItems.push({
                text: (el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 60),
                cls: (el.className || '').substring(0, 80),
                index: el.getAttribute('data-index') || el.getAttribute('index') || ''
            });
        }
    }
    
    return {primaryMenuItems: items, secondaryMenuItems: secItems};
})()
""", msg_id=2)

# 3. Vue router routes
survey["vueRoutes"] = cdp_eval(ws, """
(function() {
    var app = document.getElementById('app');
    if (!app || !app.__vue__) return {error: 'No Vue instance'};
    var vm = app.__vue__;
    var router = vm.$router;
    if (!router) return {error: 'No Vue router'};
    var routeList = [];
    try {
        var routes = router.options.routes || [];
        function extractRoutes(rs, prefix) {
            for (var i = 0; i < rs.length; i++) {
                var r = rs[i];
                routeList.push({
                    path: (prefix || '') + r.path,
                    name: r.name || '',
                    children: r.children ? r.children.length : 0,
                    redirect: r.redirect || '',
                    meta: r.meta || null
                });
                if (r.children) {
                    extractRoutes(r.children, (prefix || '') + r.path + '/');
                }
            }
        }
        extractRoutes(routes, '');
        return {totalRoutes: routeList.length, routes: routeList};
    } catch(e) {
        return {error: e.message};
    }
})()
""", msg_id=3)

# 4. Header iframe navigation
survey["headerIframe"] = cdp_eval(ws, """
(function() {
    var iframe = document.getElementById('iframe-header');
    if (!iframe) return {error: 'No iframe-header'};
    try {
        var doc = iframe.contentDocument || iframe.contentWindow.document;
        var links = doc.querySelectorAll('a');
        var items = [];
        for (var i = 0; i < links.length; i++) {
            var l = links[i];
            items.push({
                text: (l.textContent || '').trim().substring(0, 50),
                href: l.getAttribute('href') || ''
            });
        }
        return {links: items, bodyText: (doc.body ? doc.body.innerText : '').substring(0, 1000)};
    } catch(e) {
        return {error: 'Cannot access: ' + e.message};
    }
})()
""", msg_id=4)

# 5. All service cards on current page
survey["serviceCards"] = cdp_eval(ws, """
(function() {
    var cards = document.querySelectorAll('[class*="card"]');
    var result = [];
    for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        var title = c.querySelector('[class*="title"]');
        var desc = c.querySelector('[class*="desc"], [class*="dexc"]');
        if (title || desc) {
            result.push({
                title: (title ? title.textContent : '').trim().substring(0, 60),
                description: (desc ? desc.textContent : '').trim().substring(0, 120),
                cls: (c.className || '').substring(0, 80)
            });
        }
    }
    return result;
})()
""", msg_id=5)

# 6. Framework & tech stack
survey["techStack"] = cdp_eval(ws, """
(function() {
    var fw = [];
    if (window.Vue) fw.push('Vue ' + (Vue.version || ''));
    if (window.__VUE__) fw.push('Vue3');
    var app = document.getElementById('app');
    if (app && app.__vue__) fw.push('Vue2-instance');
    if (window.$ || window.jQuery) fw.push('jQuery');
    if (window.ELEMENT || (app && app.__vue__ && app.__vue__.$ELEMENT)) fw.push('Element-UI');
    if (window.Axios || (app && app.__vue__ && app.__vue__.$axios)) fw.push('Axios');
    
    // Check for specific Vue plugins
    var plugins = [];
    if (app && app.__vue__) {
        var vm = app.__vue__;
        if (vm.$store) plugins.push('Vuex');
        if (vm.$router) plugins.push('Vue-Router');
        if (vm.$message) plugins.push('Element-Message');
        if (vm.$notify) plugins.push('Element-Notify');
        if (vm.$loading) plugins.push('Element-Loading');
    }
    
    return {frameworks: fw, plugins: plugins};
})()
""", msg_id=6)

# 7. All visible top-level navigation items (首页, 全部服务 etc)
survey["topNav"] = cdp_eval(ws, """
(function() {
    var topItems = document.querySelectorAll('.top-item, .header-right .bottom-item, .page-title');
    var result = [];
    for (var i = 0; i < topItems.length; i++) {
        var el = topItems[i];
        result.push({
            text: (el.textContent || '').trim().substring(0, 40),
            cls: (el.className || '').substring(0, 60)
        });
    }
    return result;
})()
""", msg_id=7)

# 8. Vuex store modules (if available)
survey["vuexModules"] = cdp_eval(ws, """
(function() {
    var app = document.getElementById('app');
    if (!app || !app.__vue__ || !app.__vue__.$store) return {error: 'No Vuex store'};
    var store = app.__vue__.$store;
    var modules = store._modulesNamespaceMap ? Object.keys(store._modulesNamespaceMap) : [];
    var stateKeys = Object.keys(store.state || {}).slice(0, 30);
    return {modules: modules, stateKeys: stateKeys};
})()
""", msg_id=8)

ws.close()

# Write results
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(survey, f, ensure_ascii=False, indent=2)

print(f"Survey complete. Results written to {OUT_FILE}")
print(f"Keys: {list(survey.keys())}")
