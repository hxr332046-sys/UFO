#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深入探查：页面实际内容 + Vuex状态 + 导航到设立登记"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=15)

def ev(js, mid=1):
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")

# 1. 页面实际内容
print("=== 1. 页面实际内容 ===")
content = ev("""(function(){
    var text=document.body.innerText||'';
    var mainContent=document.querySelector('.main-content,.page-content,[class*="content"],[class*="main"]');
    var mainText=mainContent?mainContent.innerText.substring(0,300):'NO_MAIN';
    var sidebarItems=[];
    var sItems=document.querySelectorAll('.el-menu-item,.el-submenu__title,[class*="menu-item"]');
    for(var i=0;i<sItems.length;i++){var t=sItems[i].textContent?.trim();if(t&&t.length<30&&t.length>0)sidebarItems.push(t)}
    return{
        bodyTextPreview:text.substring(0,400),
        mainContentText:mainText,
        sidebarItems:sidebarItems.slice(0,20),
        allClasses: Array.from(new Set(Array.from(document.querySelectorAll('[class]')).map(function(e){return e.className.split(' ')[0]}))).filter(function(c){return c.length<20&&c.length>3}).slice(0,30)
    };
})()""")
print(f"  bodyText: {(content.get('bodyTextPreview','') or '')[:300]}")
print(f"  mainContent: {(content.get('mainContentText','') or '')[:200]}")
print(f"  sidebarItems: {content.get('sidebarItems',[])}")
print(f"  topClasses: {content.get('allClasses',[])}")

# 2. Vuex store 深入检查
print("\n=== 2. Vuex Store 深入 ===")
store_info = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    if(!store)return{error:'no_store'};
    var state=store.state;
    var modules=Object.keys(state);
    var result={modules:modules};
    // 检查user模块
    if(state.user){
        result.userKeys=Object.keys(state.user);
        result.hasToken=!!state.user.token;
        result.token=state.user.token?state.user.token.substring(0,20)+'...':'NONE';
        result.userInfo=state.user.userInfo?JSON.stringify(state.user.userInfo).substring(0,100):'NONE';
    }
    // 检查其他可能有登录状态的模块
    for(var i=0;i<modules.length;i++){
        var m=modules[i];
        var s=state[m];
        if(s&&typeof s==='object'){
            var keys=Object.keys(s);
            for(var j=0;j<keys.length;j++){
                if(keys[j].toLowerCase().includes('token')||keys[j].toLowerCase().includes('login')||keys[j].toLowerCase().includes('auth')){
                    result[m+'.'+keys[j]]=s[keys[j]]?String(s[keys[j]]).substring(0,30):'empty';
                }
            }
        }
    }
    return result;
})()""")
print(json.dumps(store_info, ensure_ascii=False, indent=2))

# 3. 尝试手动设置 Vuex 登录状态
print("\n=== 3. 尝试恢复登录态 ===")
restore = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    if(!store)return{error:'no_store'};
    var token=localStorage.getItem('Authorization');
    var topToken=localStorage.getItem('top-token');
    if(token){
        // 尝试commit设置token
        try{
            store.commit('user/SET_TOKEN',token);
        }catch(e){
            try{store.commit('SET_TOKEN',token)}catch(e2){}
        }
        // 也尝试直接修改state
        if(store.state.user && !store.state.user.token){
            store.state.user.token=token;
        }
    }
    return{
        tokenSet:!!(store.state.user&&store.state.user.token),
        token:store.state.user&&store.state.user.token?store.state.user.token.substring(0,20)+'...':'NONE'
    };
})()""")
print(json.dumps(restore, ensure_ascii=False, indent=2))

# 4. 尝试导航到设立登记
print("\n=== 4. 导航到设立登记 ===")
nav = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    if(!vm||!vm.$router)return{error:'no_router'};
    var router=vm.$router;
    // 检查可用路由
    var routes=router.options.routes||[];
    var allRoutes=[];
    function collectRoutes(rs,prefix){
        for(var i=0;i<rs.length;i++){
            var r=rs[i];
            var path=(prefix||'')+'/'+r.path;
            allRoutes.push({path:path,name:r.name||''});
            if(r.children)collectRoutes(r.children,path);
        }
    }
    collectRoutes(routes,'');
    // 找到设立登记相关路由
    var establishRoutes=allRoutes.filter(function(r){return r.path.includes('establish')||r.path.includes('name')||r.name.includes('establish')||r.name.includes('name')});
    // 尝试push
    try{
        router.push('/index/enterprise/establish');
        return{pushed:true,establishRoutes:establishRoutes.slice(0,10),allRoutesCount:allRoutes.length};
    }catch(e){
        return{error:e.message,establishRoutes:establishRoutes.slice(0,10)};
    }
})()""")
print(json.dumps(nav, ensure_ascii=False, indent=2))
time.sleep(5)

# 5. 检查导航后页面
print("\n=== 5. 导航后页面 ===")
after = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        bodyText:(document.body.innerText||'').substring(0,300),
        buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,15)
    };
})()""")
print(f"  hash: {after.get('hash')}")
print(f"  formCount: {after.get('formCount')}")
print(f"  buttons: {after.get('buttons')}")
print(f"  text: {(after.get('bodyText','') or '')[:200]}")

# 6. 如果还是没表单，尝试点击侧边栏菜单
if after.get('formCount',0) == 0:
    print("\n=== 6. 尝试点击侧边栏 ===")
    sidebar = ev("""(function(){
        var items=document.querySelectorAll('.el-menu-item,.el-submenu__title,[class*="menu-item"],[class*="nav-item"]');
        var result=[];
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.length>0&&t.length<30){
                result.push({index:i,text:t,tag:items[i].tagName,cls:items[i].className.substring(0,30)});
            }
        }
        // 尝试点击包含"设立"或"登记"的菜单
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('设立')||t.includes('企业登记')||t.includes('市场主体')){
                items[i].click();
                return{clicked:t,allItems:result};
            }
        }
        return{clicked:null,allItems:result};
    })()""")
    print(f"  clicked: {sidebar.get('clicked')}")
    print(f"  allItems: {sidebar.get('allItems',[])}")
    time.sleep(5)

    after2 = ev("""(function(){
        return{
            hash:location.hash,
            formCount:document.querySelectorAll('.el-form-item').length,
            text:(document.body.innerText||'').substring(0,400)
        };
    })()""")
    print(f"\n  after click: hash={after2.get('hash')} forms={after2.get('formCount')}")
    print(f"  text: {(after2.get('text','') or '')[:300]}")

    # 7. 如果有子菜单展开，再找设立登记
    if after2.get('formCount',0) == 0:
        print("\n=== 7. 搜索展开的子菜单 ===")
        submenu = ev("""(function(){
            var items=document.querySelectorAll('.el-menu-item');
            var result=[];
            for(var i=0;i<items.length;i++){
                var t=items[i].textContent?.trim()||'';
                if(t.length>0)result.push({i:i,text:t,visible:items[i].offsetParent!==null});
            }
            // 点击包含"设立"的子菜单
            for(var i=0;i<items.length;i++){
                var t=items[i].textContent?.trim()||'';
                if(t.includes('设立')&&items[i].offsetParent!==null){
                    items[i].click();
                    return{clickedSub:t,items:result.filter(function(x){return x.visible})};
                }
            }
            return{clickedSub:null,items:result.filter(function(x){return x.visible})};
        })()""")
        print(f"  clickedSub: {submenu.get('clickedSub')}")
        print(f"  visibleItems: {submenu.get('items',[])}")
        time.sleep(5)

        after3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  final: {after3}")

ws.close()
