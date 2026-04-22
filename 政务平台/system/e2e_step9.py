#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step9: 调用Vue handleCollapse/handleClick → 展开企业开办 → 导航"""
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

# 1. 调用 handleCollapse 展开"企业开办"
print("=== 1. 调用 handleCollapse ===")
expand = ev("""(function(){
    var items=document.querySelectorAll('.collapse-service .item');
    for(var i=0;i<items.length;i++){
        var span=items[i].querySelector('.text');
        if(span&&span.textContent?.trim()==='企业开办'){
            // 找Vue实例 - 向上遍历
            var el=items[i];
            while(el&&!el.__vue__)el=el.parentElement;
            if(!el||!el.__vue__)return{error:'no_vue_on_item'};
            var vm=el.__vue__;
            // 调用handleCollapse
            if(vm.handleCollapse){
                vm.handleCollapse();
                return{called:'handleCollapse',collapsed:vm.collapsed};
            }
            // 直接修改data
            vm.collapsed=false;
            return{method:'direct_set',collapsed:vm.collapsed};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  expand: {expand}")
time.sleep(2)

# 检查是否展开了
check = ev("""(function(){
    var items=document.querySelectorAll('.collapse-service .item');
    for(var i=0;i<items.length;i++){
        var span=items[i].querySelector('.text');
        if(span&&span.textContent?.trim()==='企业开办'){
            var collapsed=items[i].className.includes('is-collapsed');
            // 找子项
            var subs=items[i].querySelectorAll('.sub-item,.child,[class*="sub"]');
            var allChildren=items[i].querySelectorAll('*');
            var visibleChildren=[];
            for(var j=0;j<allChildren.length;j++){
                if(allChildren[j].offsetParent!==null&&allChildren[j].textContent?.trim()?.length<20){
                    visibleChildren.push({tag:allChildren[j].tagName,cls:allChildren[j].className?.substring(0,20),text:allChildren[j].textContent?.trim()});
                }
            }
            return{collapsed:collapsed,subCount:subs.length,visibleChildren:visibleChildren.slice(0,10),cls:items[i].className};
        }
    }
})()""")
print(f"  check: {json.dumps(check, ensure_ascii=False)[:500]}")

# 2. 如果展开了，找并点击子项
if check and not check.get('collapsed'):
    print("\n=== 2. 点击子项 ===")
    sub_click = ev("""(function(){
        var items=document.querySelectorAll('.collapse-service .item');
        for(var i=0;i<items.length;i++){
            var span=items[i].querySelector('.text');
            if(span&&span.textContent?.trim()==='企业开办'){
                // 找所有可见子元素
                var all=items[i].querySelectorAll('*');
                for(var j=0;j<all.length;j++){
                    var t=all[j].textContent?.trim()||'';
                    if((t.includes('设立')||t==='企业开办')&&all[j].offsetParent!==null&&all[j].children.length===0){
                        all[j].click();
                        return{clicked:t,tag:all[j].tagName};
                    }
                }
                // 找Vue实例的handleClick
                var el=items[i];
                while(el&&!el.__vue__)el=el.parentElement;
                if(el&&el.__vue__){
                    var vm=el.__vue__;
                    if(vm.handleClick){
                        vm.handleClick({text:'企业开办'});
                        return{called:'handleClick'};
                    }
                }
                return{error:'no_clickable_child'};
            }
        }
    })()""")
    print(f"  sub_click: {sub_click}")
    time.sleep(5)
    page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after: {page}")

# 3. 如果还是没展开，直接修改Vue data + 强制DOM更新
if check and check.get('collapsed'):
    print("\n=== 3. 强制修改Vue data ===")
    force = ev("""(function(){
        var items=document.querySelectorAll('.collapse-service .item');
        for(var i=0;i<items.length;i++){
            var span=items[i].querySelector('.text');
            if(span&&span.textContent?.trim()==='企业开办'){
                var el=items[i];
                while(el&&!el.__vue__)el=el.parentElement;
                if(el&&el.__vue__){
                    var vm=el.__vue__;
                    vm.$data.collapsed=false;
                    vm.$forceUpdate();
                    return{forced:true,collapsed:vm.$data.collapsed};
                }
                // 也尝试直接改class
                items[i].classList.remove('is-collapsed');
                return{method:'class_remove',cls:items[i].className};
            }
        }
    })()""")
    print(f"  force: {force}")
    time.sleep(2)
    
    check2 = ev("""(function(){
        var items=document.querySelectorAll('.collapse-service .item');
        for(var i=0;i<items.length;i++){
            var span=items[i].querySelector('.text');
            if(span&&span.textContent?.trim()==='企业开办'){
                return{collapsed:items[i].className.includes('is-collapsed'),cls:items[i].className};
            }
        }
    })()""")
    print(f"  after force: {check2}")

# 4. 换思路 - 侧边栏submenu
print("\n=== 4. 展开侧边栏submenu ===")
submenu = ev("""(function(){
    var submenus=document.querySelectorAll('.el-submenu');
    var r=[];
    for(var i=0;i<submenus.length;i++){
        var title=submenus[i].querySelector('.el-submenu__title');
        var t=title?.textContent?.trim()||'';
        var opened=submenus[i].className.includes('is-opened');
        r.push({i:i,text:t,opened:opened,cls:submenus[i].className?.substring(0,30)});
        // 点击"经营主体登记"submenu
        if(t.includes('经营主体')&&!opened){
            title.click();
            return{clicked:t,method:'submenu_title'};
        }
    }
    return{submenus:r};
})()""")
print(f"  submenu: {submenu}")
time.sleep(2)

# 检查submenu是否展开
after_submenu = ev("""(function(){
    var items=document.querySelectorAll('.el-menu-item');
    var r=[];
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        if(t.includes('企业开办')||t.includes('设立')){
            r.push({i:i,text:t,vis:items[i].offsetParent!==null,display:getComputedStyle(items[i]).display});
        }
    }
    return r;
})()""")
print(f"  items after submenu expand: {after_submenu}")

# 5. 点击可见的"企业开办"菜单项
if after_submenu:
    for item in after_submenu:
        if item.get('vis'):
            print(f"\n=== 5. 点击可见菜单项 ===")
            menu_click = ev(f"""(function(){{
                var items=document.querySelectorAll('.el-menu-item');
                for(var i=0;i<items.length;i++){{
                    if(items[i].textContent?.trim()==='{item.get('text')}'&&items[i].offsetParent!==null){{
                        items[i].click();
                        return{{clicked:'{item.get('text')}'}};
                    }}
                }}
            }})()""")
            print(f"  menu_click: {menu_click}")
            time.sleep(5)
            page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
            print(f"  after: {page}")
            break

# 6. 如果侧边栏菜单项不可见，尝试直接dispatch事件
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 6. 直接dispatch click到el-menu-item ===")
    dispatch = ev("""(function(){
        var items=document.querySelectorAll('.el-menu-item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t==='企业开办'){
                // 找Vue实例
                var vm=items[i].__vue__;
                if(vm){
                    // ElMenuItem 的 click 处理
                    vm.$emit('click');
                    return{method:'vm.$emit',hasVue:true};
                }
                // 直接dispatch
                items[i].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                return{method:'dispatchEvent',hasVue:!!items[i].__vue__};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  dispatch: {dispatch}")
    time.sleep(5)
    page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after dispatch: {page}")

# 最终状态
final = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
log("19.导航测试", {"hash":final.get("hash"),"formCount":final.get("formCount"),"text":(final.get("text","") or "")[:100]})

try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10)
            r = json.loads(ws.recv())
            if r.get("id") == 8888:
                d = r.get("result",{}).get("data","")
                if d:
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_step9.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step9 完成")
