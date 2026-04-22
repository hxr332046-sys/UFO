#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""获取真实nameId → 注册flow路由 → 加载表单"""
import json, time, os, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 恢复Vuex + 回首页
print("Step 1: 恢复状态")
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
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/page')})()""")
time.sleep(3)

# Step 2: 导航到select-prise
print("\nStep 2: 导航到select-prise")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)
# 如果在without-name，转到select-prise
ev("""(function(){var vm=document.getElementById('app')?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var wn=findComp(vm,'without-name',0);if(wn&&typeof wn.toSelectName==='function')wn.toSelectName()})()""")
time.sleep(3)

page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

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
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')&&!self.__url.includes('selectModuleFlows')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,400)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 在select-prise上调用searchBtn/getData获取名称列表
print("\nStep 4: 调用searchBtn/getData")
# 先分析searchBtn源码
src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    return{
        searchBtn:sp.$options?.methods?.searchBtn?.toString()?.substring(0,400)||'',
        getData:sp.$options?.methods?.getData?.toString()?.substring(0,400)||'',
        initData:sp.$options?.methods?.initData?.toString()?.substring(0,400)||'',
        searchKeyWord:sp.$data?.searchKeyWord||'',
        fromType:sp.$data?.fromType||'',
        priseListLen:sp.$data?.priseList?.length||0
    };
})()""")
print(f"  searchBtn: {src.get('searchBtn','')[:200] if src else 'None'}")
print(f"  getData: {src.get('getData','')[:200] if src else 'None'}")
print(f"  fromType: {src.get('fromType','') if src else ''}")
print(f"  priseListLen: {src.get('priseListLen',0) if src else 0}")

# 调用searchBtn
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(sp){
        // 设置搜索关键词
        sp.$set(sp.$data,'searchKeyWord','广西智信');
        if(typeof sp.searchBtn==='function')sp.searchBtn();
        else if(typeof sp.getData==='function')sp.getData();
    }
})()""")
time.sleep(5)

# Step 5: 检查API调用
print("\nStep 5: 检查API调用")
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
    if l.get('status') == 200:
        try:
            resp = json.loads(l.get('response','{}'))
            if resp.get('code') == '00000':
                data = resp.get('data',{})
                if isinstance(data, dict):
                    print(f"    data keys: {list(data.keys())[:10]}")
                    if 'busiData' in data:
                        bd = data['busiData']
                        if isinstance(bd, list) and len(bd) > 0:
                            print(f"    busiData[0]: {json.dumps(bd[0], ensure_ascii=False)[:150]}")
                        elif isinstance(bd, dict):
                            print(f"    busiData keys: {list(bd.keys())[:10]}")
                elif isinstance(data, list) and len(data) > 0:
                    print(f"    data[0]: {json.dumps(data[0], ensure_ascii=False)[:150]}")
        except: pass

# Step 6: 检查priseList
print("\nStep 6: 检查priseList")
list_data = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return null;
    var pl=sp.$data?.priseList||[];
    return{len:pl.length,items:pl.slice(0,5).map(function(p){return JSON.stringify(p).substring(0,120)})};
})()""")
print(f"  priseList: len={list_data.get('len',0) if list_data else 0}")
for item in (list_data.get('items',[]) if list_data else []):
    print(f"    {item}")

# Step 7: 如果有列表项，选择并调用startSheli
if list_data and list_data.get('len',0) > 0:
    print("\nStep 7: 选择列表项")
    # 点击第一行
    ev("""(function(){
        var rows=document.querySelectorAll('.el-table__row');
        for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}
    })()""")
    time.sleep(2)
    
    # 检查nameId
    comp = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        return{nameId:sp?.$data?.nameId||'',priseName:sp?.$data?.priseName||'',priseNo:sp?.$data?.priseNo||''};
    })()""")
    print(f"  comp: {comp}")
    
    if comp and comp.get('nameId'):
        nid = comp['nameId']
        print(f"  ✅ nameId={nid}")
        
        # 调用startSheli
        print("  调用startSheli...")
        ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var sp=findComp(vm,'select-prise',0);
            if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}});
        }})()""")
        time.sleep(5)
        
        # 检查API
        api_logs2 = ev("window.__api_logs||[]")
        new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
        for l in new_apis:
            url = l.get('url','')
            print(f"  NEW API: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
            if l.get('status') == 200:
                try:
                    resp = json.loads(l.get('response','{}'))
                    print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:50]}")
                except: pass
        
        # 检查flow路由
        routes = ev("""(function(){
            var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
            function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
            var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
            return{total:all.length,flow:flow};
        })()""")
        print(f"  flow routes: {routes.get('flow',[])}")
        
        if routes.get('flow'):
            # 导航到flow/base/basic-info
            for route in routes.get('flow',[]):
                if 'basic-info' in route:
                    print(f"  导航: {route}")
                    ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                    time.sleep(5)
                    break
    else:
        # 没有nameId，可能需要点击"开始办理"按钮
        print("  无nameId，点击开始办理...")
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){var t=btns[i].textContent?.trim()||'';if((t.includes('开始办理')||t.includes('下一步')||t.includes('确定'))&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(3)
else:
    # Step 7b: 没有列表项，使用其他来源名称
    print("\nStep 7b: 使用其他来源名称")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp){
            if(typeof sp.toOther==='function')sp.toOther();
            else if('isOther' in sp.$data)sp.$set(sp.$data,'isOther',true);
            sp.$forceUpdate();
        }
    })()""")
    time.sleep(2)
    
    # 填写表单
    ev("""(function(){
        var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
        var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
        for(var i=0;i<inputs.length;i++){
            var ph=inputs[i].placeholder||'';
            if(ph.includes('企业名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
            if(ph.includes('保留单号')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
        }
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&sp.$data?.form){sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');sp.$set(sp.$data.form,'numbers','GX2024001');sp.$forceUpdate()}
    })()""")
    time.sleep(1)
    
    # 找提交按钮
    btns = ev("""(function(){var btns=document.querySelectorAll('button,.el-button');var r=[];for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||''})}return r})()""")
    print(f"  按钮: {btns}")
    
    # 点击选择已有名称/确定
    for btn in (btns or []):
        t = btn.get('text','')
        idx = btn.get('idx',0)
        if any(kw in t for kw in ['确定','确认','选择','提交','保存']):
            print(f"  点击: {t}")
            ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
            time.sleep(3)
            
            # 检查API
            api_logs2 = ev("window.__api_logs||[]")
            new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
            for l in new_apis:
                url = l.get('url','')
                print(f"  NEW API: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
                if l.get('status') == 200:
                    try:
                        resp = json.loads(l.get('response','{}'))
                        print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:100]}")
                    except: pass
            break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 如果有flow路由，导航
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
    return{total:all.length,flow:flow};
})()""")
print(f"  flow routes: {routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
elif routes.get('flow'):
    for route in routes.get('flow',[]):
        if 'basic-info' in route:
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(5)
            fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            print(f"  导航后: hash={fc2.get('hash','') if fc2 else '?'} forms={fc2.get('formCount',0) if fc2 else 0}")
            if fc2 and fc2.get('formCount',0) > 10:
                print("✅ 表单已加载！")
            break

ws.close()
print("✅ 完成")
