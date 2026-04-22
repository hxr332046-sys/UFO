#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到表单 - 完成名称选择后让应用自然跳转，不用router.push"""
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

# 当前状态
state = ev("({hash:location.hash,hasVue:!!document.getElementById('app')?.__vue__})")
print(f"当前: hash={state.get('hash','') if state else '?'}")

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
time.sleep(1)

# 如果不在without-name，导航过去
if state and 'without-name' not in state.get('hash',''):
    print("导航到企业开办专区")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(3)
    
    page = ev("({hash:location.hash})")
    print(f"  hash={page.get('hash','') if page else '?'}")

# 现在应该在without-name页面
page = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,150)})")
print(f"\n当前页面: hash={page.get('hash','') if page else '?'} text={page.get('text','')[:60] if page else 'None'}")

# 分析without-name页面的Vue组件
print("\n分析without-name组件")
comp_analysis = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    
    // 找without-name组件
    var wn=findComp(vm,'without-name',0);
    if(!wn){
        // 也尝试找select-prise
        wn=findComp(vm,'select-prise',0);
    }
    if(!wn)return{error:'no_comp',hash:location.hash};
    
    var methods=Object.keys(wn.$options?.methods||{});
    var data=wn.$data||{};
    var dataKeys=Object.keys(data);
    
    // 找关键方法
    var navMethods=methods.filter(function(m){
        return m.includes('next')||m.includes('Next')||m.includes('submit')||m.includes('Submit')||
               m.includes('start')||m.includes('Start')||m.includes('sheli')||m.includes('Sheli')||
               m.includes('handle')||m.includes('Handle')||m.includes('go')||m.includes('Go')||
               m.includes('to')||m.includes('To')||m.includes('select')||m.includes('Select')||
               m.includes('confirm')||m.includes('Confirm')||m.includes('click')||m.includes('Click');
    });
    
    return{
        compName:wn.$options?.name||'',
        methods:methods,
        navMethods:navMethods,
        dataKeys:dataKeys.slice(0,20),
        busiDataList:data.busiDataList?.length||0,
        nameId:data.nameId||'',
        entType:data.entType||''
    };
})()""")
print(f"  compName: {comp_analysis.get('compName','') if comp_analysis else '?'}")
print(f"  navMethods: {comp_analysis.get('navMethods',[]) if comp_analysis else []}")
print(f"  dataKeys: {comp_analysis.get('dataKeys',[]) if comp_analysis else []}")
print(f"  busiDataList: {comp_analysis.get('busiDataList',0) if comp_analysis else 0}")
print(f"  nameId: {comp_analysis.get('nameId','') if comp_analysis else ''}")

# 如果有busiDataList，分析内容
if comp_analysis and comp_analysis.get('busiDataList',0) > 0:
    bdl = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
        if(!wn)return null;
        var bdl=wn.$data?.busiDataList||[];
        return bdl.slice(0,3).map(function(item){return{name:item.name||item.entName||'',id:item.id||item.nameId||'',type:item.type||item.entType||''}});
    })()""")
    print(f"  busiDataList items: {bdl}")

# 尝试各种方法来触发导航
print("\n尝试触发导航")

# 方法1: 调用toSelectName或startSheli
for method_name in ['toSelectName','startSheli','handleNext','nextStep','handleSubmit','confirmName','handleConfirm']:
    result = ev(f"""(function(){{
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
        var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
        if(wn&&typeof wn.{method_name}==='function'){{
            try{{
                wn.{method_name}();
                return{{called:true,method:'{method_name}'}};
            }}catch(e){{
                return{{error:e.message,method:'{method_name}'}};
            }}
        }}
        return{{notFound:true,method:'{method_name}'}};
    }})()""")
    if result and result.get('called'):
        print(f"  ✅ {method_name}: {result}")
        time.sleep(3)
        page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")
        if page and page.get('formCount',0) > 0:
            print("  ✅ 表单已加载！")
            break
        if page and page.get('hash','') != '#/index/without-name':
            print(f"  页面已变化: {page.get('hash','')}")
            break
    elif result and not result.get('notFound'):
        print(f"  ⚠️ {method_name}: {result}")

# 方法2: 点击页面上的按钮
print("\n点击页面按钮")
btn_analysis = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,[class*="btn"]');
    var r=[];
    for(var i=0;i<btns.length;i++){
        if(btns[i].offsetParent!==null){
            r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||'',class:(btns[i].className||'').substring(0,30)});
        }
    }
    return r.slice(0,15);
})()""")
print(f"  按钮: {btn_analysis}")

# 点击"下一步"或"确定"类按钮
for btn in (btn_analysis or []):
    t = btn.get('text','')
    if any(kw in t for kw in ['下一步','确定','确认','选择','提交','开始','办理']):
        idx = btn.get('idx',0)
        print(f"  点击: {t}")
        ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
        time.sleep(3)
        page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")
        if page and page.get('formCount',0) > 0:
            print("  ✅ 表单已加载！")
            break
        if page and 'without-name' not in page.get('hash',''):
            break

# 方法3: 通过API获取nameId后调用getHandleBusiness
print("\n方法3: 通过API获取nameId")
name_result = ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var xhr=new XMLHttpRequest();
    // 尝试获取名称信息
    xhr.open('GET','/icpsp-api/v4/pc/flow/name/getNameInfo?entType=1100',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{
        xhr.send();
        if(xhr.status===200){
            var resp=JSON.parse(xhr.responseText);
            return{status:xhr.status,code:resp.code,data:JSON.stringify(resp.data)?.substring(0,200)||''};
        }
        return{status:xhr.status};
    }catch(e){return{error:e.message}}
})()""")
print(f"  name_result: {name_result}")

# 方法4: 直接设置nameId并调用getHandleBusiness
print("\n方法4: 设置nameId并调用getHandleBusiness")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
    if(!wn)return;
    
    // 设置nameId
    if(wn.$data){
        wn.$set(wn.$data,'nameId','test001');
        wn.$set(wn.$data,'entType','1100');
    }
    
    // 调用getHandleBusiness
    if(typeof wn.getHandleBusiness==='function'){
        wn.getHandleBusiness();
    }
})()""")
time.sleep(3)

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# 如果仍然在without-name，检查getHandleBusiness做了什么
if page and 'without-name' in page.get('hash',''):
    print("\n检查getHandleBusiness效果")
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        var routes=router?.options?.routes||[];
        function findRoutes(routes,prefix){
            var r=[];
            for(var i=0;i<routes.length;i++){
                var path=prefix+routes[i].path;
                r.push(path);
                if(routes[i].children)r=r.concat(findRoutes(routes[i].children,path+'/'));
            }
            return r;
        }
        var all=findRoutes(routes,'');
        var flowRoutes=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')||r.includes('sheli')});
        return{totalRoutes:all.length,flowRoutes:flowRoutes};
    })()""")
    print(f"  routes: total={routes.get('totalRoutes',0)} flow={routes.get('flowRoutes',[])}")

# 最终结果
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
log("350.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 导航完成")
