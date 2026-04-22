#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step13: 检查当前状态 → 回首页 → 导航（绝不刷新）"""
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

# 1. 当前状态
print("=== 1. 当前状态 ===")
state = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    var text=document.body.innerText||'';
    return{
        hash:location.hash,
        url:location.href,
        isLogin:text.includes('扫码登录'),
        hasUser:text.includes('黄永裕'),
        loginToken:store?.state?.login?.token?String(store.state.login.token).substring(0,10)+'...':'empty',
        loginUserInfo:store?.state?.login?.userInfo?JSON.stringify(store.state.login.userInfo).substring(0,80):'empty',
        formCount:document.querySelectorAll('.el-form-item').length,
        textPreview:text.substring(0,150),
        routesCheck:(function(){
            var router=vm?.$router;
            if(!router)return'no_router';
            var p='/index/enterprise/enterprise-zone';
            var m=router.resolve(p);
            return{path:p,resolved:m.route.path,name:m.route.name||'',matched:m.route.matched?.length||0};
        })()
    };
})()""")
print(f"  hash: {state.get('hash')}")
print(f"  isLogin: {state.get('isLogin')}")
print(f"  hasUser: {state.get('hasUser')}")
print(f"  loginToken: {state.get('loginToken')}")
print(f"  loginUserInfo: {state.get('loginUserInfo')}")
print(f"  routes: {state.get('routesCheck')}")

# 2. 如果在404页，回首页（不刷新！）
if '#/404' in (state.get('hash') or ''):
    print("\n=== 2. 回首页（hash修改，不刷新）===")
    ev("location.hash='#/index/page'")
    time.sleep(3)
    cur = ev("({hash:location.hash, hasUser:(document.body.innerText||'').includes('黄永裕')})")
    print(f"  current: {cur}")

# 3. 如果路由还是404，尝试通过首页菜单导航
routes = state.get('routesCheck', {})
if routes and routes.get('resolved') == '/404':
    print("\n=== 3. 路由未注册，尝试首页菜单导航 ===")
    
    # 先恢复Vuex token
    ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var store=vm?.$store;
        if(store){
            var t=localStorage.getItem('top-token')||'';
            store.commit('login/SET_TOKEN',t);
        }
    })()""")
    
    # 检查侧边栏菜单
    sidebar = ev("""(function(){
        var menu=document.querySelector('.sidebar .el-menu,[class*="sidebar"] .el-menu');
        if(!menu)return{error:'no_sidebar_menu'};
        var submenus=menu.querySelectorAll('.el-submenu');
        var r=[];
        for(var i=0;i<submenus.length;i++){
            var title=submenus[i].querySelector('.el-submenu__title');
            var t=title?.textContent?.trim()||'';
            var opened=submenus[i].className.includes('is-opened');
            r.push({i:i,text:t,opened:opened});
        }
        return{submenus:r};
    })()""")
    print(f"  sidebar: {sidebar}")
    
    # 展开"经营主体登记注册"submenu
    print("\n=== 4. 展开经营主体登记注册 ===")
    expand = ev("""(function(){
        var submenus=document.querySelectorAll('.el-submenu');
        for(var i=0;i<submenus.length;i++){
            var title=submenus[i].querySelector('.el-submenu__title');
            var t=title?.textContent?.trim()||'';
            if(t.includes('经营主体')){
                if(!submenus[i].className.includes('is-opened')){
                    title.click();
                    return{clicked:t,opened:true};
                }
                return{alreadyOpen:t};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  expand: {expand}")
    time.sleep(2)
    
    # 检查展开后的菜单项
    items = ev("""(function(){
        var mi=document.querySelectorAll('.el-menu-item');
        var r=[];
        for(var i=0;i<mi.length;i++){
            var t=mi[i].textContent?.trim()||'';
            var vis=mi[i].offsetParent!==null;
            if(t)r.push({i:i,text:t,vis:vis});
        }
        return r.filter(function(x){return x.vis||x.text.includes('企业开办')});
    })()""")
    print(f"  visible items: {[x for x in (items or []) if x.get('vis')]}")
    print(f"  企业开办 items: {[x for x in (items or []) if '企业开办' in x.get('text','')]}")
    
    # 点击"企业开办"菜单项
    print("\n=== 5. 点击企业开办 ===")
    menu_click = ev("""(function(){
        var mi=document.querySelectorAll('.el-menu-item');
        for(var i=0;i<mi.length;i++){
            var t=mi[i].textContent?.trim()||'';
            if(t==='企业开办'){
                // 检查Vue实例
                var vm=mi[i].__vue__;
                if(vm){
                    // ElMenuItem的click是通过$emit('click')触发的
                    // 但实际是通过native click事件
                    mi[i].click();
                    return{clicked:t,method:'native_click',hasVue:true};
                }
                mi[i].click();
                return{clicked:t,method:'native_click',hasVue:false};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  menu_click: {menu_click}")
    time.sleep(5)
    
    page = ev("""(function(){
        return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
        text:(document.body.innerText||'').substring(0,300)};
    })()""")
    print(f"  page: hash={page.get('hash')} forms={page.get('formCount')}")
    print(f"  text: {(page.get('text','') or '')[:200]}")

    # 如果还是首页，检查菜单项的index属性（决定路由）
    if page.get('hash') == '#/index/page':
        print("\n=== 6. 检查菜单项的index（路由路径）===")
        menu_info = ev("""(function(){
            var mi=document.querySelectorAll('.el-menu-item');
            var r=[];
            for(var i=0;i<mi.length;i++){
                var t=mi[i].textContent?.trim()||'';
                if(t.includes('企业开办')||t.includes('设立')){
                    var vm=mi[i].__vue__;
                    // ElMenuItem有index prop
                    var index='';
                    if(vm)index=vm.index||'';
                    r.push({text:t,index:index,vis:mi[i].offsetParent!==null});
                }
            }
            // 也检查submenu
            var subs=document.querySelectorAll('.el-submenu');
            for(var i=0;i<subs.length;i++){
                var title=subs[i].querySelector('.el-submenu__title');
                var t=title?.textContent?.trim()||'';
                var vm=subs[i].__vue__;
                if(vm){
                    r.push({text:t,index:vm.index||'',isSubmenu:true});
                }
            }
            return r;
        })()""")
        print(f"  menu_info: {json.dumps(menu_info, ensure_ascii=False)[:400]}")
        
        # 如果有index，直接用router.push到index路径
        for m in (menu_info or []):
            if m.get('index') and not m.get('isSubmenu') and '企业开办' in m.get('text',''):
                print(f"\n=== 7. Router push to index: {m.get('index')} ===")
                nav = ev(f"""(function(){{
                    var vm=document.getElementById('app')?.__vue__;
                    if(!vm?.$router)return{{error:'no_router'}};
                    try{{vm.$router.push('{m.get("index")}');return{{ok:true}}}}catch(e){{return{{error:e.message}}}}
                }})()""")
                print(f"  nav: {nav}")
                time.sleep(5)
                page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
                print(f"  after: hash={page2.get('hash')} forms={page2.get('formCount')}")
                break

else:
    # 路由已注册！直接导航
    print("\n=== 3. 路由已注册，直接导航 ===")
    nav = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(!vm?.$router)return{error:'no_router'};
        try{vm.$router.push('/index/enterprise/enterprise-zone');return{ok:true}}catch(e){return{error:e.message}}
    })()""")
    print(f"  nav: {nav}")
    time.sleep(5)
    page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  page: {page}")

# 最终状态
final = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
log("28.导航测试", {"hash":final.get("hash"),"formCount":final.get("formCount"),"text":(final.get("text","") or "")[:100]})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step13.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step13 完成")
