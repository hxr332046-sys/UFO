#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试生产经营地址验证问题"""
import json, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)

def ev(js, timeout=15):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
    ws.settimeout(timeout + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r.get("result", {}).get("result", {}).get("value")

# 1. 找生产经营地址的验证规则
r1 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('生产经营地址')){
            var comp=items[i].__vue__;
            var prop=comp?.prop||comp?.$props?.prop||'';
            var parent=comp?.$parent;
            var rules=null;
            // 向上查找有rules的form
            var p=comp;
            while(p){
                if(p.rules&&p.rules[prop]){
                    rules=p.rules[prop];
                    break;
                }
                p=p.$parent;
            }
            var ruleText=[];
            if(rules){
                for(var j=0;j<rules.length;j++){
                    ruleText.push({
                        required:rules[j].required,
                        message:rules[j].message||'',
                        trigger:rules[j].trigger||'',
                        validator:rules[j].validator?rules[j].validator.toString().substring(0,300):'',
                        type:rules[j].type||''
                    });
                }
            }
            // 找picker组件
            var picker=items[i].querySelector('[class*="tne-data-picker"]')?.__vue__;
            var pickerInfo=null;
            if(picker){
                pickerInfo={
                    name:picker.$options?.name,
                    modelValue:picker.$props?.modelValue,
                    selected:picker.selected,
                    value:picker.$attrs?.value||picker.$data?.value
                };
            }
            return {prop:prop,rules:ruleText,pickerInfo:pickerInfo,formName:p?.$options?.name||''};
        }
    }
    return 'not_found';
})()""")

print("=== 生产经营地址验证规则 ===")
print(json.dumps(r1, ensure_ascii=False, indent=2))

# 2. 检查picker2的modelValue绑定
r2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    
    var pickers=[];
    function scan(vm,d){
        if(d>12)return;
        if(vm.$options?.name==='tne-data-picker')pickers.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1);
    }
    scan(ri,0);
    
    var p2=pickers[1];
    if(!p2)return 'no_picker2';
    
    // 检查v-model绑定
    var modelValue=p2.$props?.modelValue;
    var vModel=p2.$vnode?.data?.model?.value;
    var vModelExpr=p2.$vnode?.data?.model?.expression;
    var attrs=p2.$vnode?.data?.attrs||{};
    
    // 检查$emit历史
    return {
        modelValue:modelValue,
        vModelValue:vModel,
        vModelExpr:vModelExpr,
        attrsKeys:Object.keys(attrs),
        attrsValues:Object.fromEntries(Object.keys(attrs).map(function(k){return [k,String(attrs[k]).substring(0,50)]})),
        selected:p2.selected,
        checkValue:p2.checkValue,
        inputValue:p2.$el?.querySelector('input')?.value||''
    };
})()""")

print("\n=== PICKER2 V-MODEL ===")
print(json.dumps(r2, ensure_ascii=False, indent=2))

# 3. 尝试通过$emit('input')触发v-model更新
r3 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    
    var pickers=[];
    function scan(vm,d){
        if(d>12)return;
        if(vm.$options?.name==='tne-data-picker')pickers.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1);
    }
    scan(ri,0);
    
    var p2=pickers[1];
    if(!p2)return 'no_picker2';
    
    // 尝试$emit input事件更新v-model
    p2.$emit('input', ['450000','450100','450103']);
    
    // 也尝试$emit change
    p2.$emit('change', ['450000','450100','450103']);
    
    // 也尝试update:modelValue
    p2.$emit('update:modelValue', ['450000','450100','450103']);
    
    return 'emitted';
})()""")
print(f"\nemit结果: {r3}")

import time; time.sleep(2)

# 4. 再次检查验证
r4 = ev("""(function(){
    var msgs=document.querySelectorAll('.el-form-item__error');
    var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}
    return r;
})()""")
print(f"验证错误: {r4}")

# 5. 如果还有错误，尝试手动触发验证清除
if r4 and '生产经营' in str(r4):
    r5 = ev("""(function(){
        var forms=document.querySelectorAll('.el-form');
        for(var i=0;i<forms.length;i++){
            var comp=forms[i].__vue__;
            if(comp&&typeof comp.clearValidate==='function'){
                comp.clearValidate();
            }
        }
        return 'cleared';
    })()""")
    print(f"清除验证: {r5}")
    time.sleep(1)
    
    # 重新触发验证
    r6 = ev("""(function(){
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var lb=items[i].querySelector('.el-form-item__label');
            if(lb&&lb.textContent.trim().includes('生产经营地址')){
                var comp=items[i].__vue__;
                var form=comp?.$parent;
                if(form&&typeof form.validate==='function'){
                    form.validate(function(valid){
                        window.__validate_result=valid;
                    });
                }
            }
        }
    })()""")
    time.sleep(2)
    
    r7 = ev("""(function(){
        var msgs=document.querySelectorAll('.el-form-item__error');
        var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}
        return r;
    })()""")
    print(f"清除后验证: {r7}")

ws.close()
