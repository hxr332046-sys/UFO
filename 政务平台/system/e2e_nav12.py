#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 找设立登记卡片的父Vue组件 → 触发其click handler → 跟踪API获取nameId"""
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

# Step 1: 回到首页
print("Step 1: 回首页")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/page')})()""")
time.sleep(3)

# Step 2: 深入分析设立登记卡片的Vue组件链
print("\nStep 2: 分析设立登记卡片Vue组件链")
card_vue = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
            // 找到设立登记文本节点，向上遍历找Vue组件
            var el=allEls[i];
            var chain=[];
            var current=el;
            for(var d=0;d<15&&current;d++){
                var comp=current.__vue__;
                if(comp){
                    var methods=Object.keys(comp.$options?.methods||{});
                    var clickMethods=methods.filter(function(m){return m.toLowerCase().includes('click')||m.toLowerCase().includes('handle')||m.toLowerCase().includes('go')||m.toLowerCase().includes('to')||m.toLowerCase().includes('nav')});
                    var compName=comp.$options?.name||'';
                    var vnode=comp.$vnode;
                    var on=Object.keys(Object.assign({},vnode?.data?.on||{},vnode?.data?.nativeOn||{}));
                    chain.push({depth:d,compName:compName,tag:current.tagName,class:(current.className||'').substring(0,30),clickMethods:clickMethods,onKeys:on,dataKeys:Object.keys(comp.$data||{}).slice(0,10)});
                }
                current=current.parentElement;
            }
            return{found:true,chain:chain};
        }
    }
    return{found:false};
})()""")
print(f"  found: {card_vue.get('found') if card_vue else '?'}")
for c in (card_vue.get('chain',[]) if card_vue else []):
    print(f"  d={c.get('depth')}: {c.get('compName','')} tag={c.get('tag','')} class={c.get('class','')}")
    print(f"    clickMethods={c.get('clickMethods',[])} onKeys={c.get('onKeys',[])} dataKeys={c.get('dataKeys',[])}")

# Step 3: 找到有click handler的组件并触发
print("\nStep 3: 触发Vue click handler")
trigger_result = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
            var el=allEls[i];
            var current=el;
            for(var d=0;d<15&&current;d++){
                var comp=current.__vue__;
                if(comp){
                    var vnode=comp.$vnode;
                    var on=Object.assign({},vnode?.data?.on||{},vnode?.data?.nativeOn||{});
                    // 找click handler
                    if(on.click){
                        if(typeof on.click==='function'){
                            on.click(new MouseEvent('click'));
                            return{triggered:'on.click',depth:d,compName:comp.$options?.name||''};
                        }else if(Array.isArray(on.click)){
                            for(var j=0;j<on.click.length;j++){
                                try{on.click[j](new MouseEvent('click'))}catch(e){}
                            }
                            return{triggered:'on.click[]',depth:d,compName:comp.$options?.name||''};
                        }
                    }
                    // 也尝试$emit
                    comp.$emit('click');
                    comp.$emit('nativeClick');
                    
                    // 尝试组件方法
                    var methods=comp.$options?.methods||{};
                    for(var m in methods){
                        if(m.toLowerCase().includes('click')||m.toLowerCase().includes('handle')||m==='goTo'||m==='navigate'){
                            try{
                                methods[m].call(comp,{name:'设立登记',code:'07',busiType:'07'});
                                return{triggered:'method:'+m,depth:d,compName:comp.$options?.name||''};
                            }catch(e){}
                        }
                    }
                }
                current=current.parentElement;
            }
            return{error:'no_handler_found'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  trigger_result: {trigger_result}")
time.sleep(3)

# Step 4: 检查页面变化
page = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,100)})")
print(f"\nStep 4: hash={page.get('hash','') if page else '?'} text={page.get('text','')[:50] if page else ''}")

# Step 5: 如果仍在首页，尝试通过sidebar菜单导航
if page and page.get('hash','') == '#/index/page':
    print("\nStep 5: 尝试sidebar菜单")
    
    # 找sidebar中的菜单项
    sidebar = ev("""(function(){
        var sidebar=document.querySelector('[class*="sidebar"],[class*="menu"],[class*="nav"],[class*="aside"]');
        if(!sidebar)return{error:'no_sidebar'};
        var items=sidebar.querySelectorAll('[class*="item"],li,a,span,div');
        var r=[];
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.length>2&&t.length<20){
                var comp=items[i].__vue__;
                r.push({idx:i,text:t,hasVue:!!comp,compName:comp?comp.$options?.name||'':'',tag:items[i].tagName});
            }
        }
        return{found:true,items:r.slice(0,20)};
    })()""")
    print(f"  sidebar: found={sidebar.get('found') if sidebar else '?'} items={len(sidebar.get('items',[])) if sidebar else 0}")
    for item in (sidebar.get('items',[]) if sidebar else []):
        if any(kw in item.get('text','') for kw in ['经营','企业','登记','开办','设立']):
            print(f"    [{item.get('idx')}] {item.get('text','')} vue={item.get('hasVue')} comp={item.get('compName','')}")
    
    # 尝试通过router导航到企业开办专区
    print("\n  尝试router导航到企业开办专区")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    
    page2 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,100)})")
    print(f"  hash={page2.get('hash','') if page2 else '?'}")
    
    if page2 and 'enterprise' in page2.get('hash',''):
        print("  在企业开办专区！")
        
        # 安装XHR拦截器
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
        
        # 点击开始办理
        print("  点击开始办理")
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(5)
        
        # 检查API调用
        api_logs = ev("window.__api_logs||[]")
        for l in (api_logs or []):
            print(f"  API: {l.get('method','')} {l.get('url','')} status={l.get('status')}")
        
        page3 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  hash={page3.get('hash','') if page3 else '?'} forms={page3.get('formCount',0) if page3 else 0}")
        
        if page3 and ('without-name' in page3.get('hash','') or 'select-prise' in page3.get('hash','')):
            print("  在名称选择页！")
            
            # 调用toOther
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
                // 也设置form数据
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&sp.$data?.form){sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');sp.$set(sp.$data.form,'numbers','GX2024001');sp.$forceUpdate()}
            })()""")
            time.sleep(1)
            
            # 点击"选择已有名称"按钮
            print("  点击选择已有名称")
            ev("""(function(){
                var btns=document.querySelectorAll('button,.el-button');
                for(var i=0;i<btns.length;i++){
                    var t=btns[i].textContent?.trim()||'';
                    if(t.includes('选择已有名称')&&btns[i].offsetParent!==null){btns[i].click();return}
                }
            })()""")
            time.sleep(3)
            
            # 检查API
            api_logs2 = ev("window.__api_logs||[]")
            new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
            for l in new_apis:
                print(f"  NEW API: {l.get('method','')} {l.get('url','')} status={l.get('status')} resp={l.get('response','')[:80]}")
            
            # 检查nameId
            comp = ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(!sp)return{error:'no_comp'};
                return{nameId:sp.$data?.nameId||'',dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,200)||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
            })()""")
            print(f"  comp: nameId={comp.get('nameId','') if comp else ''}")
            
            if comp and comp.get('nameId'):
                nid = comp['nameId']
                print(f"  ✅ 获取nameId={nid}，调用startSheli")
                ev(f"""(function(){{
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                    var sp=findComp(vm,'select-prise',0);
                    if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}'}});
                }})()""")
                time.sleep(5)
                fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
                print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
            else:
                # 检查priseList
                print("  检查priseList...")
                ev("""(function(){
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                    var sp=findComp(vm,'select-prise',0);
                    if(sp&&typeof sp.getData==='function')sp.getData();
                })()""")
                time.sleep(3)
                
                priseList = ev("""(function(){
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                    var sp=findComp(vm,'select-prise',0);
                    if(!sp)return null;
                    var pl=sp.$data?.priseList||[];
                    return{len:pl.length,items:pl.slice(0,3).map(function(p){return JSON.stringify(p).substring(0,100)})};
                })()""")
                print(f"  priseList: len={priseList.get('len',0) if priseList else 0} items={priseList.get('items',[]) if priseList else []}")
                
                # 如果有列表项，点击第一个
                if priseList and priseList.get('len',0) > 0:
                    print("  点击第一个列表项...")
                    ev("""(function(){
                        var rows=document.querySelectorAll('.el-table__row,[class*="row"],[class*="list-item"]');
                        for(var i=0;i<rows.length;i++){
                            if(rows[i].offsetParent!==null){
                                rows[i].click();
                                return;
                            }
                        }
                    })()""")
                    time.sleep(2)
                    
                    # 再检查nameId
                    comp2 = ev("""(function(){
                        var app=document.getElementById('app');var vm=app?.__vue__;
                        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                        var sp=findComp(vm,'select-prise',0);
                        return{nameId:sp?.$data?.nameId||'',hash:location.hash};
                    })()""")
                    print(f"  comp2: nameId={comp2.get('nameId','') if comp2 else ''}")
                    
                    if comp2 and comp2.get('nameId'):
                        nid = comp2['nameId']
                        ev(f"""(function(){{var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}var sp=findComp(vm,'select-prise',0);if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}'}})}})()""")
                        time.sleep(5)

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 检查动态路由
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')||r.includes('declaration')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("420.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("420.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0,"flowRoutes":routes.get('flow',[])})

ws.close()
print("✅ 完成")
