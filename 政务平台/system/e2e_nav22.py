#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完全重载页面 → 逐步UI导航 → 监控所有API → 获取nameId → 表单"""
import json, time, os, requests, websocket

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    ws = websocket.create_connection(ws_url, timeout=30)
    return ws

ws = get_ws()
_mid = 0
def ev(js, ws_conn=None):
    global _mid; _mid += 1; mid = _mid
    w = ws_conn or ws
    w.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            w.settimeout(25); r = json.loads(w.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 完全重载页面
print("Step 1: 完全重载页面")
ev("""window.location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'""")
time.sleep(8)

# 重新获取WebSocket连接
ws = get_ws()

# 等Vue就绪
for attempt in range(10):
    ready = ev("(function(){return !!document.getElementById('app')?.__vue__})()")
    if ready: break
    time.sleep(2)
print(f"  Vue就绪: {ready}")

# Step 2: 恢复Vuex
print("\nStep 2: 恢复Vuex")
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
time.sleep(2)

# Step 3: 安装全局XHR拦截器（在页面级别）
print("\nStep 3: 安装XHR拦截器")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,400)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 点击"全部服务"展开服务列表
print("\nStep 4: 展开全部服务")
ev("""(function(){
    var tabs=document.querySelectorAll('[class*="tab"],[class*="nav-item"],[class*="menu-item"]');
    for(var i=0;i<tabs.length;i++){
        if(tabs[i].textContent?.trim()?.includes('全部服务')&&tabs[i].offsetParent!==null){
            tabs[i].click();return;
        }
    }
})()""")
time.sleep(2)

# Step 5: 找到"经营主体登记"或"设立登记"并点击
print("\nStep 5: 点击设立登记")
# 分析首页所有可点击的Vue组件
click_result = ev("""(function(){
    // 找所有包含"设立登记"文本的元素，找有Vue click handler的
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
            // 向上找有toBanLi方法的组件
            var current=allEls[i];
            for(var d=0;d<20&&current;d++){
                var comp=current.__vue__;
                if(comp){
                    var methods=comp.$options?.methods||{};
                    // 检查所有方法
                    for(var m in methods){
                        var src=methods[m].toString();
                        if(src.includes('router')||src.includes('jump')||src.includes('push')||src.includes('enterprise')||src.includes('namenotice')){
                            try{
                                // 获取cardlist数据
                                var cl=comp.$data?.cardlist||comp.$data?.allList||comp.$data?.listAllList||[];
                                var target=null;
                                for(var j=0;j<cl.length;j++){
                                    var n=cl[j].name||cl[j].busiName||cl[j].title||cl[j].label||'';
                                    if(n.includes('设立')||n.includes('经营主体')||n.includes('登记')){
                                        target=cl[j];break;
                                    }
                                }
                                if(target){
                                    methods[m].call(comp,target);
                                    return{called:m,card:JSON.stringify(target).substring(0,100),depth:d};
                                }else{
                                    // 没有card数据，传空
                                    methods[m].call(comp,{name:'设立登记',code:'07',busiType:'07',entType:'1100'});
                                    return{called:m+'(no_card)',depth:d};
                                }
                            }catch(e){
                                return{error:e.message,method:m,depth:d};
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
print(f"  click_result: {click_result}")
time.sleep(5)

# 检查API调用
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# Step 6: 如果到了企业开办专区，点击开始办理
if page and 'enterprise' in page.get('hash',''):
    print("\nStep 6: 点击开始办理")
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(5)
    
    page2 = ev("({hash:location.hash})")
    print(f"  hash={page2.get('hash','') if page2 else '?'}")
    
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis:
        url = l.get('url','')
        print(f"  NEW API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200 and 'selectModuleFlows' not in url:
            try:
                resp = json.loads(l.get('response','{}'))
                if resp.get('code') == '00000':
                    print(f"    data: {json.dumps(resp.get('data',''),ensure_ascii=False)[:100]}")
            except: pass
    api_logs = api_logs2

# Step 7: 在without-name/select-prise页面
page = ev("({hash:location.hash})")
print(f"\nStep 7: 当前hash={page.get('hash','') if page else '?'}")

if page and ('without-name' in page.get('hash','') or 'select-prise' in page.get('hash','')):
    print("  在名称选择页")
    
    # 如果在without-name，转到select-prise
    if 'without-name' in page.get('hash',''):
        ev("""(function(){var vm=document.getElementById('app')?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var wn=findComp(vm,'without-name',0);if(wn&&typeof wn.toSelectName==='function')wn.toSelectName()})()""")
        time.sleep(3)
    
    # 分析select-prise组件
    comp = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return{error:'no_comp'};
        return{
            fromType:sp.$data?.fromType||'',
            priseListLen:sp.$data?.priseList?.length||0,
            isOther:sp.$data?.isOther||false,
            searchKeyWord:sp.$data?.searchKeyWord||'',
            hash:location.hash
        };
    })()""")
    print(f"  comp: {comp}")
    
    # 调用getData获取名称列表
    print("  调用getData...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.getData==='function')sp.getData();
    })()""")
    time.sleep(5)
    
    # 检查API
    api_logs3 = ev("window.__api_logs||[]")
    new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs2 if 'api_logs2' in dir() else api_logs)]]
    for l in new_apis3:
        url = l.get('url','')
        print(f"  API3: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                if resp.get('code') == '00000':
                    data = resp.get('data')
                    if isinstance(data, dict):
                        bd = data.get('busiData',[])
                        if isinstance(bd, list) and len(bd) > 0:
                            print(f"    busiData[0]: {json.dumps(bd[0],ensure_ascii=False)[:120]}")
                    print(f"    data: {json.dumps(data,ensure_ascii=False)[:120] if data else 'None'}")
            except: pass
    
    # 检查priseList
    pl = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return null;
        var pl=sp.$data?.priseList||[];
        return{len:pl.length,items:pl.slice(0,3).map(function(p){return JSON.stringify(p).substring(0,100)})};
    })()""")
    print(f"  priseList: len={pl.get('len',0) if pl else 0}")
    for item in (pl.get('items',[]) if pl else []):
        print(f"    {item}")
    
    # 如果有列表项，选择第一个
    if pl and pl.get('len',0) > 0:
        print("  选择第一个列表项...")
        ev("""(function(){var rows=document.querySelectorAll('.el-table__row');for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}})()""")
        time.sleep(2)
        
        # 检查nameId
        comp2 = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var sp=findComp(vm,'select-prise',0);
            return{nameId:sp?.$data?.nameId||'',priseName:sp?.$data?.priseName||''};
        })()""")
        print(f"  comp2: {comp2}")
        
        if comp2 and comp2.get('nameId'):
            nid = comp2['nameId']
            print(f"  ✅ nameId={nid}")
            
            # 调用startSheli
            ev(f"""(function(){{
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}});
            }})()""")
            time.sleep(8)
            
            # 检查flow路由
            routes = ev("""(function(){
                var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
                function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
                var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});
                return{total:all.length,flow:flow};
            })()""")
            print(f"  flow routes: {routes.get('flow',[])}")
            
            # 导航到表单
            if routes.get('flow'):
                for route in routes.get('flow',[]):
                    if 'basic-info' in route:
                        ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                        time.sleep(5)
                        break
    else:
        # 使用其他来源名称
        print("  使用其他来源名称...")
        # 点击"其他来源名称"按钮
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('其他来源')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(3)
        
        # 分析弹出的对话框
        dialog = ev("""(function(){
            var dialogs=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<dialogs.length;i++){
                if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
                    var inputs=dialogs[i].querySelectorAll('.el-input__inner,input');
                    var btns=dialogs[i].querySelectorAll('button,.el-button');
                    var inputInfo=[];
                    for(var j=0;j<inputs.length;j++){
                        inputInfo.push({idx:j,ph:inputs[j].placeholder||'',val:inputs[j].value||'',visible:inputs[j].offsetParent!==null});
                    }
                    var btnInfo=[];
                    for(var j=0;j<btns.length;j++){
                        btnInfo.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,20)||''});
                    }
                    return{found:true,inputInfo:inputInfo,btnInfo:btnInfo};
                }
            }
            return{found:false};
        })()""")
        print(f"  dialog: {dialog}")
        
        if dialog and dialog.get('found'):
            # 填写对话框
            for inp in dialog.get('inputInfo',[]):
                ph = inp.get('ph','')
                idx = inp.get('idx',0)
                val = None
                if '名称' in ph: val = '广西智信数据科技有限公司'
                elif '单号' in ph or '保留' in ph: val = 'GX2024001'
                if val:
                    print(f"  填写 #{idx} ph={ph}: {val}")
                    ev(f"""(function(){{
                        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
                        for(var i=0;i<dialogs.length;i++){{
                            if(dialogs[i].offsetParent!==null){{
                                var inputs=dialogs[i].querySelectorAll('.el-input__inner,input');
                                var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                                s.call(inputs[{idx}],'{val}');
                                inputs[{idx}].dispatchEvent(new Event('input',{{bubbles:true}}));
                                inputs[{idx}].dispatchEvent(new Event('change',{{bubbles:true}}));
                                return;
                            }}
                        }}
                    }})()""")
            time.sleep(1)
            
            # 点击确定
            for btn in dialog.get('btnInfo',[]):
                t = btn.get('text','')
                idx = btn.get('idx',0)
                if '确定' in t or '确认' in t:
                    print(f"  点击对话框按钮: {t}")
                    ev(f"""(function(){{
                        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
                        for(var i=0;i<dialogs.length;i++){{
                            if(dialogs[i].offsetParent!==null){{
                                var btns=dialogs[i].querySelectorAll('button,.el-button');
                                if(btns[{idx}])btns[{idx}].click();
                                return;
                            }}
                        }}
                    }})()""")
                    time.sleep(3)
                    break
            
            # 检查API
            api_logs4 = ev("window.__api_logs||[]")
            new_apis4 = [l for l in (api_logs4 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs3 or [])]]
            for l in new_apis4:
                url = l.get('url','')
                print(f"  API4: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
                if l.get('status') == 200:
                    try:
                        resp = json.loads(l.get('response','{}'))
                        print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:100]}")
                    except: pass
            
            # 检查isOther和form
            comp3 = ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(!sp)return null;
                return{isOther:sp.$data?.isOther||false,nameId:sp.$data?.nameId||'',form:JSON.stringify(sp.$data?.form)?.substring(0,200)||'',priseListLen:sp.$data?.priseList?.length||0};
            })()""")
            print(f"  comp3: {comp3}")
            
            # 如果isOther=true，填写表单并提交
            if comp3 and comp3.get('isOther'):
                # 填写表单
                ev("""(function(){
                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
                    for(var i=0;i<inputs.length;i++){
                        var ph=inputs[i].placeholder||'';
                        if(ph.includes('企业名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
                        if(ph.includes('保留单号')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
                    }
                })()""")
                ev("""(function(){
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                    var sp=findComp(vm,'select-prise',0);
                    if(sp&&sp.$data?.form){sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');sp.$set(sp.$data.form,'numbers','GX2024001');sp.$forceUpdate()}
                })()""")
                time.sleep(1)
                
                # 找提交按钮
                btns = ev("""(function(){var btns=document.querySelectorAll('button,.el-button');var r=[];for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||''})}return r})()""")
                print(f"  按钮: {btns}")
                
                for btn in (btns or []):
                    t = btn.get('text','')
                    idx = btn.get('idx',0)
                    if any(kw in t for kw in ['确定','确认','选择','提交','保存','下一步']):
                        print(f"  点击: {t}")
                        ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
                        time.sleep(3)
                        
                        # 检查API
                        api_logs5 = ev("window.__api_logs||[]")
                        new_apis5 = [l for l in (api_logs5 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs4 or [])]]
                        for l in new_apis5:
                            url = l.get('url','')
                            print(f"  API5: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
                            if l.get('status') == 200:
                                try:
                                    resp = json.loads(l.get('response','{}'))
                                    print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:100]}")
                                except: pass
                        
                        # 检查nameId
                        comp4 = ev("""(function(){
                            var app=document.getElementById('app');var vm=app?.__vue__;
                            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                            var sp=findComp(vm,'select-prise',0);
                            return{nameId:sp?.$data?.nameId||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
                        })()""")
                        print(f"  comp4: {comp4}")
                        
                        if comp4 and comp4.get('nameId'):
                            nid = comp4['nameId']
                            print(f"  ✅ nameId={nid}")
                            # 调用startSheli
                            ev(f"""(function(){{
                                var app=document.getElementById('app');var vm=app?.__vue__;
                                function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                                var sp=findComp(vm,'select-prise',0);
                                if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}});
                            }})()""")
                            time.sleep(8)
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
