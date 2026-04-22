#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试导航：找到正确的路由到设立登记表单"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
        if not page: return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 当前页面状态
# ============================================================
print("Step 1: 当前页面")
cur = ev("""(function(){
    return {
        hash: location.hash,
        href: location.href.substring(0,120),
        title: document.title
    };
})()""")
print(f"  {cur}")

# ============================================================
# Step 2: 查找Vue Router路由列表
# ============================================================
print("\nStep 2: 路由列表")
routes = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router||vm.$root?.$router;
    if(!router)return'no_router';
    var r=router.options?.routes||[];
    var result=[];
    for(var i=0;i<r.length;i++){
        var route=r[i];
        var item={path:route.path||'',name:route.name||''};
        if(route.children){
            item.children=route.children.slice(0,5).map(function(c){return c.path||c.name||''});
        }
        result.push(item);
    }
    return result;
})()""")
if isinstance(routes, list):
    for r in routes[:20]:
        print(f"  {r}")
else:
    print(f"  {routes}")

# ============================================================
# Step 3: 查找菜单项中的设立登记入口
# ============================================================
print("\nStep 3: 菜单项")
menu_items = ev("""(function(){
    var items=document.querySelectorAll('.el-menu-item,.menu-item,.nav-item,a[href]');
    var result=[];
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        var href=items[i].getAttribute('href')||items[i].dataset?.href||'';
        if(t.length>0&&t.length<30){
            result.push({text:t,href:href.substring(0,60)});
        }
    }
    return result.slice(0,30);
})()""")
if isinstance(menu_items, list):
    for m in menu_items:
        print(f"  {m}")
else:
    print(f"  {menu_items}")

# ============================================================
# Step 4: 查找首页上的业务入口按钮
# ============================================================
print("\nStep 4: 首页业务入口")
biz_btns = ev("""(function(){
    var all=document.querySelectorAll('a,button,.card,.item,.service-item,.business-item');
    var result=[];
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('设立')||t.includes('登记')||t.includes('名称')||t.includes('企业'))&&t.length<50){
            var href=all[i].getAttribute('href')||all[i].dataset?.href||'';
            var onclick=all[i].getAttribute('onclick')||'';
            result.push({text:t.substring(0,30),href:href.substring(0,60),tag:all[i].tagName});
        }
    }
    return result.slice(0,15);
})()""")
if isinstance(biz_btns, list):
    for b in biz_btns:
        print(f"  {b}")
else:
    print(f"  {biz_btns}")

# ============================================================
# Step 5: 尝试通过菜单导航
# ============================================================
print("\nStep 5: 尝试导航")
# 先回到首页
ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router||vm.$root?.$router;
    if(router){
        router.push('/');
    }
})()""")
time.sleep(2)

cur2 = ev("location.hash")
print(f"  首页路由: {cur2}")

# 查找Vue组件
comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComps(vm,d,list){
        if(d>5)return list;
        var n=vm.$options?.name||'';
        if(n&&n.length>0)list.push({name:n,d:d});
        for(var i=0;i<(vm.$children||[]).length;i++){
            findComps(vm.$children[i],d+1,list);
        }
        return list;
    }
    var all=findComps(vm,0,[]);
    // 过滤出关键组件
    var key=all.filter(function(c){return c.name.includes('index')||c.name.includes('page')||c.name.includes('portal')||c.name.includes('menu')||c.name.includes('nav')||c.name.includes('home')||c.name.includes('space')});
    return key.slice(0,20);
})()""")
print(f"  关键组件: {comps}")

print("\n✅ 完成")
