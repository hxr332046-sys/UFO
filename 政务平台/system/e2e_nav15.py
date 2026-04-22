#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 分析selectModuleFlows API → 找nameId API → 注册动态路由 → 表单"""
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

# Step 1: 调用selectModuleFlows API分析响应
print("Step 1: 调用selectModuleFlows API")
flows = ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/register/guide/home/selectModuleFlows?code=1100',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{
        xhr.send();
        if(xhr.status===200){
            var resp=JSON.parse(xhr.responseText);
            return{status:xhr.status,code:resp.code,data:JSON.stringify(resp.data)?.substring(0,800)||'',msg:resp.msg||''};
        }
        return{status:xhr.status};
    }catch(e){return{error:e.message}}
})()""")
print(f"  flows: code={flows.get('code','') if flows else '?'}")
if flows and flows.get('data'):
    print(f"  data: {flows.get('data','')[:500]}")

# Step 2: 找名称相关API - 搜索所有可能的endpoints
print("\nStep 2: 搜索名称API")
name_apis = ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var apis=[
        '/icpsp-api/v4/pc/register/guide/home/selectModuleFlows?code=1100',
        '/icpsp-api/v4/pc/register/name/getNamelist?entType=1100',
        '/icpsp-api/v4/pc/register/name/selectNameList?entType=1100',
        '/icpsp-api/v4/pc/register/namenotice/getList?entType=1100',
        '/icpsp-api/v4/pc/register/namenotice/getNamelist?entType=1100',
        '/icpsp-api/v4/pc/register/namenotice/selectNameList?entType=1100',
        '/icpsp-api/v4/pc/register/guide/name/getList?entType=1100',
        '/icpsp-api/v4/pc/register/guide/namenotice/getList?entType=1100',
        '/icpsp-api/v4/pc/flow/name/getList?entType=1100',
        '/icpsp-api/v4/pc/flow/namenotice/getList?entType=1100',
        '/icpsp-api/v4/pc/flow/base/getFlowInfo?entType=1100',
        '/icpsp-api/v4/pc/flow/base/initFlow?entType=1100',
    ];
    var results=[];
    for(var i=0;i<apis.length;i++){
        var xhr=new XMLHttpRequest();
        xhr.open('GET',apis[i],false);
        xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
        try{
            xhr.send();
            var resp=null;try{resp=JSON.parse(xhr.responseText)}catch(e){}
            results.push({url:apis[i],status:xhr.status,code:resp?.code||'',dataLen:JSON.stringify(resp?.data)?.length||0,dataSample:JSON.stringify(resp?.data)?.substring(0,100)||''});
        }catch(e){results.push({url:apis[i],error:e.message})}
    }
    return results;
})()""")
for r in (name_apis or []):
    if r.get('status') != 404:
        print(f"  ✅ {r.get('url','').split('/').pop()} status={r.get('status')} code={r.get('code','')} data={r.get('dataSample','')[:60]}")
    else:
        print(f"  ❌ {r.get('url','').split('/').pop()} 404")

# Step 3: 导航到without-name页面，安装XHR拦截器，观察自然交互的API调用
print("\nStep 3: 导航到without-name并监控API")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

# 安装XHR拦截器
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

page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

# Step 4: 在without-name/select-prise页面，分析组件并尝试自然交互
print("\nStep 4: 分析名称选择页组件")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
    if(!wn)return{error:'no_comp',hash:location.hash};
    var methods=Object.keys(wn.$options?.methods||{});
    // 获取关键方法源码
    var srcs={};
    for(var i=0;i<methods.length;i++){
        var m=methods[i];
        if(m.includes('start')||m.includes('handle')||m.includes('get')||m.includes('save')||m.includes('submit')||m.includes('search')){
            srcs[m]=wn.$options.methods[m].toString().substring(0,300);
        }
    }
    return{
        compName:wn.$options?.name||'',
        methods:methods,
        srcs:srcs,
        dataKeys:Object.keys(wn.$data||{}).slice(0,15),
        priseListLen:wn.$data?.priseList?.length||0,
        busiDataListLen:wn.$data?.busiDataList?.length||0,
        nameId:wn.$data?.nameId||'',
        hash:location.hash
    };
})()""")
print(f"  compName: {comp.get('compName','') if comp else '?'}")
print(f"  methods: {comp.get('methods',[]) if comp else []}")
print(f"  priseList: {comp.get('priseListLen',0) if comp else 0}")
print(f"  nameId: {comp.get('nameId','') if comp else ''}")

# 打印关键方法源码
for m, src in (comp.get('srcs',{}) or {}).items():
    print(f"\n  {m}: {src[:200]}")

# Step 5: 调用getData获取名称列表
print("\nStep 5: 调用getData")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
    if(wn&&typeof wn.getData==='function')wn.getData();
})()""")
time.sleep(3)

# 检查API调用
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'getUserInfo' not in url and 'getCacheCreateTime' not in url:
        print(f"  API: {l.get('method','')} {url.split('?')[0]} status={l.get('status')} resp={l.get('response','')[:100]}")

# 检查列表
list_data = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
    if(!wn)return null;
    var pl=wn.$data?.priseList||wn.$data?.busiDataList||[];
    return{len:pl.length,items:pl.slice(0,3).map(function(p){return JSON.stringify(p).substring(0,100)})};
})()""")
print(f"  list: len={list_data.get('len',0) if list_data else 0} items={list_data.get('items',[]) if list_data else []}")

# Step 6: 如果有列表项，选择并调用startSheli
if list_data and list_data.get('len',0) > 0:
    print("\nStep 6: 选择列表项并调用startSheli")
    # 点击第一行
    ev("""(function(){
        var rows=document.querySelectorAll('.el-table__row');
        for(var i=0;i<rows.length;i++){if(rows[i].offsetParent!==null){rows[i].click();return}}
    })()""")
    time.sleep(2)
    
    # 检查nameId
    comp2 = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
        return{nameId:wn?.$data?.nameId||'',hash:location.hash};
    })()""")
    print(f"  nameId={comp2.get('nameId','') if comp2 else ''}")
    
    if comp2 and comp2.get('nameId'):
        nid = comp2['nameId']
        print(f"  ✅ 调用startSheli nameId={nid}")
        ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
            if(wn&&typeof wn.startSheli==='function')wn.startSheli({{nameId:'{nid}'}});
        }})()""")
        time.sleep(5)
        
        fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
    else:
        # 没有nameId，尝试点击"开始办理"按钮
        print("  点击下一步/开始办理按钮...")
        ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                var t=btns[i].textContent?.trim()||'';
                if((t.includes('下一步')||t.includes('确定')||t.includes('开始办理'))&&btns[i].offsetParent!==null&&!btns[i].disabled){
                    btns[i].click();return;
                }
            }
        })()""")
        time.sleep(3)
else:
    # Step 6b: 没有列表项，使用其他来源名称
    print("\nStep 6b: 使用其他来源名称")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
        if(wn){
            if(typeof wn.toOther==='function')wn.toOther();
            else if('isOther' in wn.$data)wn.$set(wn.$data,'isOther',true);
            wn.$forceUpdate();
        }
    })()""")
    time.sleep(2)
    
    # 填写
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
    
    # 找所有按钮并逐个尝试
    btns = ev("""(function(){var btns=document.querySelectorAll('button,.el-button');var r=[];for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||'',type:btns[i].type||''})}return r})()""")
    print(f"  按钮: {btns}")
    
    # 点击每个可能的提交按钮
    for btn in (btns or []):
        t = btn.get('text','')
        idx = btn.get('idx',0)
        if any(kw in t for kw in ['确定','确认','提交','保存','下一步','选择']):
            print(f"  尝试点击: {t}")
            ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
            time.sleep(3)
            
            # 检查API
            api_logs2 = ev("window.__api_logs||[]")
            new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
            for l in new_apis:
                print(f"  NEW API: {l.get('method','')} {l.get('url','').split('?')[0]} status={l.get('status')} resp={l.get('response','')[:100]} body={l.get('body','')[:50]}")
            
            # 检查nameId
            comp3 = ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                return{nameId:wn?.$data?.nameId||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
            })()""")
            print(f"  comp3: nameId={comp3.get('nameId','') if comp3 else ''} hash={comp3.get('hash','') if comp3 else ''}")
            
            if comp3 and comp3.get('nameId'):
                nid = comp3['nameId']
                print(f"  ✅ nameId={nid}，调用startSheli")
                ev(f"""(function(){{
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                    if(wn&&typeof wn.startSheli==='function')wn.startSheli({{nameId:'{nid}'}});
                }})()""")
                time.sleep(5)
                break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("450.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("450.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})

ws.close()
print("✅ 完成")
