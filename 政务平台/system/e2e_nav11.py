#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 不刷新页面，通过Vue Router回首页 → UI点击导航 → 动态路由自然注册"""
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

# Step 1: 不刷新，用Vue Router回首页
print("Step 1: Vue Router回首页")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/page')})()""")
time.sleep(3)

page = ev("({hash:location.hash,hasVue:!!document.getElementById('app')?.__vue__})")
print(f"  hash={page.get('hash','') if page else '?'} vue={page.get('hasVue') if page else '?'}")

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

# Step 3: 安装XHR拦截器监控所有API调用
print("\nStep 3: 安装XHR拦截器")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(){
        var self=this;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 点击"全部服务"中的"设立登记"
print("\nStep 4: 点击设立登记")
# 先分析首页所有可点击元素
home_items = ev("""(function(){
    var all=document.querySelectorAll('[class*="service"] [class*="item"],[class*="swiper-slide"],[class*="featured"] [class*="card"],[class*="all-service"] [class*="item"]');
    var r=[];
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.length>2&&t.length<50){
            r.push({idx:i,text:t.substring(0,30),class:(all[i].className||'').substring(0,30),tag:all[i].tagName});
        }
    }
    // 也搜索所有包含"设立登记"的元素
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null&&allEls[i].children.length<5){
            r.push({idx:1000+i,text:t.substring(0,30),class:(allEls[i].className||'').substring(0,30),tag:allEls[i].tagName,found:'direct'});
        }
    }
    return r.slice(0,20);
})()""")
print(f"  首页元素: {len(home_items or [])}")
for item in (home_items or []):
    if any(kw in item.get('text','') for kw in ['设立','登记','企业','开办']):
        print(f"    [{item.get('idx')}] {item.get('text','')} tag={item.get('tag','')}")

# 尝试点击设立登记
click_result = ev("""(function(){
    // 找Vue组件绑定click的设立登记元素
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
            var comp=allEls[i].__vue__;
            if(comp){
                // 找click handler
                var vnode=comp.$vnode;
                var on=vnode?.data?.on||{};
                var nativeOn=vnode?.data?.nativeOn||{};
                var handlers=Object.assign({},on,nativeOn);
                var handlerKeys=Object.keys(handlers);
                
                if(handlerKeys.length>0){
                    // 触发所有handler
                    for(var k in handlers){
                        if(typeof handlers[k]==='function'){
                            try{handlers[k](new Event('click'))}catch(e){}
                        }else if(handlers[k]&&handlers[k].length>0){
                            for(var j=0;j<handlers[k].length;j++){
                                try{handlers[k][j](new Event('click'))}catch(e){}
                            }
                        }
                    }
                    return{triggered:'vue_handlers',keys:handlerKeys,text:t.substring(0,20)};
                }
                
                // 如果没有v-on绑定，尝试$emit
                comp.$emit('click');
                comp.$emit('nativeClick');
                
                // 也尝试parent的handler
                var parent=comp.$parent;
                if(parent){
                    var pVnode=parent.$vnode;
                    var pOn=Object.assign({},pVnode?.data?.on||{},pVnode?.data?.nativeOn||{});
                    for(var k in pOn){
                        if(k.includes('click')){
                            try{pOn[k](new Event('click'),comp)}catch(e){}
                        }
                    }
                }
                
                return{triggered:'emit',text:t.substring(0,20)};
            }
            
            // 没有Vue组件，直接click
            allEls[i].click();
            allEls[i].dispatchEvent(new Event('click',{bubbles:true}));
            return{triggered:'dom_click',text:t.substring(0,20)};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click_result: {click_result}")
time.sleep(3)

# 检查API调用
api_logs = ev("window.__api_logs||[]")
for log_item in (api_logs or []):
    print(f"  API: {log_item.get('method','')} {log_item.get('url','')} status={log_item.get('status')}")

# Step 5: 检查页面变化
page2 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,100)})")
print(f"\nStep 5: hash={page2.get('hash','') if page2 else '?'} text={page2.get('text','')[:50] if page2 else ''}")

# Step 6: 如果到了企业开办专区或名称选择页，继续导航
if page2 and ('enterprise' in page2.get('hash','') or 'without-name' in page2.get('hash','') or 'select' in page2.get('hash','')):
    print("\nStep 6: 继续导航")
    
    if 'enterprise' in page2.get('hash',''):
        # 点击开始办理
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(3)
    
    page3 = ev("({hash:location.hash})")
    print(f"  hash={page3.get('hash','') if page3 else '?'}")
    
    if page3 and ('without-name' in page3.get('hash','') or 'select-prise' in page3.get('hash','')):
        # 在名称选择页
        print("  在名称选择页")
        
        # 设置isOther=true
        ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var sp=findComp(vm,'select-prise',0)||findComp(vm,'without-name',0);
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
        })()""")
        time.sleep(1)
        
        # 设置form数据
        ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var sp=findComp(vm,'select-prise',0);
            if(sp&&sp.$data?.form){
                sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');
                sp.$set(sp.$data.form,'numbers','GX2024001');
                sp.$forceUpdate();
            }
        })()""")
        time.sleep(1)
        
        # 点击"选择已有名称"按钮（这是提交按钮）
        print("  点击选择已有名称...")
        ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                var t=btns[i].textContent?.trim()||'';
                if(t.includes('选择已有名称')&&btns[i].offsetParent!==null){
                    btns[i].click();return;
                }
            }
        })()""")
        time.sleep(3)
        
        # 检查API调用
        api_logs2 = ev("window.__api_logs||[]")
        new_logs = [l for l in (api_logs2 or []) if l not in (api_logs or [])]
        for log_item in new_logs:
            print(f"  NEW API: {log_item.get('method','')} {log_item.get('url','')} status={log_item.get('status')} resp={log_item.get('response','')[:80]}")
        
        # 检查nameId
        comp = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var sp=findComp(vm,'select-prise',0);
            if(!sp)return{error:'no_comp'};
            return{nameId:sp.$data?.nameId||'',dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,200)||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
        })()""")
        print(f"  comp: nameId={comp.get('nameId','') if comp else ''} hash={comp.get('hash','') if comp else ''}")
        
        # 如果有nameId，调用startSheli
        if comp and comp.get('nameId'):
            nid = comp['nameId']
            print(f"  调用startSheli nameId={nid}")
            ev(f"""(function(){{
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}'}});
            }})()""")
            time.sleep(5)
        else:
            # 尝试getHandleBusiness
            print("  尝试getHandleBusiness...")
            ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness({entType:'1100',nameId:''});
            })()""")
            time.sleep(3)

# Step 7: 检查动态路由
print("\nStep 7: 检查动态路由")
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')||r.includes('declaration')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

# 如果有flow路由，导航
if routes.get('flow'):
    for route in routes.get('flow',[]):
        if 'basic-info' in route or 'base' in route:
            print(f"  导航到: {route}")
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(5)
            break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    ev("localStorage.setItem('e2e_form_loaded','true')")
    log("410.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("410.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0,"flowRoutes":routes.get('flow',[])})

ws.close()
print("✅ 完成")
