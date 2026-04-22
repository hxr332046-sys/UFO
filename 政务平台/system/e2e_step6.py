#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step6: 回首页→修复Vuex登录态→正确导航→探查表单"""
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

# 1. 回到首页
print("=== 1. 回首页 ===")
ev("location.hash = '#/index/page'")
time.sleep(3)
cur = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  current: {cur}")

# 2. 深入分析Vuex store结构 - 找到正确的登录恢复方式
print("\n=== 2. Vuex Store 完整分析 ===")
store_detail = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    if(!store)return{error:'no_store'};
    
    // 获取所有mutations
    var mutations=[];
    var m=store._mutations||{};
    for(var k in m){mutations.push(k)}
    
    // 获取所有actions
    var actions=[];
    var a=store._actions||{};
    for(var k in a){actions.push(k)}
    
    // 获取login module完整状态
    var loginState=store.state.login||{};
    
    // 获取common module
    var commonState=store.state.common||{};
    
    // 获取index module (可能有用户信息)
    var indexState=store.state.index||{};
    
    return{
        mutations:mutations,
        actions:actions,
        loginState:loginState,
        commonState:commonState,
        indexKeys:Object.keys(indexState),
        indexUserInfo:indexState.userInfo?JSON.stringify(indexState.userInfo).substring(0,100):'none'
    };
})()""")
print(f"  mutations: {store_detail.get('mutations',[])}")
print(f"  actions: {store_detail.get('actions',[])}")
print(f"  loginState: {store_detail.get('loginState',{})}")
print(f"  commonState: {store_detail.get('commonState',{})}")

# 3. 检查路由守卫
print("\n=== 3. 路由守卫分析 ===")
router_guard = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var router=vm&&vm.$router;
    if(!router)return{error:'no_router'};
    var guards={beforeEach:[],beforeResolve:[],afterEach:[]};
    // router.beforeHooks
    if(router.beforeHooks)guards.beforeEach=router.beforeHooks.map(function(h){return h.toString().substring(0,200)});
    if(router.resolveHooks)guards.beforeResolve=router.resolveHooks.map(function(h){return h.toString().substring(0,200)});
    if(router.afterHooks)guards.afterEach=router.afterHooks.map(function(h){return h.toString().substring(0,200)});
    return{guardCount:{before:router.beforeHooks?.length||0,resolve:router.resolveHooks?.length||0,after:router.afterHooks?.length||0},guards:guards};
})()""")
guard_count = router_guard.get('guardCount',{}) if router_guard else {}
print(f"  guard counts: {guard_count}")
# 打印beforeEach守卫内容（关键！）
guards = router_guard.get('guards',{}) if router_guard else {}
for i, g in enumerate(guards.get('beforeEach',[])):
    print(f"  beforeEach[{i}]: {g[:300]}")

# 4. 尝试恢复登录态 - 通过正确的mutation
print("\n=== 4. 恢复Vuex登录态 ===")
restore = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    if(!store)return{error:'no_store'};
    
    var topToken=localStorage.getItem('top-token')||'';
    var results=[];
    
    // 尝试所有可能的mutation
    var tryMutations=[
        'login/SET_TOKEN','login/SET_USER_INFO','SET_TOKEN','SET_USER_INFO',
        'SET_LOGIN_INFO','SET_LOGIN','LOGIN','SET_AUTH',
        'login/setToken','login/setUserInfo','setToken','setUserInfo',
        'SET_TOKEN_INFO','SAVE_TOKEN','SAVE_LOGIN'
    ];
    
    for(var i=0;i<tryMutations.length;i++){
        try{
            store.commit(tryMutations[i],topToken);
            results.push(tryMutations[i]+':ok');
        }catch(e){
            results.push(tryMutations[i]+':'+e.message.substring(0,30));
        }
    }
    
    // 直接修改state
    if(store.state.login){
        store.state.login.token=topToken;
        results.push('direct_login.token:ok');
    }
    
    // 尝试dispatch actions
    var tryActions=['login/getUserInfo','getUserInfo','login/refresh','refresh'];
    for(var i=0;i<tryActions.length;i++){
        try{
            store.dispatch(tryActions[i]);
            results.push(tryActions[i]+':dispatched');
        }catch(e){
            results.push(tryActions[i]+':'+e.message.substring(0,30));
        }
    }
    
    return{results:results,loginToken:store.state.login?.token?'set('+String(store.state.login.token).length+')':'empty'};
})()""")
print(f"  restore results: {restore}")

# 5. 现在尝试Vue Router导航
print("\n=== 5. Vue Router导航到企业开办 ===")
time.sleep(2)
nav = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    if(!vm||!vm.$router)return{error:'no_router'};
    try{
        vm.$router.push('/index/enterprise/enterprise-zone');
        return{pushed:true};
    }catch(e){return{error:e.message}}
})()""")
print(f"  nav: {nav}")
time.sleep(5)

page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  page: hash={page.get('hash')} forms={page.get('formCount')}")
print(f"  text: {(page.get('text','') or '')[:200]}")

# 6. 如果还是404，尝试通过首页卡片点击
if page.get('hash') == '#/404' or page.get('formCount',0) == 0:
    print("\n=== 6. 通过首页卡片点击 ===")
    ev("location.hash = '#/index/page'")
    time.sleep(3)
    
    # 找到"企业开办一件事"卡片并模拟Vue点击
    card_click = ev("""(function(){
        // 搜索所有元素，找到包含"企业开办一件事"文本的
        var all=document.querySelectorAll('*');
        var targets=[];
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            var children=all[i].children?.length||0;
            // 只找叶子节点或接近叶子的节点
            if(t.includes('企业开办一件事')&&children<3){
                targets.push({tag:all[i].tagName,cls:all[i].className?.substring(0,40)||'',text:t.substring(0,30),parent:all[i].parentElement?.tagName});
            }
        }
        
        // 找到最精确的元素点击
        for(var i=0;i<targets.length;i++){
            var el=document.querySelector(targets[i].cls?targets[i].tag+'.'+targets[i].cls.split(' ')[0]:targets[i].tag);
            // 用更精确的方式找到
        }
        
        // 直接搜索并点击
        var h3s=document.querySelectorAll('h3,h4,h5,div.title,div.text,span');
        for(var i=0;i<h3s.length;i++){
            var t=h3s[i].textContent?.trim()||'';
            if(t==='企业开办一件事'){
                // 触发完整的Vue事件链
                var event=new MouseEvent('click',{bubbles:true,cancelable:true,view:window});
                h3s[i].dispatchEvent(event);
                return{clicked:t,tag:h3s[i].tagName,method:'dispatchEvent'};
            }
        }
        
        // 尝试找router-link
        var rls=document.querySelectorAll('a[href*="enterprise"],[data-v-]');
        for(var i=0;i<rls.length;i++){
            var t=rls[i].textContent?.trim()||'';
            if(t.includes('企业开办')){
                rls[i].click();
                return{clicked:t,method:'router-link'};
            }
        }
        
        return{error:'not_found',targets:targets.slice(0,5)};
    })()""")
    print(f"  card click: {card_click}")
    time.sleep(5)
    
    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after card click: {page2}")

# 7. 如果还是不行，尝试直接修改hash + 刷新
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 7. 修改hash后刷新 ===")
    ev("location.hash = '#/index/enterprise/enterprise-zone'")
    time.sleep(1)
    ev("location.reload()")
    time.sleep(8)
    page3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, isLogin:(document.body.innerText||'').includes('扫码登录')})")
    print(f"  after reload: {page3}")

# 8. 最终状态记录
final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
log("16.导航测试最终状态", {
    "hash": final.get("hash"),
    "formCount": final.get("formCount"),
    "textPreview": (final.get("text","") or "")[:200],
})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10)
            r = json.loads(ws.recv())
            if r.get("id") == 8888:
                d = r.get("result",{}).get("data","")
                if d:
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_step6.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step6 完成")
