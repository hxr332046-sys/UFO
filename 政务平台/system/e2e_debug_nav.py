#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试 Vue Router 导航问题"""
import json, time, requests, websocket

CDP_PORT = 9225

pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
ws_url = None
for p in pages:
    if p.get("type") == "page":
        ws_url = p["webSocketDebuggerUrl"]
        break

ws = websocket.create_connection(ws_url, timeout=15)

def cdp_eval(js, mid=1):
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid:
            return r.get("result",{}).get("result",{}).get("value")

# 1. 当前状态
print("=== 当前页面 ===")
cur = cdp_eval("({hash:location.hash, href:location.href, title:document.title})")
print(f"  hash: {cur.get('hash')}")
print(f"  title: {cur.get('title')}")

# 2. 检查 Vue 实例
print("\n=== Vue 实例检查 ===")
vue_info = cdp_eval("""(function(){
    var app = document.getElementById('app');
    if (!app || !app.__vue__) return {hasVue: false};
    var vm = app.__vue__;
    var router = vm.$router;
    return {
        hasVue: true,
        hasRouter: !!router,
        currentRoute: router ? router.currentRoute?.path : 'N/A',
        routes: router ? router.options?.routes?.map(function(r){return {path:r.path, name:r.name}}).slice(0,10) : [],
        mode: router ? router.mode : 'N/A'
    };
})()""")
print(f"  hasVue: {vue_info.get('hasVue')}")
print(f"  hasRouter: {vue_info.get('hasRouter')}")
print(f"  currentRoute: {vue_info.get('currentRoute')}")
print(f"  mode: {vue_info.get('mode')}")
if vue_info.get('routes'):
    for r in vue_info['routes']:
        print(f"  route: {r}")

# 3. 尝试不同导航方式
print("\n=== 尝试导航方式1: $router.push ===")
r1 = cdp_eval("""(function(){
    var app = document.getElementById('app');
    if (!app || !app.__vue__) return {error:'no_vue'};
    try {
        app.__vue__.$router.push('/index/enterprise/establish');
        return {pushed: true};
    } catch(e) {
        return {error: e.message};
    }
})()""")
print(f"  result: {r1}")
time.sleep(5)
cur2 = cdp_eval("location.hash")
print(f"  hash after: {cur2}")

# 4. 如果还是首页，尝试直接修改 hash
if cur2 == '#/index/page' or not cur2:
    print("\n=== 尝试导航方式2: 直接修改hash ===")
    cdp_eval("location.hash = '#/index/enterprise/establish'")
    time.sleep(5)
    cur3 = cdp_eval("location.hash")
    print(f"  hash after: {cur3}")

    # 5. 尝试完整URL
    if cur3 == '#/index/page' or not cur3:
        print("\n=== 尝试导航方式3: 完整URL ===")
        cdp_eval("location.href = 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/establish'")
        time.sleep(6)
        cur4 = cdp_eval("({hash:location.hash, href:location.href})")
        print(f"  after: {cur4}")

# 6. 检查页面内容
print("\n=== 最终页面内容 ===")
page_content = cdp_eval("""(function(){
    var text = document.body.innerText || '';
    var formItems = document.querySelectorAll('.el-form-item');
    var buttons = document.querySelectorAll('button,.el-button');
    var btnTexts = [];
    for(var i=0;i<buttons.length;i++){var t=buttons[i].textContent?.trim();if(t&&t.length<20)btnTexts.push(t)}
    return {
        hash: location.hash,
        formCount: formItems.length,
        buttons: btnTexts.slice(0,15),
        textPreview: text.substring(0, 300)
    };
})()""")
print(f"  hash: {page_content.get('hash')}")
print(f"  formCount: {page_content.get('formCount')}")
print(f"  buttons: {page_content.get('buttons')}")
print(f"  textPreview: {page_content.get('textPreview','')[:200]}")

# 7. 搜索设立登记入口
print("\n=== 搜索设立登记入口 ===")
entry_search = cdp_eval("""(function(){
    var result = {links:[], cards:[], menuItems:[]};
    // 搜索所有链接
    var links = document.querySelectorAll('a[href]');
    for(var i=0;i<links.length;i++){
        var href = links[i].getAttribute('href')||'';
        var text = links[i].textContent?.trim()||'';
        if(text.includes('设立')||text.includes('登记')||href.includes('establish')){
            result.links.push({text:text.substring(0,30), href:href.substring(0,60)});
        }
    }
    // 搜索服务卡片
    var cards = document.querySelectorAll('.service-card, .card-item, [class*="card"]');
    for(var i=0;i<cards.length;i++){
        var text = cards[i].textContent?.trim()||'';
        if(text.includes('设立')||text.includes('登记')){
            result.cards.push({text:text.substring(0,50), tag:cards[i].tagName, class:cards[i].className.substring(0,40)});
        }
    }
    // 搜索菜单项
    var menus = document.querySelectorAll('.el-menu-item, .el-submenu__title, .nav-item, [class*="menu"], [class*="nav"]');
    for(var i=0;i<menus.length;i++){
        var text = menus[i].textContent?.trim()||'';
        if(text.length>0 && text.length<30){
            result.menuItems.push(text);
        }
    }
    return result;
})()""")
print(f"  links: {entry_search.get('links',[])}")
print(f"  cards: {entry_search.get('cards',[])}")
print(f"  menuItems: {entry_search.get('menuItems',[])}")

# 8. 尝试点击设立登记入口
if entry_search.get('cards'):
    print("\n=== 尝试点击设立登记卡片 ===")
    click_result = cdp_eval("""(function(){
        var cards = document.querySelectorAll('.service-card, .card-item, [class*="card"]');
        for(var i=0;i<cards.length;i++){
            var text = cards[i].textContent?.trim()||'';
            if(text.includes('设立')||text.includes('登记')){
                cards[i].click();
                return {clicked: text.substring(0,50)};
            }
        }
        return {error:'no_card_found'};
    })()""")
    print(f"  click: {click_result}")
    time.sleep(5)
    cur5 = cdp_eval("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after click: {cur5}")

ws.close()
