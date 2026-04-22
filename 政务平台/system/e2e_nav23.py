#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析首页卡片数据 → 正确调用jumpPage → 自然导航"""
import json, time, requests, websocket

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

# Step 1: 深度分析首页组件数据
print("Step 1: 深度分析首页组件数据")
data_analysis = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
            var el=allEls[i];
            var chain=[];
            var current=el;
            for(var d=0;d<20&&current;d++){
                var comp=current.__vue__;
                if(comp){
                    var allData={};
                    // 递归搜索所有数据属性
                    function searchData(obj,prefix,depth){
                        if(depth>3||!obj)return;
                        for(var k in obj){
                            var v=obj[k];
                            if(k.startsWith('_')||k.startsWith('$'))continue;
                            var key=prefix?prefix+'.'+k:k;
                            if(Array.isArray(v)){
                                if(v.length>0){
                                    allData[key]='Array['+v.length+']';
                                    // 检查数组元素
                                    if(typeof v[0]==='object'){
                                        allData[key+'[0]']=JSON.stringify(v[0])?.substring(0,80)||'object';
                                    }
                                }else{
                                    allData[key]='Array[0]';
                                }
                            }else if(typeof v==='object'&&v!==null){
                                allData[key]='object';
                            }else if(typeof v==='string'&&v.length>0){
                                allData[key]=v.substring(0,50);
                            }else if(typeof v!=='function'){
                                allData[key]=String(v);
                            }
                        }
                    }
                    searchData(comp.$data,'data',0);
                    searchData(comp.$props,'props',0);
                    
                    var methods=Object.keys(comp.$options?.methods||{});
                    var jumpMethods=methods.filter(function(m){return m.includes('jump')||m.includes('Jump')||m.includes('go')||m.includes('Go')||m.includes('to')||m.includes('To')||m.includes('handle')||m.includes('Handle')||m.includes('click')||m.includes('Click')||m.includes('banLi')});
                    
                    chain.push({
                        depth:d,
                        compName:comp.$options?.name||'',
                        tag:current.tagName,
                        class:(current.className||'').substring(0,40),
                        methods:methods.slice(0,20),
                        jumpMethods:jumpMethods,
                        dataKeys:Object.keys(allData).slice(0,30),
                        dataSample:allData
                    });
                }
                current=current.parentElement;
            }
            return{found:true,chain:chain};
        }
    }
    return{found:false};
})()""")

if data_analysis and data_analysis.get('found'):
    for c in data_analysis.get('chain',[]):
        if c.get('jumpMethods') or c.get('compName'):
            print(f"\n  d={c.get('depth')}: {c.get('compName','')} tag={c.get('tag','')} class={c.get('class','')}")
            print(f"    jumpMethods: {c.get('jumpMethods',[])}")
            ds = c.get('dataSample',{})
            # 找包含设立登记/数组的数据
            for k,v in ds.items():
                if '设立' in str(v) or '登记' in str(v) or 'Array[' in str(v) or 'busi' in k.lower() or 'list' in k.lower() or 'card' in k.lower() or 'item' in k.lower() or 'service' in k.lower():
                    print(f"    {k}: {v}")
else:
    print("  not found")

# Step 2: 获取jumpPage完整源码
print("\nStep 2: 获取jumpPage源码")
jump_src = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
            var current=allEls[i];
            for(var d=0;d<20&&current;d++){
                var comp=current.__vue__;
                if(comp){
                    var methods=comp.$options?.methods||{};
                    for(var m in methods){
                        if(m.includes('jump')||m.includes('Jump')||m.includes('banLi')||m.includes('toBanLi')){
                            return{name:m,src:methods[m].toString().substring(0,1200),depth:d,compName:comp.$options?.name||''};
                        }
                    }
                }
                current=current.parentElement;
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  name: {jump_src.get('name','')}")
print(f"  src: {jump_src.get('src','')[:600]}")

# Step 3: 获取组件的完整数据（特别是包含设立登记的列表）
print("\nStep 3: 获取包含设立登记的列表数据")
list_data = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
            var current=allEls[i];
            for(var d=0;d<20&&current;d++){
                var comp=current.__vue__;
                if(comp){
                    var data=comp.$data||{};
                    // 搜索所有数组属性
                    for(var k in data){
                        var v=data[k];
                        if(Array.isArray(v)&&v.length>0){
                            // 检查数组中是否有设立登记
                            var found=false;
                            for(var j=0;j<v.length;j++){
                                var itemStr=JSON.stringify(v[j])||'';
                                if(itemStr.includes('设立')||itemStr.includes('登记')||itemStr.includes('07')){
                                    return{key:k,len:v.length,foundIdx:j,item:JSON.stringify(v[j]).substring(0,300),allItems:v.slice(0,5).map(function(x){return JSON.stringify(x).substring(0,80)})};
                                }
                            }
                        }
                        // 也检查嵌套对象
                        if(typeof v==='object'&&v!==null&&!Array.isArray(v)){
                            for(var k2 in v){
                                var v2=v[k2];
                                if(Array.isArray(v2)&&v2.length>0){
                                    for(var j=0;j<v2.length;j++){
                                        var itemStr=JSON.stringify(v2[j])||'';
                                        if(itemStr.includes('设立')||itemStr.includes('登记')||itemStr.includes('07')){
                                            return{key:k+'.'+k2,len:v2.length,foundIdx:j,item:JSON.stringify(v2[j]).substring(0,300),allItems:v2.slice(0,5).map(function(x){return JSON.stringify(x).substring(0,80)})};
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                current=current.parentElement;
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  key: {list_data.get('key','') if list_data else ''}")
print(f"  foundIdx: {list_data.get('foundIdx','') if list_data else ''}")
print(f"  item: {list_data.get('item','')[:200] if list_data else ''}")
print(f"  allItems: {list_data.get('allItems',[]) if list_data else []}")

# Step 4: 用正确的数据调用jumpPage
print("\nStep 4: 用正确数据调用jumpPage")
if list_data and list_data.get('key'):
    key = list_data['key']
    idx = list_data.get('foundIdx',0)
    
    # 安装XHR拦截器
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
    
    result = ev(f"""(function(){{
        var allEls=document.querySelectorAll('*');
        for(var i=0;i<allEls.length;i++){{
            var t=allEls[i].textContent?.trim()||'';
            if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){{
                var current=allEls[i];
                for(var d=0;d<20&&current;d++){{
                    var comp=current.__vue__;
                    if(comp){{
                        var methods=comp.$options?.methods||{{}};
                        for(var m in methods){{
                            if(m.includes('jump')||m.includes('Jump')||m.includes('banLi')||m.includes('toBanLi')){{
                                // 获取数据
                                var keys='{key}'.split('.');
                                var arr=comp.$data;
                                for(var ki=0;ki<keys.length;ki++){{arr=arr?.[keys[ki]]}}
                                if(Array.isArray(arr)&&arr.length>{idx}){{
                                    try{{
                                        methods[m].call(comp,arr[{idx}]);
                                        return{{called:true,method:m,item:JSON.stringify(arr[{idx}]).substring(0,100)}};
                                    }}catch(e){{
                                        return{{error:e.message,method:m}};
                                    }}
                                }}
                            }}
                        }}
                    }}
                    current=current.parentElement;
                }}
            }}
        }}
        return{{error:'not_found'}};
    }})()""")
    print(f"  result: {result}")
    time.sleep(5)
    
    # 检查API和页面
    api_logs = ev("window.__api_logs||[]")
    for l in (api_logs or []):
        url = l.get('url','')
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    
    page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")
    
    # Step 5: 如果到了企业开办专区，继续
    if page and 'enterprise' in page.get('hash',''):
        print("\nStep 5: 在企业开办专区，点击开始办理")
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(5)
        
        page2 = ev("({hash:location.hash})")
        print(f"  hash={page2.get('hash','') if page2 else '?'}")
        
        # 在名称选择页
        if page2 and ('without-name' in page2.get('hash','') or 'select-prise' in page2.get('hash','')):
            print("  在名称选择页")
            
            # 转到select-prise
            if 'without-name' in page2.get('hash',''):
                ev("""(function(){var vm=document.getElementById('app')?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var wn=findComp(vm,'without-name',0);if(wn&&typeof wn.toSelectName==='function')wn.toSelectName()})()""")
                time.sleep(3)
            
            # 调用getData
            print("  调用getData...")
            ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(sp&&typeof sp.getData==='function')sp.getData()})()""")
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
                        if resp.get('code') == '00000':
                            data = resp.get('data')
                            print(f"    data: {json.dumps(data,ensure_ascii=False)[:150]}")
                    except: pass
            
            # 检查priseList
            pl = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(!sp)return null;var pl=sp.$data?.priseList||[];return{len:pl.length,items:pl.slice(0,3).map(function(p){return JSON.stringify(p).substring(0,100)})}})()""")
            print(f"  priseList: len={pl.get('len',0) if pl else 0}")
            
            if pl and pl.get('len',0) > 0:
                # 选择第一个
                print("  选择第一个列表项...")
                ev("""(function(){var rows=document.querySelectorAll('.el-table__row');for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}})()""")
                time.sleep(2)
                
                comp = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);return{nameId:sp?.$data?.nameId||'',priseName:sp?.$data?.priseName||''}})()""")
                print(f"  comp: {comp}")
                
                if comp and comp.get('nameId'):
                    nid = comp['nameId']
                    print(f"  ✅ nameId={nid}，调用startSheli")
                    ev(f"""(function(){{var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}var sp=findComp(vm,'select-prise',0);if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}})}})()""")
                    time.sleep(8)
                    
                    # 检查flow路由
                    routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
                    print(f"  flow routes: {routes.get('flow',[])}")
                    
                    if routes.get('flow'):
                        for route in routes.get('flow',[]):
                            if 'basic-info' in route:
                                ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                                time.sleep(5)
                                break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
print(f"  flow routes: {routes.get('flow',[])}")

ws.close()
print("✅ 完成")
