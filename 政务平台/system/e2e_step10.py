#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step10: 恢复Vuex登录态 → 导航 → 探查表单"""
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

# 1. 获取用户信息并完整恢复Vuex
print("=== 1. 恢复Vuex登录态 ===")
restore = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    if(!store)return{error:'no_store'};
    var topToken=localStorage.getItem('top-token')||'';
    store.commit('login/SET_TOKEN',topToken);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUser',false);
    xhr.setRequestHeader('top-token',topToken);
    xhr.setRequestHeader('Authorization',topToken);
    try{xhr.send()}catch(e){return{error:'api:'+e.message}}
    if(xhr.status===200){
        try{
            var data=JSON.parse(xhr.responseText);
            var ui=data.data||data.result||data;
            store.commit('login/SET_USER_INFO',ui);
            return{ok:true,token:!!store.state.login.token,userInfo:Object.keys(store.state.login.userInfo||{}).length,name:ui.userName||ui.loginName||''};
        }catch(e){return{error:'parse:'+e.message}}
    }
    return{error:'status:'+xhr.status};
})()""")
print(f"  restore: {restore}")

# 2. Vue Router导航
print("\n=== 2. 导航到企业开办专区 ===")
nav = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    if(!vm||!vm.$router)return{error:'no_router'};
    try{vm.$router.push('/index/enterprise/enterprise-zone');return{ok:true}}catch(e){return{error:e.message}}
})()""")
print(f"  nav: {nav}")
time.sleep(5)

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,is404:(document.body.innerText||'').includes('页面不存在'),text:(document.body.innerText||'').substring(0,200)})")
print(f"  page: hash={page.get('hash')} forms={page.get('formCount')} is404={page.get('is404')}")
print(f"  text: {(page.get('text','') or '')[:150]}")

# 3. 如果404，检查路由resolve
if page.get('is404'):
    print("\n=== 3. 路由resolve检查 ===")
    resolve = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        if(!router)return{error:'no_router'};
        var paths=['/index/page','/index/enterprise/enterprise-zone','/index/enterprise/establish','/index/name-check','/company/my-space/space-index'];
        return paths.map(function(p){
            var m=router.resolve(p);
            return{path:p,resolved:m.route.path,name:m.route.name||'',matched:m.route.matched?.length||0};
        });
    })()""")
    print(f"  resolve: {json.dumps(resolve, ensure_ascii=False)[:400]}")

    # 4. 尝试导航到非auth路由
    print("\n=== 4. 尝试非auth路由 ===")
    ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(vm?.$router)vm.$router.push('/index/page');
    })()""")
    time.sleep(2)
    nav2 = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(!vm?.$router)return{error:'no_router'};
        try{vm.$router.push('/index/name-check');return{ok:true}}catch(e){return{error:e.message}}
    })()""")
    print(f"  nav2: {nav2}")
    time.sleep(5)
    page2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,is404:(document.body.innerText||'').includes('页面不存在')})")
    print(f"  page2: {page2}")

    # 5. 如果name-check也404，说明是路由懒加载chunk问题
    if page2.get('is404'):
        print("\n=== 5. 路由组件加载检查 ===")
        chunk = ev("""(function(){
            var vm=document.getElementById('app')?.__vue__;
            var router=vm?.$router;
            if(!router)return{error:'no_router'};
            var match=router.resolve('/index/enterprise/enterprise-zone');
            var route=match.route;
            var comps=[];
            for(var i=0;i<route.matched.length;i++){
                var m=route.matched[i];
                for(var k in m.components||{}){
                    var c=m.components[k];
                    comps.push({key:k,type:typeof c,isFn:typeof c==='function',src:c.toString?.()?.substring(0,80)||''});
                }
            }
            return{matched:route.matched.length,comps:comps};
        })()""")
        print(f"  chunk: {json.dumps(chunk, ensure_ascii=False)[:500]}")

        # 6. 检查是否chunk加载失败
        print("\n=== 6. 检查JS加载状态 ===")
        js_check = ev("""(function(){
            var scripts=document.querySelectorAll('script[src]');
            var srcs=[];
            for(var i=0;i<scripts.length;i++){
                var s=scripts[i].src||'';
                srcs.push(s.substring(s.lastIndexOf('/')+1));
            }
            var errors=window.__chunkLoadErrors||[];
            return{scriptCount:scripts.length,srcs:srcs.slice(0,15),errors:errors};
        })()""")
        print(f"  js: {json.dumps(js_check, ensure_ascii=False)[:300]}")

        # 7. 尝试手动触发chunk加载
        print("\n=== 7. 手动触发路由组件加载 ===")
        manual = ev("""(function(){
            var vm=document.getElementById('app')?.__vue__;
            var router=vm?.$router;
            if(!router)return{error:'no_router'};
            // 检查matched路由的组件是否是懒加载函数
            var match=router.resolve('/index/enterprise/enterprise-zone');
            var route=match.route;
            if(route.matched.length>0){
                var comp=route.matched[0].components?.default;
                if(typeof comp==='function'){
                    // 这是懒加载，尝试执行
                    try{
                        var result=comp();
                        if(result&&result.then){
                            return{type:'promise',msg:'chunk is lazy-loaded, needs network'};
                        }
                        return{type:'sync',result:typeof result};
                    }catch(e){return{error:e.message}}
                }
                return{type:typeof comp,name:comp.name||''};
            }
            return{error:'no_matched'};
        })()""")
        print(f"  manual: {json.dumps(manual, ensure_ascii=False)[:300]}")

# 8. 如果所有路由都404，尝试通过首页卡片直接跳转
print("\n=== 8. 通过首页卡片跳转 ===")
ev("location.hash='#/index/page'")
time.sleep(3)

# 找到所有带href的a标签
links = ev("""(function(){
    var as=document.querySelectorAll('a[href]');
    var r=[];
    for(var i=0;i<as.length;i++){
        var t=as[i].textContent?.trim()||'';
        var h=as[i].getAttribute('href')||'';
        if(t.includes('企业开办')||t.includes('设立')||h.includes('enterprise')){
            r.push({text:t.substring(0,20),href:h.substring(0,60)});
        }
    }
    // 也检查router-link
    var rls=document.querySelectorAll('[data-v-]');
    return{links:r,routerLinks:rls.length};
})()""")
print(f"  links: {links}")

# 9. 尝试通过window.open或location.href直接跳到业务页面
print("\n=== 9. 直接跳转业务页面 ===")
# 先尝试通过API获取企业开办专区数据
api_test = ev("""(function(){
    var topToken=localStorage.getItem('top-token')||'';
    var apis=[
        '/icpsp-api/v4/pc/register/enterpriseZone',
        '/icpsp-api/v4/pc/register/guide/enterprise',
        '/icpsp-api/v4/pc/register/establish/list',
        '/icpsp-api/v4/pc/branch/list',
        '/icpsp-api/v4/pc/company/mySpace',
    ];
    var results=[];
    for(var i=0;i<apis.length;i++){
        var xhr=new XMLHttpRequest();
        xhr.open('GET',apis[i],false);
        xhr.setRequestHeader('top-token',topToken);
        xhr.setRequestHeader('Authorization',topToken);
        try{xhr.send()}catch(e){results.push({api:apis[i],error:e.message});continue}
        results.push({api:apis[i],status:xhr.status,body:xhr.responseText?.substring(0,100)});
    }
    return results;
})()""")
for a in (api_test or []):
    print(f"  {a.get('api','')}: status={a.get('status','ERR')} body={str(a.get('body',''))[:80]}")

# 10. 最终状态
final = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body.innerText||'').substring(0,200)})")
log("20.导航+登录态恢复测试", {"hash":final.get("hash"),"formCount":final.get("formCount"),"text":(final.get("text","") or "")[:100]})

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
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_step10.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step10 完成")
