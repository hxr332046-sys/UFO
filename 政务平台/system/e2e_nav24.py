#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找到busiType=07的卡片 → 调用jumpPage → 自然导航到表单"""
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

# Step 1: 遍历cardlist找busiType=07的卡片
print("Step 1: 找busiType=07的卡片")
card = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
            var current=allEls[i];
            for(var d=0;d<20&&current;d++){
                var comp=current.__vue__;
                if(comp&&typeof comp.jumpPage==='function'){
                    // cardlist在props中
                    var cl=comp.$props?.cardlist||comp.$data?.cardlist||[];
                    // 可能是树形结构，递归搜索
                    function findCard(items){
                        if(!items)return null;
                        for(var i=0;i<items.length;i++){
                            var item=items[i];
                            var routeStr=item.route||'';
                            if(routeStr.includes('"07"')||routeStr.includes('busiType')&&routeStr.includes('07')){
                                return{item:JSON.stringify(item).substring(0,500),idx:i,route:routeStr.substring(0,300)};
                            }
                            // 检查children
                            if(item.childrenList||item.children){
                                var r=findCard(item.childrenList||item.children);
                                if(r)return r;
                            }
                        }
                        return null;
                    }
                    var found=findCard(cl);
                    if(!found){
                        // 也搜索所有items
                        return{error:'not_in_cardlist',cardlistLen:cl.length,cardlistSample:cl.slice(0,3).map(function(c){return JSON.stringify(c).substring(0,80)})};
                    }
                    return found;
                }
                current=current.parentElement;
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  result: {card}")

# Step 2: 如果没找到，列出所有卡片的route
if not card or card.get('error'):
    print("\nStep 2: 列出所有卡片route")
    all_cards = ev("""(function(){
        var allEls=document.querySelectorAll('*');
        for(var i=0;i<allEls.length;i++){
            var t=allEls[i].textContent?.trim()||'';
            if(t.includes('设立登记')&&t.length<30&&allEls[i].offsetParent!==null){
                var current=allEls[i];
                for(var d=0;d<20&&current;d++){
                    var comp=current.__vue__;
                    if(comp&&typeof comp.jumpPage==='function'){
                        var cl=comp.$props?.cardlist||comp.$data?.cardlist||[];
                        function flatten(items,prefix){
                            var r=[];
                            if(!items)return r;
                            for(var i=0;i<items.length;i++){
                                var item=items[i];
                                r.push({prefix:prefix,idx:i,name:item.name||item.busiName||item.remark||'',route:(item.route||'').substring(0,100),id:item.id||''});
                                if(item.childrenList||item.children){
                                    r=r.concat(flatten(item.childrenList||item.children,prefix+i+'.'));
                                }
                            }
                            return r;
                        }
                        return flatten(cl,'');
                    }
                    current=current.parentElement;
                }
            }
        }
        return[];
    })()""")
    for c in (all_cards or []):
        route = c.get('route','')
        name = c.get('name','')
        if '07' in route or '设立' in name or '登记' in name or 'busiType' in route:
            print(f"  ✅ {c.get('prefix','')}{c.get('idx','')}: name={name} route={route}")
        # 也打印所有包含busiType的
        if 'busiType' in route:
            print(f"  BUSI: {c.get('prefix','')}{c.get('idx','')}: name={name} route={route}")

# Step 3: 直接用$router.push导航到企业开办专区（已知可行路径）
print("\nStep 3: 直接导航到企业开办专区")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)

page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

if page and 'enterprise' in page.get('hash',''):
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
                    window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,400)||'',body:self.__body?.substring(0,200)||''});
                }
            });
            return origSend.apply(this,arguments);
        };
    })()""")
    
    # 点击开始办理
    print("  点击开始办理")
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(5)
    
    page2 = ev("({hash:location.hash})")
    print(f"  hash2={page2.get('hash','') if page2 else '?'}")
    
    # 检查API
    api_logs = ev("window.__api_logs||[]")
    for l in (api_logs or []):
        url = l.get('url','')
        if 'selectModuleFlows' in url:
            print(f"  selectModuleFlows: status={l.get('status')}")
            if l.get('status') == 200:
                try:
                    resp = json.loads(l.get('response','{}'))
                    print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:200]}")
                except: pass
    
    # 在without-name/select-prise
    if page2 and ('without-name' in page2.get('hash','') or 'select-prise' in page2.get('hash','')):
        print("\n  在名称选择页")
        
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
                        print(f"    data: {json.dumps(data,ensure_ascii=False)[:200]}")
                except: pass
        
        # 检查priseList
        pl = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(!sp)return null;var pl=sp.$data?.priseList||[];return{len:pl.length,items:pl.slice(0,5).map(function(p){return JSON.stringify(p).substring(0,120)})}})()""")
        print(f"  priseList: len={pl.get('len',0) if pl else 0}")
        for item in (pl.get('items',[]) if pl else []):
            print(f"    {item}")
        
        if pl and pl.get('len',0) > 0:
            # 选择第一个
            print("  选择第一个列表项...")
            ev("""(function(){var rows=document.querySelectorAll('.el-table__row');for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}})()""")
            time.sleep(2)
            
            comp = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);return{nameId:sp?.$data?.nameId||'',priseName:sp?.$data?.priseName||''}})()""")
            print(f"  comp: {comp}")
            
            if comp and comp.get('nameId'):
                nid = comp['nameId']
                print(f"  ✅ nameId={nid}")
                ev(f"""(function(){{var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}var sp=findComp(vm,'select-prise',0);if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}})}})()""")
                time.sleep(8)
                
                routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
                print(f"  flow routes: {routes.get('flow',[])}")
                
                if routes.get('flow'):
                    for route in routes.get('flow',[]):
                        if 'basic-info' in route:
                            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                            time.sleep(5)
                            break
        else:
            # 没有priseList，使用其他来源名称
            print("  无priseList，使用其他来源名称")
            # 先分析select-prise的toOther方法
            toOther_src = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(!sp)return null;return{toOther:sp.$options?.methods?.toOther?.toString()?.substring(0,500)||'',isOther:sp.$data?.isOther||false,form:JSON.stringify(sp.$data?.form)?.substring(0,200)||'',dataKeys:Object.keys(sp.$data||{}).slice(0,20)}})()""")
            print(f"  toOther: {toOther_src.get('toOther','')[:300] if toOther_src else ''}")
            print(f"  isOther: {toOther_src.get('isOther','') if toOther_src else ''}")
            print(f"  form: {toOther_src.get('form','') if toOther_src else ''}")
            print(f"  dataKeys: {toOther_src.get('dataKeys',[]) if toOther_src else []}")
            
            # 点击"其他来源名称"按钮
            ev("""(function(){
                var btns=document.querySelectorAll('button,.el-button,[class*="btn"]');
                for(var i=0;i<btns.length;i++){
                    var t=btns[i].textContent?.trim()||'';
                    if((t.includes('其他来源')||t.includes('其他方式')||t.includes('其他名称'))&&btns[i].offsetParent!==null){
                        btns[i].click();return;
                    }
                }
                // 如果没有按钮，直接调用toOther
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&typeof sp.toOther==='function')sp.toOther();
            })()""")
            time.sleep(3)
            
            # 检查isOther
            isOther = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);return{isOther:sp?.$data?.isOther||false,formFields:Object.keys(sp?.$data?.form||{}).slice(0,10)}})()""")
            print(f"  isOther: {isOther.get('isOther','') if isOther else ''}")
            print(f"  formFields: {isOther.get('formFields',[]) if isOther else []}")
            
            if isOther and isOther.get('isOther'):
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
                
                for btn in (btns or []):
                    t = btn.get('text','')
                    idx = btn.get('idx',0)
                    if any(kw in t for kw in ['确定','确认','选择','提交','保存','下一步','选择已有名称']):
                        print(f"  点击: {t}")
                        ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
                        time.sleep(3)
                        
                        # 检查API
                        api_logs3 = ev("window.__api_logs||[]")
                        new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs2 or [])]]
                        for l in new_apis3:
                            url = l.get('url','')
                            print(f"  API3: {l.get('method','')} {url.split('?')[0]} status={l.get('status')}")
                            if l.get('status') == 200:
                                try:
                                    resp = json.loads(l.get('response','{}'))
                                    print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:150]}")
                                except: pass
                        
                        # 检查nameId
                        comp2 = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);return{nameId:sp?.$data?.nameId||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length}})()""")
                        print(f"  comp2: {comp2}")
                        
                        if comp2 and comp2.get('nameId'):
                            nid = comp2['nameId']
                            print(f"  ✅ nameId={nid}")
                            ev(f"""(function(){{var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}var sp=findComp(vm,'select-prise',0);if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'1100'}})}})()""")
                            time.sleep(8)
                            break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
print(f"  flow routes: {routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
elif routes.get('flow'):
    for route in routes.get('flow',[]):
        if 'basic-info' in route:
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(5)
            fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            if fc2 and fc2.get('formCount',0) > 10:
                print(f"✅ 表单已加载！hash={fc2.get('hash','')} forms={fc2.get('formCount',0)}")
            break

ws.close()
print("✅ 完成")
