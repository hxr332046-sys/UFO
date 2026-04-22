#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设置el-form model字段 → 修复验证 → 尝试保存/下一步 → 遍历步骤"""
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

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# Step 1: 获取el-form model完整字段和当前值
print("\nStep 1: el-form model字段")
form_model = ev("""(function(){
    var formEl=document.querySelector('.el-form');
    if(!formEl)return{error:'no_form'};
    var comp=formEl.__vue__;
    if(!comp)return{error:'no_vue'};
    var model=comp.model||{};
    var result={};
    for(var k in model){
        var v=model[k];
        if(v===null||v===undefined||v==='')result[k]='(empty)';
        else if(typeof v==='object')result[k]='obj:'+JSON.stringify(v).substring(0,60);
        else result[k]=String(v).substring(0,60);
    }
    return{keys:Object.keys(model).length,model:result};
})()""")
print(f"  keys: {form_model.get('keys',0) if form_model else 0}")
if form_model and form_model.get('model'):
    for k,v in form_model.get('model',{}).items():
        if v != '(empty)':
            print(f"    {k}: {v}")

# Step 2: 设置el-form model所有字段
print("\nStep 2: 设置el-form model")
set_result = ev("""(function(){
    var formEl=document.querySelector('.el-form');
    if(!formEl)return{error:'no_form'};
    var comp=formEl.__vue__;
    var model=comp.model||{};
    var set=comp.$set.bind(comp);
    
    // 行业类型相关
    set(model,'itemIndustryTypeCode','I65');
    set(model,'industryTypeName','软件和信息技术服务业');
    set(model,'multiIndustryName','软件和信息技术服务业');
    set(model,'multiIndustry','I65');
    set(model,'industryId','I65');
    set(model,'zlBusinessInd','I65');
    
    // 经营范围
    set(model,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    set(model,'busiAreaCode','I65');
    set(model,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    set(model,'busiAreaData','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    set(model,'areaCategory','');
    set(model,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    
    // 经营期限
    set(model,'busiPeriod','1');  // 长期
    set(model,'busiDateEnd','');
    
    // 其他字段
    set(model,'secretaryServiceEnt','');
    set(model,'businessUuid','');
    set(model,'xfz','');
    
    comp.$forceUpdate();
    return{set:true};
})()""")
print(f"  set_result: {set_result}")

# Step 3: 修复经营期限radio
print("\nStep 3: 修复经营期限")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营期限')){
            var radios=items[i].querySelectorAll('.el-radio__input');
            for(var j=0;j<radios.length;j++){
                var text=radios[j].closest('.el-radio')?.textContent?.trim()||'';
                if(text.includes('长期')&&!radios[j].classList.contains('is-checked')){
                    radios[j].click();
                    return{clicked:'长期'};
                }
            }
        }
    }
})()""")
time.sleep(1)

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
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 5: 检查验证错误
print("\nStep 5: 检查验证错误")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors: {errors}")

# Step 6: 尝试保存
print("\nStep 6: 尝试保存")
save_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findFormComp(vm,0);
    if(!comp)return{error:'no_comp'};
    
    // 调用save方法
    if(typeof comp.save==='function'){
        try{
            comp.save(null,function(){},'working');
            return{called:'save'};
        }catch(e){
            return{error:e.message};
        }
    }
    return{error:'no_save'};
})()""")
print(f"  save_result: {save_result}")
time.sleep(5)

# 检查API
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'getUserInfo' not in url and 'getCacheCreateTime' not in url:
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:30]}")
            except: pass

# Step 7: 检查验证错误
errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"\n  errors after save: {errors2}")

# Step 8: 如果有验证错误，修复
if errors2:
    print("\nStep 8: 修复验证错误")
    for err in errors2:
        print(f"  修复: {err}")
        if '经营期限' in err:
            ev("""(function(){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                    var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                    if(label.includes('经营期限')){
                        var radios=items[i].querySelectorAll('.el-radio__input');
                        for(var j=0;j<radios.length;j++){
                            if(!radios[j].classList.contains('is-checked')){
                                radios[j].click();break;
                            }
                        }
                    }
                }
            })()""")
        elif '行业类型' in err:
            # 设置el-form model
            ev("""(function(){
                var formEl=document.querySelector('.el-form');
                var comp=formEl?.__vue__;
                if(comp&&comp.model){
                    comp.$set(comp.model,'itemIndustryTypeCode','I65');
                    comp.$set(comp.model,'industryTypeName','软件和信息技术服务业');
                }
            })()""")
        elif '经营范围' in err or '经营用语' in err:
            ev("""(function(){
                var formEl=document.querySelector('.el-form');
                var comp=formEl?.__vue__;
                if(comp&&comp.model){
                    comp.$set(comp.model,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
                }
            })()""")
        elif '企业住所' in err or '区域' in err:
            ev("""(function(){
                var formEl=document.querySelector('.el-form');
                var comp=formEl?.__vue__;
                if(comp&&comp.model){
                    comp.$set(comp.model,'domDistrict','450103');
                }
            })()""")
    time.sleep(2)

# Step 9: 尝试下一步
print("\nStep 9: 尝试下一步")
# 找到下一步按钮
next_btn = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('保存并下一步')||t.includes('下一步')||t.includes('保存'))&&btns[i].offsetParent!==null&&!btns[i].disabled){
            return{idx:i,text:t};
        }
    }
    return{error:'no_btn'};
})()""")
print(f"  next_btn: {next_btn}")

if next_btn and not next_btn.get('error'):
    idx = next_btn.get('idx',0)
    ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
    time.sleep(5)
    
    # 检查API
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis:
        url = l.get('url','')
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:30]}")
            except: pass
    
    # 检查页面
    page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# Step 10: 遍历步骤
print("\nStep 10: 遍历步骤")
for step in range(7):
    current = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findFormComp(vm,d){
            if(d>15)return null;
            if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
                var bdi=vm.$data.businessDataInfo;
                return{
                    hash:location.hash,
                    formCount:document.querySelectorAll('.el-form-item').length,
                    curStep:bdi.processVo?.stepList?.length||0,
                    curCompUrl:bdi.flowData?.currCompUrl||'',
                    stepList:bdi.processVo?.stepList?.map(function(s){return s.stepName||s.name||''})||[]
                };
            }
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
            return null;
        }
        return findFormComp(vm,0);
    })()""")
    
    if not current:
        print(f"  步骤{step}: 无组件")
        break
    
    h = current.get('hash','')
    fc = current.get('formCount',0)
    steps = current.get('stepList',[])
    compUrl = current.get('curCompUrl','')
    
    print(f"\n  步骤{step}: hash={h} forms={fc} compUrl={compUrl}")
    if steps:
        print(f"    stepList: {steps}")
    
    # 检查验证错误
    errs = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,30))}return r.slice(0,5)})()""")
    if errs:
        print(f"    errors: {errs}")
    
    # 找下一步按钮
    btn = ev("""(function(){
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if((t.includes('保存并下一步')||t.includes('下一步'))&&btns[i].offsetParent!==null&&!btns[i].disabled){
                return{idx:i,text:t};
            }
        }
        return null;
    })()""")
    
    if not btn:
        print("    无下一步按钮")
        break
    
    print(f"    点击: {btn.get('text','')}")
    ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{btn.get('idx',0)}])btns[{btn.get('idx',0)}].click()}})()""")
    time.sleep(5)
    
    # 检查API
    api_logs3 = ev("window.__api_logs||[]")
    new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis3[-3:]:
        url = l.get('url','')
        print(f"    API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    api_logs = api_logs3

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

ws.close()
print("✅ 完成")
