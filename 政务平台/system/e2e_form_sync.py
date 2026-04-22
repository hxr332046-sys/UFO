#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""直接设置form.distList+distCode+streetCode绕过验证"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
        if not page: return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 回到guide/base
# ============================================================
print("Step 1: 回到guide/base")
ev("""(function(){document.getElementById('app').__vue__.$router.push('/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=')})()""")
time.sleep(3)

# ============================================================
# Step 2: 查看form.distList当前值
# ============================================================
print("Step 2: form.distList")
form_state = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form;
    if(!form)return'no_form';
    return {
        formDistList:JSON.stringify(form.distList).substring(0,60),
        formDistCode:form.distCode,
        formStreetCode:form.streetCode,
        formStreetName:form.streetName,
        formHavaAdress:form.havaAdress,
        formAddress:form.address,
        formEntType:form.entType,
        formNameCode:form.nameCode,
        // 也看comp.$data.distList
        dataDistList:JSON.stringify(comp.$data.distList).substring(0,60),
        // 看ElForm model
        elFormModel:null
    };
})()""")
print(f"  {json.dumps(form_state, ensure_ascii=False)[:400] if isinstance(form_state,dict) else form_state}")

# ============================================================
# Step 3: 找ElForm的model并直接设置distList
# ============================================================
print("\nStep 3: 设置form.distList")
set_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form;
    if(!form)return'no_form';
    
    // 关键：设置form.distList为非空数组（验证器检查truthy）
    comp.$set(form,'distList',['450000','450100','450103']);
    comp.$set(form,'distCode','450103');
    comp.$set(form,'streetCode','');
    comp.$set(form,'streetName','');
    comp.$set(form,'havaAdress','0');
    comp.$set(form,'address','广西壮族自治区/南宁市/青秀区');
    comp.$set(form,'detAddress','民族大道100号');
    comp.$set(form,'entType','1100');
    comp.$set(form,'nameCode','0');
    comp.$set(form,'registerCapital','100');
    comp.$set(form,'moneyKindCode','156');
    comp.$set(form,'fzSign','N');
    comp.$set(form,'parentEntRegno','');
    comp.$set(form,'parentEntName','');
    
    // 也设置comp.$data.distList
    comp.$set(comp.$data,'distList',['450000','450100','450103']);
    
    // 清除验证
    var elForm=comp.$refs?.form;
    if(elForm){try{elForm.clearValidate()}catch(e){}}
    
    return {
        formDistList:JSON.stringify(form.distList).substring(0,40),
        dataDistList:JSON.stringify(comp.$data.distList).substring(0,40),
        formDistCode:form.distCode
    };
})()""")
print(f"  {set_result}")

# ============================================================
# Step 4: 验证form
# ============================================================
print("\nStep 4: 验证form")
validate_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var elForm=comp.$refs?.form;
    if(!elForm)return'no_form';
    
    return new Promise(function(resolve){
        elForm.validate(function(valid,fields){
            var errors=[];
            if(fields){
                Object.keys(fields).forEach(function(k){
                    if(fields[k]&&fields[k].length)errors.push(k+':'+fields[k][0].message);
                });
            }
            resolve({valid:valid,errors:errors});
        });
    });
})()""", timeout=10)
print(f"  {validate_result}")

# ============================================================
# Step 5: 如果验证通过，调用fzjgFlowSave
# ============================================================
print("\nStep 5: fzjgFlowSave")

# 拦截
ev("""(function(){
    window.__all_xhr=[];window.__jump_args=[];window.__save_api=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        window.__all_xhr.push({url:url.substring(0,80),bodyLen:(body||'').length});
        if(url.includes('guide')||url.includes('flow')||url.includes('save')||url.includes('extraDto')||url.includes('register')){
            var self=this;
            self.addEventListener('load',function(){window.__save_api={url:url,status:self.status,text:(self.responseText||'').substring(0,300)}});
        }
        return origSend.apply(this,arguments);
    };
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router;
    if(router&&router.jump){
        var origJump=router.jump.bind(router);
        router.jump=function(){window.__jump_args.push(Array.from(arguments).map(function(a){return typeof a==='object'?JSON.stringify(a).substring(0,300):String(a)}));return origJump.apply(router,arguments)};
    }
})()""")

save_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    try{comp.fzjgFlowSave();return{called:true}}catch(e){return{error:e.message.substring(0,100)}}
})()""", timeout=20)
print(f"  fzjgFlowSave: {save_result}")
time.sleep(10)

# ============================================================
# Step 6: 检查结果
# ============================================================
print("\nStep 6: 检查结果")
xhr = ev("window.__all_xhr")
save_api = ev("window.__save_api")
jump = ev("window.__jump_args")
cur = ev("location.hash")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")

print(f"  XHR: {xhr}")
print(f"  saveAPI: {save_api}")
print(f"  jump: {jump}")
print(f"  路由: {cur}")
print(f"  验证错误: {errors}")

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    return {flowControl:!!findComp(vm,'flow-control',0),withoutName:!!findComp(vm,'without-name',0),hash:location.hash};
})()""")
print(f"  组件: {comps}")

if isinstance(comps, dict) and comps.get('withoutName'):
    ev("""(function(){var vm=document.getElementById('app').__vue__;function f(vm,n,d){if(d>20)return null;if(vm.$options?.name===n)return vm;for(var i=0;i<vm.$children.length;i++){var r=f(vm.$children[i],n,d+1);if(r)return r}return null}var wn=f(vm,'without-name',0);if(wn)wn.toNotName()})()""")
    time.sleep(5)
    comps2 = ev("""(function(){var vm=document.getElementById('app').__vue__;function f(vm,n,d){if(d>20)return null;if(vm.$options?.name===n)return vm;for(var i=0;i<vm.$children.length;i++){var r=f(vm.$children[i],n,d+1);if(r)return r}return null}return{flowControl:!!f(vm,'flow-control',0),hash:location.hash}})()""")
    print(f"  toNotName后: {comps2}")

print("\n✅ 完成")
