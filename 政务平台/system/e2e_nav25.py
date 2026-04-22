#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析select-prise所有方法 → 找到提交其他来源名称的正确方法 → 获取nameId"""
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

# Step 1: 获取select-prise所有方法的完整源码
print("Step 1: 获取select-prise所有方法源码")
methods_src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    var methods=sp.$options?.methods||{};
    var result={};
    for(var m in methods){
        result[m]=methods[m].toString().substring(0,600);
    }
    return{compName:sp.$options?.name||'',methods:result,dataKeys:Object.keys(sp.$data||{}),fromType:sp.$data?.fromType||'',isOther:sp.$data?.isOther||false};
})()""")
print(f"  compName: {methods_src.get('compName','') if methods_src else ''}")
print(f"  fromType: {methods_src.get('fromType','') if methods_src else ''}")
print(f"  dataKeys: {methods_src.get('dataKeys',[]) if methods_src else []}")

for m, src in (methods_src.get('methods',{}) or {}).items():
    print(f"\n  {m}: {src[:400]}")

# Step 2: 安装XHR拦截器
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

# Step 3: 切换isOther并填写表单
print("\nStep 3: 填写其他来源名称表单")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(sp){
        if(!sp.$data?.isOther){
            if(typeof sp.toOther==='function')sp.toOther();
            else sp.$set(sp.$data,'isOther',true);
        }
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
    if(sp&&sp.$data?.form){
        sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');
        sp.$set(sp.$data.form,'numbers','GX2024001');
        sp.$forceUpdate();
    }
})()""")
time.sleep(1)

# Step 4: 尝试调用validateName方法
print("\nStep 4: 调用validateName")
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    
    // 查找validateName方法
    if(typeof sp.validateName==='function'){
        try{
            var r=sp.validateName();
            return{called:'validateName',resultType:typeof r,isPromise:!!(r&&typeof r.then==='function')};
        }catch(e){
            return{error:e.message,method:'validateName'};
        }
    }
    return{error:'no_validateName'};
})()""")
print(f"  result: {result}")
time.sleep(5)

# 检查API
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    if l.get('status') == 200:
        try:
            resp = json.loads(l.get('response','{}'))
            print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:50]} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:150]}")
        except: pass

# Step 5: 如果validateName没有触发API，尝试其他方法
print("\nStep 5: 尝试其他提交方法")
# 逐个尝试select-prise的方法
for method_name in ['submitOtherName', 'handleSubmit', 'submitForm', 'handleOther', 'saveOtherName', 'addOtherName', 'confirmOther', 'handleConfirm', 'onSubmit']:
    r = ev(f"""(function(){{
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return null;
        if(typeof sp.{method_name}==='function')return{{hasMethod:true}};
        return{{hasMethod:false}};
    }})()""")
    if r and r.get('hasMethod'):
        print(f"  ✅ 找到方法: {method_name}")
        # 调用它
        r2 = ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var sp=findComp(vm,'select-prise',0);
            if(sp&&typeof sp.{method_name}==='function'){{
                try{{var r=sp.{method_name}();return{{called:true,isPromise:!!(r&&typeof r.then==='function')}}}}catch(e){{return{{error:e.message}}}}
            }}
        }})()""")
        print(f"    result: {r2}")
        time.sleep(3)
        
        # 检查API
        api_logs2 = ev("window.__api_logs||[]")
        new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
        for l in new_apis:
            url = l.get('url','')
            print(f"    API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
            if l.get('status') == 200:
                try:
                    resp = json.loads(l.get('response','{}'))
                    print(f"      code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:150]}")
                except: pass
        api_logs = api_logs2

# Step 6: 如果所有方法都不行，直接调用API
print("\nStep 6: 直接调用名称相关API")
# 从之前的分析，getData调用了selectNameInforList
# 需要找到创建/保存名称的API
for api_path in [
    '/icpsp-api/v4/pc/register/guide/home/saveNameInfor',
    '/icpsp-api/v4/pc/register/guide/home/insertNameInfor',
    '/icpsp-api/v4/pc/register/guide/home/addNameInfor',
    '/icpsp-api/v4/pc/register/guide/home/bindName',
    '/icpsp-api/v4/pc/register/guide/index/bindName',
    '/icpsp-api/v4/pc/register/guide/index/saveName',
    '/icpsp-api/v4/pc/register/guide/name/save',
    '/icpsp-api/v4/pc/register/guide/name/bindName',
    '/icpsp-api/v4/pc/register/index/bindName',
    '/icpsp-api/v4/pc/register/index/saveName',
    '/icpsp-api/v4/pc/register/name/save',
    '/icpsp-api/v4/pc/register/name/bindName',
]:
    r = ev(f"""(function(){{
        var t=localStorage.getItem('top-token')||'';
        var xhr=new XMLHttpRequest();
        xhr.open('POST','{api_path}',false);
        xhr.setRequestHeader('Content-Type','application/json');
        xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
        try{{
            xhr.send(JSON.stringify({{name:'广西智信数据科技有限公司',numbers:'GX2024001',entType:'1100',busiType:'07'}}));
            return{{status:xhr.status,resp:xhr.responseText?.substring(0,200)||''}};
        }}catch(e){{return{{error:e.message}}}}
    }})()""")
    status = r.get('status',0) if r else 0
    if status != 404:
        print(f"  ✅ {api_path.split('/').pop()}: status={status} resp={r.get('resp','')[:80] if r else ''}")
    else:
        print(f"  ❌ {api_path.split('/').pop()}: 404")

# Step 7: 也尝试GET请求
print("\nStep 7: 尝试GET API")
for api_path in [
    '/icpsp-api/v4/pc/register/guide/home/getNameId?name=广西智信数据科技有限公司&entType=1100',
    '/icpsp-api/v4/pc/register/guide/home/getOtherName?name=广西智信数据科技有限公司&entType=1100',
    '/icpsp-api/v4/pc/register/guide/home/selectNameInforList?entType=1100&name=广西智信',
]:
    r = ev(f"""(function(){{
        var t=localStorage.getItem('top-token')||'';
        var xhr=new XMLHttpRequest();
        xhr.open('GET','{api_path}',false);
        xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
        try{{
            xhr.send();
            return{{status:xhr.status,resp:xhr.responseText?.substring(0,200)||''}};
        }}catch(e){{return{{error:e.message}}}}
    }})()""")
    status = r.get('status',0) if r else 0
    if status != 404:
        print(f"  ✅ status={status} resp={r.get('resp','')[:80] if r else ''}")

# 最终检查
comp = ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var sp=findComp(vm,'select-prise',0);return{nameId:sp?.$data?.nameId||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length}})()""")
print(f"\n最终: {comp}")

ws.close()
print("✅ 完成")
