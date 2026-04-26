#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
政务平台网站普查脚本
通过 CDP 对政务平台进行全面结构扫描，输出 JSON 结果
"""

import json
import time
import requests
import websocket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_helper import CDPHelper


def full_survey(helper, output_path=None):
    """执行完整网站普查"""
    survey = {}

    # 1. 页面基本信息
    survey["pageInfo"] = helper.get_page_info()

    # 2. Vue Router 全部路由
    survey["vueRoutes"] = helper.eval("""
        (function() {
            var app = document.getElementById('app');
            if (!app || !app.__vue__) return {error: 'No Vue instance'};
            var router = app.__vue__.$router;
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
    """)

    # 3. 侧边栏菜单
    survey["sidebar"] = helper.eval("""
        (function() {
            var sidebar = document.querySelector('.sidebar') || document.querySelector('#sidebar');
            if (!sidebar) return {items: []};
            var menuItems = sidebar.querySelectorAll('.el-menu-item, .el-submenu__title');
            var items = [];
            for (var i = 0; i < menuItems.length; i++) {
                var el = menuItems[i];
                items.push({
                    text: (el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 60),
                    isSubmenu: el.classList.contains('el-submenu__title'),
                    isActive: el.classList.contains('is-active'),
                    index: el.getAttribute('data-index') || el.getAttribute('index') || ''
                });
            }
            return {items: items};
        })()
    """)

    # 4. 顶部导航
    survey["topNav"] = helper.eval("""
        (function() {
            var items = document.querySelectorAll('.top-item, .header-right .bottom-item');
            var result = [];
            for (var i = 0; i < items.length; i++) {
                result.push({
                    text: (items[i].textContent || '').trim().substring(0, 40),
                    cls: (items[i].className || '').substring(0, 60)
                });
            }
            return result;
        })()
    """)

    # 5. 服务卡片
    survey["serviceCards"] = helper.eval("""
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
    """)

    # 6. 技术栈
    survey["techStack"] = helper.eval("""
        (function() {
            var fw = [];
            var app = document.getElementById('app');
            if (app && app.__vue__) fw.push('Vue2-instance');
            if (window.$ || window.jQuery) fw.push('jQuery');
            if (window.ELEMENT || (app && app.__vue__ && app.__vue__.$ELEMENT)) fw.push('Element-UI');
            var plugins = [];
            if (app && app.__vue__) {
                var vm = app.__vue__;
                if (vm.$store) plugins.push('Vuex');
                if (vm.$router) plugins.push('Vue-Router');
                if (vm.$message) plugins.push('Element-Message');
                if (vm.$notify) plugins.push('Element-Notify');
            }
            return {frameworks: fw, plugins: plugins};
        })()
    """)

    # 7. Vuex 模块
    survey["vuexModules"] = helper.eval("""
        (function() {
            var app = document.getElementById('app');
            if (!app || !app.__vue__ || !app.__vue__.$store) return {error: 'No Vuex store'};
            var store = app.__vue__.$store;
            var modules = store._modulesNamespaceMap ? Object.keys(store._modulesNamespaceMap) : [];
            var stateKeys = Object.keys(store.state || {});
            return {modules: modules, stateKeys: stateKeys};
        })()
    """)

    # 8. 表单元素清单
    survey["formElements"] = helper.eval("""
        (function() {
            var inputs = document.querySelectorAll('input, select, textarea');
            var result = [];
            for (var i = 0; i < Math.min(inputs.length, 80); i++) {
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

    # 9. 按钮清单
    survey["buttons"] = helper.eval("""
        (function() {
            var btns = document.querySelectorAll('button, [role="button"], .el-button');
            var result = [];
            var seen = new Set();
            for (var i = 0; i < btns.length; i++) {
                var b = btns[i];
                var txt = (b.textContent || '').trim().substring(0, 40);
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

    # 输出结果
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(survey, f, ensure_ascii=False, indent=2)
        print(f"Survey complete. Results written to {output_path}")
    return survey


if __name__ == "__main__":
    helper = CDPHelper()
    page = helper.connect()
    print(f"Connected: {page.get('title', '')}")

    output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "survey", "survey_result.json")
    full_survey(helper, output_path=output)
    helper.close()
