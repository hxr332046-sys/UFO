#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 分析startSheli/getHandleBusiness完整源码 → 直接调用API获取nameId → 注册路由"""
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

# 确保在without-name页面
page = ev("({hash:location.hash})")
if not page or 'without-name' not in page.get('hash',''):
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(5)

# Step 1: 获取startSheli完整源码
print("Step 1: 获取startSheli完整源码")
src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
    if(!wn)return{error:'no_comp'};
    return{
        startSheli:wn.$options?.methods?.startSheli?.toString()?.substring(0,1500)||'no_method',
        getHandleBusiness:wn.$options?.methods?.getHandleBusiness?.toString()?.substring(0,1500)||'no_method',
        compName:wn.$options?.name||'',
        fromType:wn.$data?.fromType||'',
        nameId:wn.$data?.nameId||''
    };
})()""")
print(f"  compName: {src.get('compName','') if src else '?'}")
print(f"  fromType: {src.get('fromType','') if src else ''}")
print(f"  startSheli: {src.get('startSheli','')[:600] if src else 'None'}")
print(f"  getHandleBusiness: {src.get('getHandleBusiness','')[:600] if src else 'None'}")

# Step 2: 如果在without-name，需要先到select-prise
if src and src.get('compName','') == 'without-name':
    print("\nStep 2: 导航到select-prise")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0);
        if(wn&&typeof wn.toSelectName==='function')wn.toSelectName();
    })()""")
    time.sleep(3)
    
    page2 = ev("({hash:location.hash})")
    print(f"  hash={page2.get('hash','') if page2 else '?'}")
    
    # 重新获取select-prise源码
    src2 = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return{error:'no_comp'};
        return{
            startSheli:sp.$options?.methods?.startSheli?.toString()?.substring(0,1500)||'no_method',
            getHandleBusiness:sp.$options?.methods?.getHandleBusiness?.toString()?.substring(0,1500)||'no_method',
            fromType:sp.$data?.fromType||'',
            nameId:sp.$data?.nameId||''
        };
    })()""")
    print(f"  startSheli: {src2.get('startSheli','')[:800] if src2 else 'None'}")
    print(f"  getHandleBusiness: {src2.get('getHandleBusiness','')[:800] if src2 else 'None'}")

# Step 3: 分析$api对象找相关API
print("\nStep 3: 分析$api对象")
api_methods = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0)||findComp(vm,'without-name',0);
    if(!sp||!sp.$api)return{error:'no_api'};
    var api=sp.$api;
    var keys=Object.keys(api);
    var nameRelated=keys.filter(function(k){return k.toLowerCase().includes('name')||k.toLowerCase().includes('sheli')||k.toLowerCase().includes('flow')||k.toLowerCase().includes('business')||k.toLowerCase().includes('handle')});
    var allRelated={};
    for(var i=0;i<nameRelated.length;i++){
        var v=api[nameRelated[i]];
        if(typeof v==='function'){
            allRelated[nameRelated[i]]=v.toString().substring(0,200);
        }else if(typeof v==='object'){
            allRelated[nameRelated[i]]=JSON.stringify(v)?.substring(0,100)||'object';
        }
    }
    return{totalKeys:keys.length,nameRelated:nameRelated,allRelated:allRelated};
})()""")
print(f"  totalKeys: {api_methods.get('totalKeys',0) if api_methods else 0}")
print(f"  nameRelated: {api_methods.get('nameRelated',[]) if api_methods else []}")
for k, v in (api_methods.get('allRelated',{}) or {}).items():
    print(f"  {k}: {v[:150]}")

# Step 4: 直接调用$api方法获取nameId
print("\nStep 4: 直接调用$api方法")
api_call = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0)||findComp(vm,'without-name',0);
    if(!sp||!sp.$api)return{error:'no_api'};
    
    // 尝试调用startSheli相关的API
    // startSheli源码中调用了 e.$api.in... 可能是insertName或initName
    var api=sp.$api;
    var results=[];
    
    // 查找所有API方法
    for(var k in api){
        if(typeof api[k]==='function'){
            var fnStr=api[k].toString();
            // 找包含nameId或nId的API
            if(fnStr.includes('nameId')||fnStr.includes('nId')||fnStr.includes('sheli')||fnStr.includes('insert')||fnStr.includes('init')||fnStr.includes('save')){
                results.push({key:k,src:fnStr.substring(0,200)});
            }
        }
    }
    return{results:results};
})()""")
print(f"  results: {api_call}")

# Step 5: 尝试直接调用getHandleBusiness注册路由（用假nameId）
print("\nStep 5: 尝试getHandleBusiness注册路由")
ghb_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0)||findComp(vm,'without-name',0);
    if(!sp)return{error:'no_comp'};
    
    // getHandleBusiness需要参数 {entType, nameId}
    if(typeof sp.getHandleBusiness==='function'){
        try{
            sp.getHandleBusiness({entType:'1100',nameId:'test_auto_001'});
            return{called:true};
        }catch(e){
            return{error:e.message};
        }
    }
    return{error:'no_method'};
})()""")
print(f"  result: {ghb_result}")
time.sleep(3)

# 检查路由
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

# Step 6: 如果路由注册了，导航到表单
if routes.get('flow'):
    print("\nStep 6: 导航到表单")
    for route in routes.get('flow',[]):
        if 'basic-info' in route or 'base' in route:
            print(f"  导航: {route}")
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(5)
            break
    
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
else:
    # Step 6b: 分析$router.jump方法
    print("\nStep 6b: 分析$router.jump")
    jump_src = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        if(!router)return{error:'no_router'};
        return{
            hasJump:typeof router.jump==='function',
            jumpSrc:router.jump?.toString()?.substring(0,500)||'no_method',
            hasPush:typeof router.push==='function',
            addRoutes:router.addRoutes?.toString()?.substring(0,200)||'no_method',
            addRoute:router.addRoute?.toString()?.substring(0,200)||'no_method'
        };
    })()""")
    print(f"  jump: {jump_src}")
    
    # 尝试手动调用$router.jump注册路由
    print("\n  尝试$router.jump注册路由...")
    ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        if(router&&typeof router.jump==='function'){
            try{
                router.jump({
                    project:'name-register',
                    path:'namenotice/name-changerule',
                    params:{busiType:'07',busiId:'',entType:'1100',nameId:'test_auto_001'},
                    target:'_self'
                });
                return{called:true};
            }catch(e){
                return{error:e.message};
            }
        }
    })()""")
    time.sleep(3)
    
    routes2 = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  routes2: total={routes2.get('total',0)} flow={routes2.get('flow',[])}")
    
    if routes2.get('flow'):
        for route in routes2.get('flow',[]):
            if 'basic-info' in route:
                ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                time.sleep(5)
                break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

log("460.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0,"flowRoutes":routes.get('flow',[])})
ws.close()
print("✅ 完成")
