#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step8: 通过collapse-service展开+点击企业开办"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)

_mid = 0
def ev(js, mid=None):
    global _mid
    if mid is None: mid = _mid + 1; _mid = mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":10000}}))
    while True:
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None

# 回首页
ev("location.hash='#/index/page'")
time.sleep(3)

# 1. 分析collapse-service结构
print("=== 1. collapse-service分析 ===")
cs = ev("""(function(){
    var r=[];
    var items=document.querySelectorAll('.collapse-service .item');
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        var collapsed=items[i].className.includes('is-collapsed');
        var span=items[i].querySelector('.text');
        var arrow=items[i].querySelector('.arrow,[class*="arrow"]');
        r.push({
            i:i,
            text:t.substring(0,40),
            collapsed:collapsed,
            spanText:span?.textContent?.trim()||'',
            hasArrow:!!arrow,
            cls:items[i].className?.substring(0,50)||'',
            childHtml:items[i].innerHTML?.substring(0,100)||''
        });
    }
    return r;
})()""")
for c in (cs or []):
    print(f"  [{c.get('i')}] collapsed={c.get('collapsed')} text={c.get('spanText','') or c.get('text','')}")

# 2. 点击"企业开办"的SPAN.text（精确点击）
print("\n=== 2. 点击SPAN.text '企业开办' ===")
click1 = ev("""(function(){
    var items=document.querySelectorAll('.collapse-service .item');
    for(var i=0;i<items.length;i++){
        var span=items[i].querySelector('.text');
        if(span&&span.textContent?.trim()==='企业开办'){
            // 先展开
            span.click();
            return{clicked:'span.text',text:span.textContent?.trim(),itemCls:items[i].className};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click1: {click1}")
time.sleep(3)

# 检查是否展开了
expanded = ev("""(function(){
    var items=document.querySelectorAll('.collapse-service .item');
    for(var i=0;i<items.length;i++){
        var span=items[i].querySelector('.text');
        if(span&&span.textContent?.trim()==='企业开办'){
            var collapsed=items[i].className.includes('is-collapsed');
            var children=items[i].querySelectorAll('.sub-item,.child-item,[class*="sub"]');
            return{collapsed:collapsed,childCount:children.length,cls:items[i].className};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  expanded: {expanded}")

# 3. 如果展开了，找子项
if expanded and not expanded.get('collapsed'):
    print("\n=== 3. 查找子项 ===")
    sub_items = ev("""(function(){
        var items=document.querySelectorAll('.collapse-service .item');
        for(var i=0;i<items.length;i++){
            var span=items[i].querySelector('.text');
            if(span&&span.textContent?.trim()==='企业开办'){
                var children=items[i].children;
                var r=[];
                for(var j=0;j<children.length;j++){
                    var t=children[j].textContent?.trim()||'';
                    if(t.length>0&&t.length<30)r.push({j:j,tag:children[j].tagName,cls:children[j].className?.substring(0,30)||'',text:t});
                }
                // 也搜索所有后代
                var all=items[i].querySelectorAll('*');
                var deep=[];
                for(var j=0;j<all.length;j++){
                    var t=all[j].textContent?.trim()||'';
                    if((t.includes('设立')||t==='企业开办')&&t.length<15&&all[j].children.length===0){
                        deep.push({tag:all[j].tagName,cls:all[j].className?.substring(0,30)||'',text:t});
                    }
                }
                return{children:r.slice(0,10),deep:deep};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  sub_items: {json.dumps(sub_items, ensure_ascii=False)[:500]}")

# 4. 如果还是collapsed，尝试点击arrow/展开按钮
if expanded and expanded.get('collapsed'):
    print("\n=== 4. 点击展开按钮 ===")
    expand_click = ev("""(function(){
        var items=document.querySelectorAll('.collapse-service .item');
        for(var i=0;i<items.length;i++){
            var span=items[i].querySelector('.text');
            if(span&&span.textContent?.trim()==='企业开办'){
                // 点击整个item
                items[i].click();
                // 也点击arrow
                var arrow=items[i].querySelector('.arrow,[class*="arrow"],[class*="expand"]');
                if(arrow)arrow.click();
                return{clicked:'item+arrow',cls:items[i].className};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  expand: {expand_click}")
    time.sleep(2)
    
    # 再检查
    expanded2 = ev("""(function(){
        var items=document.querySelectorAll('.collapse-service .item');
        for(var i=0;i<items.length;i++){
            var span=items[i].querySelector('.text');
            if(span&&span.textContent?.trim()==='企业开办'){
                return{collapsed:items[i].className.includes('is-collapsed'),cls:items[i].className};
            }
        }
    })()""")
    print(f"  after expand: {expanded2}")

# 5. 尝试Vue组件方式 - 找到item的Vue实例并调用方法
print("\n=== 5. Vue组件方式 ===")
vue_click = ev("""(function(){
    var items=document.querySelectorAll('.collapse-service .item');
    for(var i=0;i<items.length;i++){
        var span=items[i].querySelector('.text');
        if(span&&span.textContent?.trim()==='企业开办'){
            // 找Vue实例
            var el=items[i];
            while(el&&!el.__vue__)el=el.parentElement;
            if(el&&el.__vue__){
                var vm=el.__vue__;
                var methods=[];
                for(var k in vm.$options.methods||{}){
                    methods.push(k);
                }
                // 也检查data
                var dataKeys=[];
                for(var k in vm.$data||{}){
                    dataKeys.push(k+':'+JSON.stringify(vm.$data[k]).substring(0,30));
                }
                return{hasVue:true,methods:methods,dataKeys:dataKeys,vueName:vm.$options?.name||''};
            }
            // 检查span的Vue实例
            if(span.__vue__){
                var vm2=span.__vue__;
                var m2=[];
                for(var k in vm2.$options.methods||{})m2.push(k);
                return{hasVue:true,from:'span',methods:m2,vueName:vm2.$options?.name||''};
            }
            return{hasVue:false};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  vue: {vue_click}")

# 6. 换个思路 - 直接通过API获取企业开办页面数据
print("\n=== 6. 通过API获取页面数据 ===")
api_data = ev("""(function(){
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/register/guide/enterprise',false);
    xhr.setRequestHeader('top-token',localStorage.getItem('top-token')||'');
    xhr.send();
    return{status:xhr.status,body:xhr.responseText?.substring(0,300)};
})()""")
print(f"  enterprise guide API: status={api_data.get('status')} body={api_data.get('body','')[:200]}")

# 7. 尝试获取企业开办专区的API
api2 = ev("""(function(){
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/register/enterpriseZone',false);
    xhr.setRequestHeader('top-token',localStorage.getItem('top-token')||'');
    xhr.send();
    return{status:xhr.status,body:xhr.responseText?.substring(0,300)};
})()""")
print(f"  enterpriseZone API: status={api2.get('status')} body={api2.get('body','')[:200]}")

# 8. 尝试通过侧边栏菜单导航（先展开侧边栏）
print("\n=== 8. 侧边栏菜单导航 ===")
sidebar = ev("""(function(){
    // 先找到侧边栏
    var sidebar=document.querySelector('.sidebar,[class*="sidebar"],.el-menu');
    if(!sidebar)return{error:'no_sidebar'};
    // 检查是否可见
    var vis=sidebar.offsetParent!==null;
    var items=sidebar.querySelectorAll('.el-menu-item');
    var r=[];
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        if(t)r.push({i:i,text:t,vis:items[i].offsetParent!==null,display:getComputedStyle(items[i]).display});
    }
    return{sidebarVisible:vis,items:r.slice(0,10),sidebarCls:sidebar.className?.substring(0,30)};
})()""")
print(f"  sidebar: {json.dumps(sidebar, ensure_ascii=False)[:300]}")

# 如果侧边栏不可见，尝试点击菜单按钮展开
if sidebar and not sidebar.get('sidebarVisible'):
    print("\n=== 8b. 展开侧边栏 ===")
    menu_btn = ev("""(function(){
        // 找菜单按钮
        var btns=document.querySelectorAll('[class*="menu-btn"],[class*="hamburger"],[class*="toggle"],.el-icon-menu,.el-icon-s-fold,.el-icon-s-unfold');
        for(var i=0;i<btns.length;i++){
            btns[i].click();
            return{clicked:btns[i].className?.substring(0,30)};
        }
        // 也尝试点击header中的菜单
        var header=document.querySelector('.header,[class*="header"]');
        if(header){
            var first=header.querySelector('div,span,i');
            if(first){first.click();return{clicked:'header_first_child'}}
        }
        return{error:'no_menu_btn'};
    })()""")
    print(f"  menu btn: {menu_btn}")
    time.sleep(2)
    
    # 再检查侧边栏
    sidebar2 = ev("""(function(){
        var sidebar=document.querySelector('.sidebar,[class*="sidebar"],.el-menu');
        if(!sidebar)return{error:'no_sidebar'};
        var vis=sidebar.offsetParent!==null||getComputedStyle(sidebar).display!=='none';
        var items=sidebar.querySelectorAll('.el-menu-item');
        var r=[];
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('企业开办')||t.includes('设立'))r.push({i:i,text:t,vis:items[i].offsetParent!==null});
        }
        return{sidebarVisible:vis,matchingItems:r};
    })()""")
    print(f"  sidebar after: {sidebar2}")

# 9. 最终 - 如果侧边栏可见，点击"企业开办"
if ev("""(function(){
    var items=document.querySelectorAll('.el-menu-item');
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        if(t==='企业开办'&&items[i].offsetParent!==null)return true;
    }
    return false;
})()"""):
    print("\n=== 9. 点击侧边栏企业开办 ===")
    menu_click = ev("""(function(){
        var items=document.querySelectorAll('.el-menu-item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t==='企业开办'&&items[i].offsetParent!==null){
                items[i].click();
                return{clicked:t};
            }
        }
    })()""")
    print(f"  menu click: {menu_click}")
    time.sleep(5)
    page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after: {page}")

# 最终状态
final = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
log("18.导航测试", {"hash":final.get("hash"),"formCount":final.get("formCount"),"text":(final.get("text","") or "")[:100]})

try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10)
            r = json.loads(ws.recv())
            if r.get("id") == 8888:
                d = r.get("result",{}).get("data","")
                if d:
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_step8.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step8 完成")
