#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""尝试fromType=0路径(queryNameInfoList) + toNotName路径 → 找到可用的nameId"""
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

# 回首页
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/page')})()""")
time.sleep(3)

# 导航到without-name
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

page = ev("({hash:location.hash})")
print(f"当前: hash={page.get('hash','') if page else '?'}")

# Step 1: 分析without-name组件
print("\nStep 1: 分析without-name组件")
wn_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(!wn)return{error:'no_comp'};
    var methods=wn.$options?.methods||{};
    var srcs={};
    for(var m in methods){srcs[m]=methods[m].toString().substring(0,400)}
    return{
        compName:wn.$options?.name||'',
        methods:Object.keys(methods),
        srcs:srcs,
        dataKeys:Object.keys(wn.$data||{}),
        fromType:wn.$data?.fromType||'',
        entType:wn.$data?.entType||wn.$route?.query?.entType||''
    };
})()""")
print(f"  compName: {wn_info.get('compName','') if wn_info else ''}")
print(f"  methods: {wn_info.get('methods',[]) if wn_info else []}")
print(f"  fromType: {wn_info.get('fromType','') if wn_info else ''}")
print(f"  entType: {wn_info.get('entType','') if wn_info else ''}")
for m, src in (wn_info.get('srcs',{}) or {}).items():
    print(f"  {m}: {src[:300]}")

# Step 2: 尝试toNotName路径
print("\nStep 2: 尝试toNotName路径")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(wn&&typeof wn.toNotName==='function')wn.toNotName();
})()""")
time.sleep(5)

page2 = ev("""(function(){return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body?.innerText||'').substring(0,150)}})()""")
print(f"  hash={page2.get('hash','') if page2 else '?'} forms={page2.get('formCount',0) if page2 else 0}")
print(f"  text={page2.get('text','')[:80] if page2 else ''}")

# Step 3: 如果toNotName导航到了新页面，分析
if page2 and page2.get('hash','') != page.get('hash',''):
    print("\nStep 3: 分析新页面")
    # 找页面组件
    comp = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findActive(vm,d){if(d>10)return null;
            if(vm.$options?.name&&vm.$el?.offsetParent!==null&&vm.$options?.name!=='layout'&&vm.$options?.name!=='index'){
                return{compName:vm.$options?.name,methods:Object.keys(vm.$options?.methods||{}).slice(0,15),dataKeys:Object.keys(vm.$data||{}).slice(0,15)};
            }
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findActive(vm.$children[i],d+1);if(r)return r}return null}
        return findActive(vm,0);
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
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,500)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 5: 回到without-name，尝试设置fromType=0然后调用initData
print("\nStep 5: 回到without-name设置fromType=0")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/without-name?entType=1100')})()""")
time.sleep(3)

# 设置fromType=0并转到select-prise
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(wn){
        wn.$set(wn.$data,'fromType','0');
        if(typeof wn.toSelectName==='function')wn.toSelectName();
    }
})()""")
time.sleep(3)

# 设置select-prise的fromType=0
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(sp){
        sp.$set(sp.$data,'fromType','0');
        sp.$set(sp.$data,'searchKeyWord','广西智信');
        sp.$forceUpdate();
    }
})()""")
time.sleep(1)

# 调用initData (会调用queryNameInfoList)
print("  调用initData...")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(sp&&typeof sp.initData==='function')sp.initData();
})()""")
time.sleep(5)

# 检查API
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'queryNameInfoList' in url or 'name' in url.lower():
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:50]}")
                data = resp.get('data')
                if data:
                    bd = data.get('busiData',{}) if isinstance(data, dict) else data
                    if isinstance(bd, dict):
                        records = bd.get('records',[])
                        total = bd.get('total',0)
                        print(f"    total={total} records={len(records)}")
                        for r in records[:3]:
                            print(f"      {json.dumps(r,ensure_ascii=False)[:120]}")
                    elif isinstance(bd, list):
                        print(f"    list len={len(bd)}")
                        for r in bd[:3]:
                            print(f"      {json.dumps(r,ensure_ascii=False)[:120]}")
            except: pass

# 检查priseList
pl = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(!sp)return null;var pl=sp.$data?.priseList||[];return{len:pl.length,fromType:sp.$data?.fromType||'',items:pl.slice(0,5).map(function(p){return JSON.stringify(p).substring(0,120)})}})()""")
print(f"  priseList: len={pl.get('len',0) if pl else 0} fromType={pl.get('fromType','') if pl else ''}")
for item in (pl.get('items',[]) if pl else []):
    print(f"    {item}")

# Step 6: 如果有列表项，选择并调用startSheli
if pl and pl.get('len',0) > 0:
    print("\nStep 6: 选择列表项")
    ev("""(function(){var rows=document.querySelectorAll('.el-table__row');for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}})()""")
    time.sleep(2)
    
    comp = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);return{nameId:sp?.$data?.nameId||'',priseName:sp?.$data?.priseName||'',priseNo:sp?.$data?.priseNo||''}})()""")
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
    # Step 6b: 尝试fromType=1
    print("\nStep 6b: 尝试fromType=1")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp){
            sp.$set(sp.$data,'fromType','1');
            sp.$set(sp.$data,'searchKeyWord','');
            sp.$forceUpdate();
        }
    })()""")
    time.sleep(1)
    
    ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(sp&&typeof sp.initData==='function')sp.initData()})()""")
    time.sleep(5)
    
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis:
        url = l.get('url','')
        if 'name' in url.lower() or 'query' in url.lower():
            print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
            if l.get('status') == 200:
                try:
                    resp = json.loads(l.get('response','{}'))
                    data = resp.get('data')
                    if data:
                        bd = data.get('busiData',{}) if isinstance(data, dict) else data
                        if isinstance(bd, dict):
                            records = bd.get('records',[])
                            print(f"    total={bd.get('total',0)} records={len(records)}")
                            for r in records[:3]:
                                print(f"      {json.dumps(r,ensure_ascii=False)[:120]}")
                except: pass
    
    pl2 = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);if(!sp)return null;var pl=sp.$data?.priseList||[];return{len:pl.length,fromType:sp.$data?.fromType||''}})()""")
    print(f"  priseList2: len={pl2.get('len',0) if pl2 else 0} fromType={pl2.get('fromType','') if pl2 else ''}")

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
