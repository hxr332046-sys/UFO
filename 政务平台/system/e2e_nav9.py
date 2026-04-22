#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 正确填写其他来源名称 → validateName → 获取nameId → startSheli → 表单"""
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

# Step 1: 确保在select-prise且isOther=true
page = ev("({hash:location.hash})")
print(f"当前: hash={page.get('hash','') if page else '?'}")

if not page or 'select-prise' not in page.get('hash',''):
    print("导航到select-prise...")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(3)
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/select-prise')})()""")
    time.sleep(3)

# 设置isOther=true
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(sp){sp.$set(sp.$data,'isOther',true);sp.$forceUpdate()}
})()""")
time.sleep(2)

# Step 2: 分析validateName源码和form结构
print("\nStep 2: 分析validateName和form")
src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    var methods=sp.$options?.methods||{};
    return{
        validateName:methods.validateName?.toString()?.substring(0,800)||'',
        form:JSON.stringify(sp.$data?.form)||'',
        rules:JSON.stringify(sp.$data?.rules)?.substring(0,300)||'',
        dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,200)||''
    };
})()""")
print(f"  validateName: {src.get('validateName','')[:400] if src else 'None'}")
print(f"  form: {src.get('form','') if src else ''}")
print(f"  rules: {src.get('rules','') if src else ''}")

# Step 3: 正确填写表单
print("\nStep 3: 正确填写表单")
# 先清空form然后设置正确值
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return;
    // 直接设置form数据
    sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');
    sp.$set(sp.$data.form,'numbers','GX2024001');
    sp.$forceUpdate();
})()""")
time.sleep(1)

# 也通过DOM填写
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    for(var i=0;i<fi.length;i++){
        var lb=fi[i].querySelector('.el-form-item__label');
        var input=fi[i].querySelector('.el-input__inner,input');
        if(!input)continue;
        var ph=input.placeholder||'';
        if(ph.includes('企业名称')){
            s.call(input,'广西智信数据科技有限公司');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
        }
        if(ph.includes('保留单号')){
            s.call(input,'GX2024001');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
        }
    }
})()""")
time.sleep(1)

# 验证填写
form_val = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    return{form:JSON.stringify(sp?.$data?.form),inputVals:Array.from(document.querySelectorAll('.el-form-item .el-input__inner')).map(function(i){return i.value}).filter(function(v){return v})};
})()""")
print(f"  form: {form_val}")

# Step 4: 安装XHR拦截器监控API调用
print("\nStep 4: 安装XHR拦截器")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){
        this.__url=u;this.__method=m;
        return origOpen.apply(this,arguments);
    };
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(){
        var self=this;
        this.addEventListener('load',function(){
            window.__api_logs.push({
                url:self.__url,
                method:self.__method,
                status:self.status,
                response:self.responseText?.substring(0,300)||''
            });
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 5: 调用validateName
print("\nStep 5: 调用validateName")
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    try{
        var r=sp.validateName();
        return{called:true,result:r};
    }catch(e){
        return{error:e.message};
    }
})()""")
print(f"  result: {result}")
time.sleep(3)

# 检查API调用
api_logs = ev("window.__api_logs||[]")
print(f"  api_logs: {api_logs}")

# Step 6: 检查nameId
print("\nStep 6: 检查nameId")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    return{
        nameId:sp.$data?.nameId||sp.$data?.form?.nameId||sp.$data?.dataInfo?.nameId||'',
        dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,300)||'',
        form:JSON.stringify(sp.$data?.form)||'',
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        errMsg:document.querySelector('.el-message,[class*="error"]')?.textContent?.trim()||''
    };
})()""")
print(f"  nameId: {comp.get('nameId','') if comp else ''}")
print(f"  dataInfo: {comp.get('dataInfo','') if comp else ''}")
print(f"  errMsg: {comp.get('errMsg','') if comp else ''}")

# Step 7: 如果validateName返回了promise，等待结果
if result and result.get('called'):
    # validateName可能返回Promise
    print("\nStep 7: 等待Promise结果")
    time.sleep(3)
    
    # 再次检查
    comp2 = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return{error:'no_comp'};
        return{
            nameId:sp.$data?.nameId||sp.$data?.form?.nameId||sp.$data?.dataInfo?.nameId||'',
            dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,300)||'',
            hash:location.hash,
            formCount:document.querySelectorAll('.el-form-item').length
        };
    })()""")
    print(f"  comp2: nameId={comp2.get('nameId','') if comp2 else ''} hash={comp2.get('hash','') if comp2 else ''}")
    
    api_logs2 = ev("window.__api_logs||[]")
    print(f"  api_logs2: {api_logs2}")

# Step 8: 如果有nameId，调用startSheli
nameId = (comp.get('nameId','') if comp else '') or (comp2.get('nameId','') if comp else '')
if nameId:
    print(f"\nStep 8: 调用startSheli (nameId={nameId})")
    ev(f"""(function(){{
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nameId}'}});
    }})()""")
    time.sleep(5)
    
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
else:
    # Step 8b: 尝试直接调用startSheli不带参数
    print("\nStep 8b: 尝试startSheli不带参数")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp){
            // startSheli需要参数t={nameId:...}
            // 尝试传入form对象
            if(typeof sp.startSheli==='function'){
                try{sp.startSheli(sp.$data.form)}catch(e){console.log('startSheli error:',e)}
            }
        }
    })()""")
    time.sleep(5)
    
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
    
    api_logs3 = ev("window.__api_logs||[]")
    print(f"  api_logs3: {api_logs3}")

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
log("390.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 完成")
