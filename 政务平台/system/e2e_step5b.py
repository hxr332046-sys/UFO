#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step5b: 点击正确入口导航到设立登记"""
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
        except:
            return None

# 1. 搜索所有菜单项和可点击元素
print("=== 1. 搜索所有菜单/卡片 ===")
all_items = ev("""(function(){
    var r=[];
    // el-menu-item
    var mi=document.querySelectorAll('.el-menu-item');
    for(var i=0;i<mi.length;i++){
        var t=mi[i].textContent?.trim()||'';
        if(t)r.push({type:'menu',i:i,text:t,tag:mi[i].tagName,cls:mi[i].className?.substring(0,30)||'',visible:mi[i].offsetParent!==null});
    }
    // el-submenu
    var sm=document.querySelectorAll('.el-submenu__title');
    for(var i=0;i<sm.length;i++){
        var t=sm[i].textContent?.trim()||'';
        if(t)r.push({type:'submenu',i:i,text:t,tag:sm[i].tagName,cls:sm[i].className?.substring(0,30)||''});
    }
    // collapse-service / item
    var cs=document.querySelectorAll('.collapse-service,.item,.service-item,[class*="card"]');
    for(var i=0;i<cs.length;i++){
        var t=cs[i].textContent?.trim()||'';
        if(t&&t.length<50)r.push({type:'card',i:i,text:t.substring(0,40),tag:cs[i].tagName,cls:cs[i].className?.substring(0,30)||'',visible:cs[i].offsetParent!==null});
    }
    return r;
})()""")
for item in (all_items or []):
    vis = "✅" if item.get("visible") != False else "❌"
    print(f"  {vis} [{item.get('type')}] {item.get('text','')}")

# 2. 点击"企业开办一件事"或"经营主体登记"
print("\n=== 2. 点击经营主体登记 ===")
click1 = ev("""(function(){
    // 先点击 经营主体登记 submenu
    var sm=document.querySelectorAll('.el-submenu__title');
    for(var i=0;i<sm.length;i++){
        var t=sm[i].textContent?.trim()||'';
        if(t.includes('经营主体登记')){
            sm[i].click();
            return{clicked:t,method:'submenu'};
        }
    }
    // 尝试 collapse-service
    var cs=document.querySelectorAll('.collapse-service');
    for(var i=0;i<cs.length;i++){
        var t=cs[i].textContent?.trim()||'';
        if(t.includes('经营主体登记')){
            cs[i].click();
            return{clicked:t.substring(0,30),method:'collapse'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click1: {click1}")
time.sleep(3)

# 3. 展开后找"企业开办"
print("\n=== 3. 找企业开办 ===")
items_after = ev("""(function(){
    var mi=document.querySelectorAll('.el-menu-item');
    var r=[];
    for(var i=0;i<mi.length;i++){
        var t=mi[i].textContent?.trim()||'';
        var vis=mi[i].offsetParent!==null;
        if(t)r.push({i:i,text:t,visible:vis});
    }
    return r;
})()""")
print(f"  menu items after expand: {items_after}")

# 点击企业开办
click2 = ev("""(function(){
    var mi=document.querySelectorAll('.el-menu-item');
    for(var i=0;i<mi.length;i++){
        var t=mi[i].textContent?.trim()||'';
        if((t.includes('企业开办')||t==='企业开办')&&mi[i].offsetParent!==null){
            mi[i].click();
            return{clicked:t};
        }
    }
    // 也尝试 collapse item
    var items=document.querySelectorAll('.item');
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        if(t.includes('企业开办')&&items[i].offsetParent!==null){
            items[i].click();
            return{clicked:t,method:'item'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click2: {click2}")
time.sleep(5)

# 检查页面
page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  page: hash={page.get('hash')} forms={page.get('formCount')}")
print(f"  text: {(page.get('text','') or '')[:200]}")

# 4. 如果到了企业开办专区，找设立登记入口
if page.get('formCount',0) == 0 and '企业开办' in (page.get('text','') or ''):
    print("\n=== 4. 在企业开办专区找设立登记 ===")
    click3 = ev("""(function(){
        var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t==='设立登记'&&t.length<10&&all[i].offsetParent!==null){
                all[i].click();
                return{clicked:t,tag:all[i].tagName};
            }
        }
        // 也找"设立"相关
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.includes('设立')&&t.length<20&&all[i].offsetParent!==null){
                all[i].click();
                return{clicked:t,tag:all[i].tagName};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  click3: {click3}")
    time.sleep(5)
    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after: {page2}")

# 5. 如果还是没表单，尝试直接router push
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 5. Vue Router push ===")
    router_push = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app&&app.__vue__;
        if(!vm||!vm.$router)return{error:'no_router'};
        // 先导航到企业开办专区
        try{vm.$router.push('/index/enterprise/enterprise-zone');return{pushed:'enterprise-zone'}}catch(e){return{error:e.message}}
    })()""")
    print(f"  router: {router_push}")
    time.sleep(5)
    page3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after router: hash={page3.get('hash')} forms={page3.get('formCount')}")
    print(f"  text: {(page3.get('text','') or '')[:150]}")

    # 如果到了企业开办专区
    if page3.get('formCount',0) == 0:
        print("\n=== 5b. 在专区页面找设立登记 ===")
        zone_items = ev("""(function(){
            var r=[];
            var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li,[class*="item"],[class*="card"]');
            for(var i=0;i<all.length;i++){
                var t=all[i].textContent?.trim()||'';
                if((t.includes('设立')||t.includes('开办')||t.includes('登记'))&&t.length<30&&all[i].offsetParent!==null){
                    r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,30)||'',text:t});
                }
            }
            return r;
        })()""")
        print(f"  zone items: {zone_items}")
        
        # 点击设立登记
        click4 = ev("""(function(){
            var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li,[class*="item"]');
            for(var i=0;i<all.length;i++){
                var t=all[i].textContent?.trim()||'';
                if(t.includes('设立')&&t.length<15&&all[i].offsetParent!==null){
                    all[i].click();
                    return{clicked:t};
                }
            }
            return{error:'not_found'};
        })()""")
        print(f"  click4: {click4}")
        time.sleep(5)
        page4 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  after: {page4}")

# 6. 最终状态
final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body.innerText||'').substring(0,400)};
})()""")
log("15.最终导航状态", {
    "hash": final.get("hash"),
    "formCount": final.get("formCount"),
    "textPreview": (final.get("text","") or "")[:200],
})

# 7. 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10)
            r = json.loads(ws.recv())
            if r.get("id") == 8888:
                d = r.get("result",{}).get("data","")
                if d:
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_final.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n  📸 截图: {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step5b 完成")
