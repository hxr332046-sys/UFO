#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 用$router.jump传递params → namenotice页面正常渲染 → 逐步前进 → flow路由注册 → 表单"""
import json, time, os, requests, websocket
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# 恢复Vuex
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")

# Step 1: 分析$router.jump方法
print("Step 1: 分析$router.jump")
jump_info = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var router=vm?.$router;
    if(!router)return{error:'no_router'};
    return{
        hasJump:typeof router.jump==='function',
        jumpSrc:router.jump?.toString()?.substring(0,800)||'',
        currentRoute:JSON.stringify({path:router.currentRoute?.path,query:router.currentRoute?.query,params:router.currentRoute?.params})?.substring(0,200)||''
    };
})()""")
print(f"  hasJump: {jump_info.get('hasJump') if jump_info else '?'}")
print(f"  jumpSrc: {jump_info.get('jumpSrc','')[:400] if jump_info else ''}")

# Step 2: 用$router.jump导航到namenotice/name-changerule（带params）
print("\nStep 2: $router.jump到namenotice/name-changerule")
jump_result = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var router=vm?.$router;
    if(!router||typeof router.jump!=='function')return{error:'no_jump'};
    try{
        router.jump({
            project:'name-register',
            path:'namenotice/name-changerule',
            params:{busiType:'07',busiId:'',entType:'1100',nameId:'test_auto_001'},
            target:'_self'
        });
        return{called:true};
    }catch(e){return{error:e.message}}
})()""")
print(f"  jump_result: {jump_result}")
time.sleep(5)

page = ev("""(function(){return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,btnCount:document.querySelectorAll('button').length,text:(document.body?.innerText||'').substring(0,150)}})()""")
print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0} btns={page.get('btnCount',0) if page else 0}")
print(f"  text: {page.get('text','')[:80] if page else ''}")

# Step 3: 如果页面有内容，分析组件
if page and page.get('btnCount',0) > 0:
    print("\nStep 3: 分析页面组件")
    comp = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,d){if(d>10)return null;
            if(vm.$el&&vm.$el.offsetParent!==null&&vm.$options?.name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],d+1);if(r)return r}return null}
        // 找namenotice相关组件
        function findByName(vm,name,d){if(d>15)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findByName(vm.$children[i],name,d+1);if(r)return r}return null}
        
        var nc=findByName(vm,'name-changerule',0)||findByName(vm,'declaration-instructions',0)||findByName(vm,'namenotice',0);
        if(!nc){
            // 找所有有methods的组件
            var all=[];
            function findAll(vm,d){if(d>10)return;if(vm.$options?.name&&vm.$el?.offsetParent!==null){all.push({name:vm.$options.name,methods:Object.keys(vm.$options?.methods||{}).slice(0,5)})}for(var i=0;i<(vm.$children||[]).length;i++)findAll(vm.$children[i],d+1)}
            findAll(vm,0);
            return{error:'no_comp',allComps:all.slice(0,10)};
        }
        return{
            compName:nc.$options?.name||'',
            methods:Object.keys(nc.$options?.methods||{}).slice(0,15),
            dataKeys:Object.keys(nc.$data||{}).slice(0,15),
            routeParams:JSON.stringify(nc.$route?.params)||'',
            routeQuery:JSON.stringify(nc.$route?.query)||''
        };
    })()""")
    print(f"  comp: {comp}")

# Step 4: 安装XHR拦截器
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,200)||'',body:self.__body?.substring(0,100)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 5: 逐步前进
print("\nStep 5: 逐步前进")
for step in range(15):
    current = ev("""(function(){return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,btnCount:document.querySelectorAll('button:not([disabled])').length,checkboxCount:document.querySelectorAll('.el-checkbox:not(.is-checked)').length,text:(document.body?.innerText||'').substring(0,100)}})()""")
    h = current.get('hash','') if current else '?'
    fc = current.get('formCount',0) if current else 0
    bc = current.get('btnCount',0) if current else 0
    cc = current.get('checkboxCount',0) if current else 0
    
    print(f"\n  步骤{step}: hash={h} forms={fc} btns={bc} checkboxes={cc}")
    
    if fc > 20:
        print("  ✅ 大量表单出现！")
        break
    
    # 检查flow路由
    flow_routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow/base')});
        return flow;
    })()""")
    if flow_routes:
        print(f"  ✅ flow/base路由已注册: {flow_routes}")
        for route in flow_routes:
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(5)
            fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            if fc2 and fc2.get('formCount',0) > 10:
                print(f"  ✅ 表单加载: {fc2}")
                current = fc2
                break
        break
    
    # 先勾选checkbox
    if cc > 0:
        ev("""(function(){var cbs=document.querySelectorAll('.el-checkbox__input:not(.is-checked)');for(var i=0;i<cbs.length;i++){cbs[i].click()}})()""")
        time.sleep(1)
    
    # 点击按钮
    clicked = False
    btns = ev("""(function(){var btns=document.querySelectorAll('button,.el-button');var r=[];for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null&&!btns[i].disabled){var t=btns[i].textContent?.trim()||'';if(t)r.push({idx:i,text:t.substring(0,20)})}}return r})()""")
    
    for btn in (btns or []):
        t = btn.get('text','')
        idx = btn.get('idx',0)
        if any(kw in t for kw in ['下一步','确定','确认','同意','我已阅读','继续','保存并下一步','我同意','开始']):
            print(f"  点击: {t}")
            ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
            clicked = True
            time.sleep(3)
            break
    
    if not clicked:
        # 尝试Vue组件方法
        print("  尝试Vue组件下一步方法...")
        ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findByName(vm,name,d){if(d>15)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findByName(vm.$children[i],name,d+1);if(r)return r}return null}
            // 找当前页面组件
            function findActive(vm,d){if(d>10)return null;if(vm.$options?.name&&vm.$el?.offsetParent!==null){var methods=vm.$options?.methods||{};for(var m in methods){if(m.includes('next')||m.includes('Next')||m.includes('handle')||m.includes('submit')){try{methods[m].call(vm);return m}catch(e){}}}}for(var i=0;i<(vm.$children||[]).length;i++){var r=findActive(vm.$children[i],d+1);if(r)return r}return null}
            var result=findActive(vm,0);
        })()""")
        time.sleep(3)
    
    # 检查API
    api_logs = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs or []) if 'getUserInfo' not in l.get('url','') and 'getCacheCreateTime' not in l.get('url','')]
    if new_apis:
        for l in new_apis[-3:]:
            print(f"  API: {l.get('method','')} {l.get('url','').split('?')[0].split('/').pop()} status={l.get('status')}")

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("500.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    # 最后检查flow路由
    routes_final = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  flow routes: {routes_final.get('flow',[])}")
    log("500.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0,"flowRoutes":routes_final.get('flow',[])})

ws.close()
print("✅ 完成")
