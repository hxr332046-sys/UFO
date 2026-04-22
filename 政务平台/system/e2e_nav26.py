#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调用getDataInfo → validateNameAndSerialNum → 获取dataInfo/nameId → startSheli → flow路由"""
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

# 确保在select-prise
page = ev("({hash:location.hash})")
if not page or 'select-prise' not in page.get('hash',''):
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(5)
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var wn=findComp(vm,'without-name',0);if(wn&&typeof wn.toSelectName==='function')wn.toSelectName()})()""")
    time.sleep(3)

# Step 1: 安装XHR拦截器
print("Step 1: 安装XHR拦截器")
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

# Step 2: 切换isOther，填写表单
print("\nStep 2: 填写其他来源名称表单")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(sp){
        if(!sp.$data?.isOther){
            if(typeof sp.toOther==='function')sp.toOther();
            else sp.$set(sp.$data,'isOther',true);
        }
        sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');
        sp.$set(sp.$data.form,'numbers','GX2024001');
        sp.$forceUpdate();
    }
})()""")
time.sleep(1)

# 同时填写DOM
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

# Step 3: 直接调用getDataInfo（绕过el-form验证）
print("\nStep 3: 调用getDataInfo")
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    
    // 直接调用getDataInfo
    if(typeof sp.getDataInfo==='function'){
        try{
            var r=sp.getDataInfo();
            if(r&&typeof r.then==='function'){
                r.then(function(resp){
                    window.__getDataInfo_result={code:resp?.code||'',data:JSON.stringify(resp?.data)?.substring(0,500)||'',msg:resp?.msg||''};
                }).catch(function(e){
                    window.__getDataInfo_result={error:e.message||'unknown'};
                });
            }
            return{called:true,isPromise:!!(r&&typeof r.then==='function')};
        }catch(e){
            return{error:e.message};
        }
    }
    return{error:'no_method'};
})()""")
print(f"  result: {result}")
time.sleep(5)

# 检查API调用
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    if l.get('status') == 200:
        try:
            resp = json.loads(l.get('response','{}'))
            print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:50]}")
            data = resp.get('data')
            if data:
                print(f"    data: {json.dumps(data,ensure_ascii=False)[:200]}")
        except: pass

# 检查getDataInfo结果
get_result = ev("window.__getDataInfo_result||null")
print(f"  getDataInfo_result: {get_result}")

# Step 4: 检查dataInfo
print("\nStep 4: 检查dataInfo")
dataInfo = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return null;
    return{
        dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,500)||'',
        nameId:sp.$data?.dataInfo?.nameId||sp.$data?.dataInfo?.nId||sp.$data?.dataInfo?.id||'',
        isSearch:sp.$data?.isSearch||false
    };
})()""")
print(f"  dataInfo: {dataInfo.get('dataInfo','') if dataInfo else 'None'}")
print(f"  nameId: {dataInfo.get('nameId','') if dataInfo else ''}")
print(f"  isSearch: {dataInfo.get('isSearch','') if dataInfo else ''}")

# Step 5: 如果有nameId，调用startSheli
nid = None
if dataInfo and dataInfo.get('nameId'):
    nid = dataInfo['nameId']
    print(f"\nStep 5: ✅ nameId={nid}，调用startSheli")
else:
    # 尝试从dataInfo JSON中提取
    di_str = dataInfo.get('dataInfo','') if dataInfo else ''
    if di_str and di_str != '{}':
        try:
            di = json.loads(di_str)
            nid = di.get('nameId') or di.get('nId') or di.get('id') or ''
            if nid:
                print(f"\nStep 5: ✅ 从dataInfo提取nameId={nid}")
        except: pass
    
    if not nid:
        # 也尝试从API响应中提取
        print("\nStep 5: 尝试从API响应提取nameId")
        for l in (api_logs or []):
            if 'validateNameAndSerialNum' in l.get('url','') and l.get('status') == 200:
                try:
                    resp = json.loads(l.get('response','{}'))
                    if resp.get('code') == '00000':
                        bd = resp.get('data',{}).get('busiData',{})
                        if isinstance(bd, dict):
                            nid = bd.get('nameId') or bd.get('nId') or bd.get('id') or ''
                            print(f"  从API提取: nameId={nid}")
                            if nid: break
                except: pass

if nid:
    print(f"  调用startSheli nameId={nid}")
    ev(f"""(function(){{
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}',entType:'4540'}});
    }})()""")
    time.sleep(8)
    
    # 检查API
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis:
        url = l.get('url','')
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:100]}")
            except: pass
    
    # 检查flow路由
    routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
    print(f"  flow routes: {routes.get('flow',[])}")
    
    if routes.get('flow'):
        for route in routes.get('flow',[]):
            if 'basic-info' in route:
                print(f"  导航: {route}")
                ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                time.sleep(5)
                break
else:
    print("\n  ❌ 无法获取nameId")
    
    # 尝试直接用dataInfo调用startSheli
    print("  尝试直接用dataInfo调用startSheli...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.startSheli==='function'){
            // 用dataInfo作为参数
            var di=sp.$data?.dataInfo||{};
            sp.startSheli({nameId:di.nameId||di.nId||di.id||'unknown',entType:'1100'});
        }
    })()""")
    time.sleep(5)
    
    routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
    print(f"  flow routes: {routes.get('flow',[])}")

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
