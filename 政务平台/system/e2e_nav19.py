#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 在select-prise组件上调用startSheli → 监控bindName API → 获取nameId → 注册flow路由"""
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

# Step 1: 回首页恢复状态
print("Step 1: 恢复状态")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm&&vm.$router)vm.$router.push('/index/page');
})()""")
time.sleep(2)

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
time.sleep(1)

# Step 2: 导航到select-prise
print("\nStep 2: 导航到select-prise")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

# 如果在without-name，转到select-prise
if page and 'without-name' in page.get('hash',''):
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var wn=findComp(vm,'without-name',0);if(wn&&typeof wn.toSelectName==='function')wn.toSelectName()})()""")
    time.sleep(3)

page = ev("({hash:location.hash})")
print(f"  hash2={page.get('hash','') if page else '?'}")

# Step 3: 安装XHR拦截器
print("\nStep 3: 安装XHR拦截器")
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

# Step 4: 在select-prise组件上调用startSheli（组件内部能访问this.$api）
print("\nStep 4: 调用startSheli")
# 先分析select-prise组件的fromType
comp_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    return{
        compName:sp.$options?.name||'',
        fromType:sp.$data?.fromType||'',
        nameId:sp.$data?.nameId||'',
        priseName:sp.$data?.priseName||'',
        priseNo:sp.$data?.priseNo||'',
        hash:location.hash
    };
})()""")
print(f"  comp: {comp_info}")

# 调用startSheli，传入{nameId, entType}
# startSheli内部会调用this.$api.index.bindName({nId: t.nameId})
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    if(typeof sp.startSheli!=='function')return{error:'no_startSheli'};
    
    // startSheli需要参数 {nameId, entType}
    try{
        var p=sp.startSheli({nameId:'test_auto_001',entType:'1100'});
        // startSheli返回Promise
        if(p&&typeof p.then==='function'){
            p.then(function(r){
                window.__startSheli_result={code:r?.code||'',data:JSON.stringify(r?.data)?.substring(0,200)||'',msg:r?.msg||''};
            }).catch(function(e){
                window.__startSheli_result={error:e.message||'unknown'};
            });
        }
        return{called:true,isPromise:!!(p&&typeof p.then==='function')};
    }catch(e){
        return{error:e.message};
    }
})()""")
print(f"  result: {result}")
time.sleep(5)

# Step 5: 检查API调用和结果
print("\nStep 5: 检查API调用")
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'getUserInfo' not in url and 'getCacheCreateTime' not in url:
        print(f"  API: {l.get('method','')} {url} status={l.get('status')} resp={l.get('response','')[:120]}")

startSheli_result = ev("window.__startSheli_result||null")
print(f"  startSheli_result: {startSheli_result}")

# Step 6: 检查路由
print("\nStep 6: 检查路由")
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
    return{total:all.length,flow:flow,namenotice:all.filter(function(r){return r.includes('namenotice')})};
})()""")
print(f"  flow routes: {routes.get('flow',[])}")
print(f"  namenotice routes: {routes.get('namenotice',[])}")

# Step 7: 如果bindName API被调用了，获取真实URL和nameId
if api_logs:
    for l in api_logs:
        url = l.get('url','')
        if 'bindName' in url or 'bind' in url:
            print(f"\n  ✅ bindName API: {url}")
            resp = l.get('response','')
            if resp:
                try:
                    resp_data = json.loads(resp)
                    if resp_data.get('code') == '00000':
                        nid = resp_data.get('data',{}).get('resultType','') if isinstance(resp_data.get('data'), dict) else ''
                        print(f"  bindName成功: {resp[:100]}")
                except: pass

# Step 8: 如果有namenotice路由，导航到declaration-instructions然后逐步前进
if routes.get('namenotice') and not routes.get('flow'):
    print("\nStep 8: 通过namenotice路由导航")
    # 先到declaration-instructions
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/namenotice/declaration-instructions')})()""")
    time.sleep(3)
    
    page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")
    
    # 逐步点击下一步
    for step in range(10):
        current = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body?.innerText||'').substring(0,80)})")
        print(f"\n  步骤{step}: hash={current.get('hash','') if current else '?'} forms={current.get('formCount',0) if current else 0}")
        
        if current and 'flow/base' in current.get('hash',''):
            print("  ✅ 到达flow/base！")
            break
        
        if current and current.get('formCount',0) > 20:
            print("  ✅ 大量表单出现！")
            break
        
        # 检查当前路由
        routes_now = ev("""(function(){
            var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
            function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
            var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
            return{flow:flow};
        })()""")
        if routes_now.get('flow'):
            print(f"  flow路由已注册: {routes_now.get('flow',[])}")
            for route in routes_now.get('flow',[]):
                if 'basic-info' in route or 'base' in route:
                    ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                    time.sleep(5)
                    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
                    if fc and fc.get('formCount',0) > 10:
                        print(f"  ✅ 表单加载: hash={fc.get('hash','')} forms={fc.get('formCount',0)}")
                        break
            break
        
        # 点击下一步
        clicked = False
        for btn_text in ['下一步','确定','确认','同意','我已阅读','继续','保存并下一步','我同意']:
            cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null&&!btns[i].disabled){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
            if cr and cr.get('clicked'):
                print(f"  点击: {btn_text}")
                clicked = True
                time.sleep(3)
                break
        
        if not clicked:
            # 尝试checkbox（同意条款）
            ev("""(function(){var cbs=document.querySelectorAll('.el-checkbox__input:not(.is-checked)');for(var i=0;i<cbs.length;i++){cbs[i].click()}})()""")
            time.sleep(1)
            # 重试
            for btn_text in ['下一步','确定','同意']:
                cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
                if cr and cr.get('clicked'):
                    print(f"  点击(重试): {btn_text}")
                    time.sleep(3)
                    break
            else:
                print("  无按钮可点击")
                break
        
        # 检查API
        api_logs2 = ev("window.__api_logs||[]")
        new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])] and 'getUserInfo' not in l.get('url','') and 'getCacheCreateTime' not in l.get('url','')]
        for l in new_apis[-3:]:
            print(f"  API: {l.get('method','')} {l.get('url','').split('?')[0].split('/').pop()} status={l.get('status')}")
        api_logs = api_logs2

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("490.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("490.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})

ws.close()
print("✅ 完成")
