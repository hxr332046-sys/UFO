#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 分析$api.index.bindName真实URL → 获取nameId → 注册flow路由"""
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

# 确保在select-prise
page = ev("({hash:location.hash})")
if not page or 'select-prise' not in page.get('hash',''):
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(3)
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var wn=findComp(vm,'without-name',0);if(wn&&typeof wn.toSelectName==='function')wn.toSelectName()})()""")
    time.sleep(3)

# Step 1: 深入分析$api对象结构
print("Step 1: 分析$api对象结构")
api_analysis = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp||!sp.$api)return{error:'no_api'};
    var api=sp.$api;
    var result={};
    for(var k in api){
        var v=api[k];
        if(typeof v==='object'&&v!==null){
            var subKeys=Object.keys(v);
            var subResult={};
            for(var j=0;j<subKeys.length;j++){
                var sv=v[subKeys[j]];
                if(typeof sv==='function'){
                    subResult[subKeys[j]]=sv.toString().substring(0,200);
                }else{
                    subResult[subKeys[j]]=typeof sv;
                }
            }
            result[k]=subResult;
        }else if(typeof v==='function'){
            result[k]=v.toString().substring(0,200);
        }
    }
    return result;
})()""")
print(f"  $api keys: {list(api_analysis.keys()) if api_analysis else 'None'}")
for k, v in (api_analysis or {}).items():
    if isinstance(v, dict):
        print(f"  $api.{k}:")
        for sk, sv in v.items():
            if 'bindName' in sk or 'bind' in sk or 'name' in sk.lower() or 'sheli' in sk or 'flow' in sk:
                print(f"    {sk}: {str(sv)[:150]}")
    elif isinstance(v, str) and ('bindName' in v or 'name' in v.lower()):
        print(f"  $api.{k}: {v[:150]}")

# Step 2: 获取bindName方法的完整源码
print("\nStep 2: 获取bindName源码")
bindname_src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp||!sp.$api||!sp.$api.index)return{error:'no_index'};
    var bindName=sp.$api.index.bindName;
    if(!bindName)return{error:'no_bindName'};
    return{src:bindName.toString().substring(0,500)};
})()""")
print(f"  bindName src: {bindname_src.get('src','')[:300] if bindname_src else 'None'}")

# Step 3: 拦截XHR并直接调用bindName
print("\nStep 3: 拦截XHR并调用bindName")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||'',body:self.__body?.substring(0,100)||''});
        });
        return origSend.apply(this,arguments);
    };
})()""")

# 直接调用bindName
bind_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp||!sp.$api||!sp.$api.index||!sp.$api.index.bindName)return{error:'no_bindName'};
    
    // 调用bindName
    return sp.$api.index.bindName({nId:'test_auto_001'}).then(function(r){
        return{code:r.code,data:JSON.stringify(r.data)?.substring(0,200)||'',msg:r.msg||''};
    }).catch(function(e){
        return{error:e.message||'unknown'};
    });
})()""")
time.sleep(3)

# 检查API调用
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'getUserInfo' not in url and 'getCacheCreateTime' not in url:
        print(f"  API: {l.get('method','')} {url} status={l.get('status')} resp={l.get('response','')[:100]}")

print(f"  bind_result: {bind_result}")

# Step 4: 如果bindName返回了nameId，调用getHandleBusiness注册flow路由
if bind_result and bind_result.get('code') == '00000':
    print("\nStep 4: bindName成功，调用getHandleBusiness")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness({entType:'1100',nameId:'test_auto_001'});
    })()""")
    time.sleep(3)
    
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")
else:
    # Step 4b: bindName失败，分析原因
    print("\nStep 4b: bindName失败，分析原因")
    
    # 检查是否有"请先选择名称"之类的错误
    err_msg = ev("""(function(){
        var msgs=document.querySelectorAll('.el-message,[class*="error"],[class*="message"]');
        var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}
        return r.slice(0,5);
    })()""")
    print(f"  错误消息: {err_msg}")
    
    # 尝试先选择一个名称再调用startSheli
    print("\n  尝试先获取名称列表...")
    # 调用getData
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.getData==='function')sp.getData();
    })()""")
    time.sleep(3)
    
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis:
        print(f"  NEW API: {l.get('method','')} {l.get('url','')} status={l.get('status')} resp={l.get('response','')[:150]}")
    
    # 检查列表
    list_data = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return null;
        var pl=sp.$data?.priseList||[];
        return{len:pl.length,items:pl.slice(0,3).map(function(p){return JSON.stringify(p).substring(0,100)})};
    })()""")
    print(f"  priseList: len={list_data.get('len',0) if list_data else 0}")
    
    if list_data and list_data.get('len',0) > 0:
        print("  选择第一个列表项...")
        ev("""(function(){var rows=document.querySelectorAll('.el-table__row');for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}})()""")
        time.sleep(2)
        
        # 再次调用startSheli
        comp = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var sp=findComp(vm,'select-prise',0);
            return{nameId:sp?.$data?.nameId||'',priseName:sp?.$data?.priseName||''};
        })()""")
        print(f"  comp: {comp}")
        
        if comp and comp.get('nameId'):
            nid = comp['nameId']
            print(f"  ✅ nameId={nid}，调用startSheli")
            ev(f"""(function(){{
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}});
            }})()""")
            time.sleep(5)
            
            # 检查路由
            routes2 = ev("""(function(){
                var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
                function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
                var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
                return{total:all.length,flow:flow};
            })()""")
            print(f"  routes: total={routes2.get('total',0)} flow={routes2.get('flow',[])}")
            
            api_logs3 = ev("window.__api_logs||[]")
            new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs2 or [])]]
            for l in new_apis3:
                print(f"  API3: {l.get('method','')} {l.get('url','')} status={l.get('status')} resp={l.get('response','')[:100]}")
    else:
        # 没有名称列表，需要创建名称
        print("  无名称列表，尝试创建名称...")
        
        # 分析$api.index的所有方法
        print("\n  分析$api.index所有方法")
        index_methods = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var sp=findComp(vm,'select-prise',0);
            if(!sp||!sp.$api||!sp.$api.index)return null;
            var idx=sp.$api.index;
            var methods={};
            for(var k in idx){
                if(typeof idx[k]==='function'){
                    methods[k]=idx[k].toString().substring(0,150);
                }
            }
            return methods;
        })()""")
        print(f"  $api.index methods: {index_methods}")
        
        # 尝试调用$api.index的其他方法
        if index_methods:
            for method_name, method_src in index_methods.items():
                if 'save' in method_name.lower() or 'insert' in method_name.lower() or 'create' in method_name.lower() or 'add' in method_name.lower():
                    print(f"\n  尝试调用 {method_name}...")
                    result = ev(f"""(function(){{
                        var app=document.getElementById('app');var vm=app?.__vue__;
                        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                        var sp=findComp(vm,'select-prise',0);
                        if(!sp||!sp.$api||!sp.$api.index||!sp.$api.index.{method_name})return{{error:'no_method'}};
                        return sp.$api.index.{method_name}({{name:'广西智信数据科技有限公司',numbers:'GX2024001',entType:'1100',nId:'test_auto_001'}}).then(function(r){{
                            return{{code:r.code,data:JSON.stringify(r.data)?.substring(0,200)||'',msg:r.msg||''}};
                        }}).catch(function(e){{return{{error:e.message||'unknown'}}}});
                    }})()""")
                    time.sleep(3)
                    print(f"  result: {result}")
                    
                    api_logs3 = ev("window.__api_logs||[]")
                    new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs2 or [])]]
                    for l in new_apis3:
                        print(f"  API3: {l.get('method','')} {l.get('url','')} status={l.get('status')} resp={l.get('response','')[:100]}")
                    
                    if result and result.get('code') == '00000':
                        print("  ✅ 成功！")
                        break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
    return{total:all.length,flow:flow};
})()""")
print(f"  flow routes: {routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("480.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("480.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0,"flowRoutes":routes.get('flow',[])})

ws.close()
print("✅ 完成")
