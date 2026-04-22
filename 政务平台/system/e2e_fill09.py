#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复4个验证错误: 企业住所cascader + 生产经营地址cascader + 行业类型tree + 经营范围"""
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

# Step 1: 找到每个验证错误对应的form-item和其prop
print("\nStep 1: 分析验证字段")
fields = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=items[i].__vue__;
        var prop=comp?.prop||comp?.$props?.prop||'';
        var error=items[i].querySelector('.el-form-item__error')?.textContent?.trim()||'';
        if(label||error){
            result.push({idx:i,label:label.substring(0,20),prop:prop,error:error.substring(0,30),
                hasCascader:!!items[i].querySelector('.el-cascader'),
                hasSelect:!!items[i].querySelector('.el-select'),
                hasTreeSelect:!!items[i].querySelector('[class*="tree-popper"],.tne-select'),
                hasButton:!!items[i].querySelector('button'),
                hasRadio:!!items[i].querySelector('.el-radio'),
                hasInput:!!items[i].querySelector('input.el-input__inner')
            });
        }
    }
    return result;
})()""")
for f in (fields or []):
    if f.get('error') or f.get('label') in ['企业住所：','生产经营地址：','行业类型：','经营范围（许可经营项目）：','详细地址：','生产经营地详细地址：']:
        print(f"  [{f.get('idx')}] prop={f.get('prop','')} label={f.get('label','')} err={f.get('error','')} cascader={f.get('hasCascader')} select={f.get('hasSelect')} tree={f.get('hasTreeSelect')} btn={f.get('hasButton')}")

# Step 2: 找到businessDataInfo组件的el-form引用
print("\nStep 2: 找el-form引用")
form_ref = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var refs=vm.$refs||{};
            var formRef=null;
            for(var k in refs){
                var r=refs[k];
                if(r&&r.$options&&(r.$options.name==='ElForm'||r.$el?.classList?.contains('el-form'))){
                    formRef={refName:k,compName:r.$options?.name||'',modelKeys:r.model?Object.keys(r.model).length:0};
                    break;
                }
            }
            // 也检查子组件的refs
            for(var i=0;i<(vm.$children||[]).length;i++){
                var child=vm.$children[i];
                var childRefs=child.$refs||{};
                for(var k in childRefs){
                    var r=childRefs[k];
                    if(r&&r.$options&&(r.$options.name==='ElForm'||r.$el?.classList?.contains('el-form'))){
                        formRef={refName:k,compName:r.$options?.name||'',parentComp:child.$options?.name||'',modelKeys:r.model?Object.keys(r.model).length:0,modelSample:r.model?Object.keys(r.model).slice(0,20):[]};
                        break;
                    }
                }
                if(formRef)break;
            }
            return formRef;
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  form_ref: {form_ref}")

# Step 3: 直接分析el-form组件
print("\nStep 3: 直接分析el-form")
form_detail = ev("""(function(){
    var formEl=document.querySelector('.el-form');
    if(!formEl)return{error:'no_form'};
    var comp=formEl.__vue__;
    if(!comp)return{error:'no_vue'};
    var model=comp.model;
    if(!model)return{error:'no_model'};
    return{
        compName:comp.$options?.name||'',
        modelKeys:Object.keys(model),
        modelJSON:JSON.stringify(model).substring(0,500)
    };
})()""")
print(f"  modelKeys: {form_detail.get('modelKeys',[]) if form_detail else []}")
print(f"  modelJSON: {form_detail.get('modelJSON','')[:300] if form_detail else ''}")

# Step 4: 设置el-form model字段
print("\nStep 4: 设置el-form model字段")
if form_detail and form_detail.get('modelKeys'):
    set_result = ev("""(function(){
        var formEl=document.querySelector('.el-form');
        var comp=formEl.__vue__;
        var model=comp.model;
        
        // 企业住所 - cascader需要数组值
        comp.$set(model,'domDistrict',['450000','450100','450103']);
        // 生产经营地址
        comp.$set(model,'proLocDistrict',['450000','450100','450103']);
        // 行业类型
        comp.$set(model,'itemIndustryTypeCode','I65');
        comp.$set(model,'industryTypeName','软件和信息技术服务业');
        comp.$set(model,'multiIndustryName','软件和信息技术服务业');
        comp.$set(model,'multiIndustry','I65');
        comp.$set(model,'industryId','I65');
        comp.$set(model,'zlBusinessInd','I65');
        // 经营范围
        comp.$set(model,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
        comp.$set(model,'busiAreaCode','I65');
        comp.$set(model,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
        comp.$set(model,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
        // 经营期限
        comp.$set(model,'busiPeriod','1');
        
        comp.$forceUpdate();
        
        // 清除验证错误
        comp.clearValidate();
        
        return{set:true,keysAfter:Object.keys(model).length};
    })()""")
    print(f"  set_result: {set_result}")
else:
    # model为空，需要找正确的form
    print("  el-form model为空，搜索子组件form")
    sub_form = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findAllForms(vm,d){
            if(d>15)return[];
            var result=[];
            if(vm.$el&&vm.$el.classList?.contains('el-form')&&vm.model&&Object.keys(vm.model).length>0){
                result.push({name:vm.$options?.name||'',modelKeys:Object.keys(vm.model).slice(0,20),modelJSON:JSON.stringify(vm.model).substring(0,300)});
            }
            for(var i=0;i<(vm.$children||[]).length;i++){
                result=result.concat(findAllForms(vm.$children[i],d+1));
            }
            return result;
        }
        return findAllForms(vm,0);
    })()""")
    print(f"  sub_forms: {sub_form}")

# Step 5: 验证cascader组件
print("\nStep 5: 验证cascader")
cascader_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业住所')&&!label.includes('详细')||label.includes('生产经营地址')&&!label.includes('详细')){
            var cascader=items[i].querySelector('.el-cascader');
            if(cascader){
                var comp=cascader.__vue__;
                result.push({label:label,compName:comp?.$options?.name||'',value:JSON.stringify(comp.value||comp.presentText||''),presentText:comp.presentText||'',prop:items[i].__vue__?.prop||''});
            }
        }
    }
    return result;
})()""")
print(f"  cascader_info: {cascader_info}")

# Step 6: 设置cascader值
print("\nStep 6: 设置cascader值")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if((label.includes('企业住所')&&!label.includes('详细'))||(label.includes('生产经营地址')&&!label.includes('详细'))){
            var cascader=items[i].querySelector('.el-cascader');
            if(cascader){
                var comp=cascader.__vue__;
                if(comp){
                    var val=['450000','450100','450103'];
                    comp.$emit('input',val);
                    comp.$emit('change',val);
                    comp.value=val;
                    comp.presentText='广西壮族自治区/南宁市/青秀区';
                    comp.$forceUpdate();
                }
            }
        }
    }
})()""")
time.sleep(2)

# Step 7: 设置行业类型tne-select
print("\nStep 7: 设置行业类型tne-select")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            if(select){
                var comp=select.__vue__;
                if(comp){
                    comp.$emit('input','I65');
                    comp.$emit('change','I65');
                    comp.value='I65';
                    comp.selectedLabel='软件和信息技术服务业';
                    comp.$forceUpdate();
                }
            }
        }
    }
})()""")
time.sleep(1)

# Step 8: 设置经营范围
print("\nStep 8: 设置经营范围")
# 找经营范围的textarea/input
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var textarea=items[i].querySelector('textarea');
            if(textarea){
                var s=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
                s.call(textarea,'软件开发;信息技术咨询服务;数据处理和存储支持服务');
                textarea.dispatchEvent(new Event('input',{bubbles:true}));
                textarea.dispatchEvent(new Event('change',{bubbles:true}));
            }
            // 也设置Vue组件
            var comp=items[i].__vue__;
            // 向上找有businessArea的组件
            var el=items[i];
            for(var d=0;d<10&&el;d++){
                var vc=el.__vue__;
                if(vc&&vc.$data){
                    for(var k in vc.$data){
                        if(k==='businessArea'||k==='busiAreaName'||k==='busiAreaData'){
                            vc.$set(vc.$data,k,'软件开发;信息技术咨询服务;数据处理和存储支持服务');
                        }
                    }
                }
                el=el.parentElement;
            }
        }
    }
})()""")
time.sleep(1)

# Step 9: 重新验证
print("\nStep 9: 重新验证")
ev("""(function(){
    var formEl=document.querySelector('.el-form');
    if(formEl){
        var comp=formEl.__vue__;
        if(comp&&typeof comp.validate==='function'){
            comp.validate(function(valid,invalidFields){
                window.__validate_result={valid:valid,invalidFields:Object.keys(invalidFields||{}).slice(0,10)};
            });
        }
    }
})()""")
time.sleep(3)

validate_result = ev("window.__validate_result||null")
print(f"  validate_result: {validate_result}")

# 检查验证错误
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors: {errors}")

# Step 10: 如果还有错误，尝试通过businessDataInfo组件的save方法
print("\nStep 10: 尝试save")
if not errors:
    save_result = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findFormComp(vm,d){
            if(d>15)return null;
            if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
            return null;
        }
        var comp=findFormComp(vm,0);
        if(comp&&typeof comp.save==='function'){
            comp.save(null,function(){},'working');
            return{called:true};
        }
        return{error:'no_save'};
    })()""")
    print(f"  save: {save_result}")
    time.sleep(5)
    
    # 检查结果
    page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

ws.close()
print("✅ 完成")
