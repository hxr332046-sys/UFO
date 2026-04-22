#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同步cascader值到父表单，解决验证问题"""
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
# Step 1: 分析tne-data-picker的updateBindData和updateSelected
# ============================================================
print("Step 1: tne-data-picker方法源码")
methods_src = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    var result={};
    var names=['updateBindData','updateSelected','onPropsChange','getNodeData','loadData','loadAllData','loadNodeData'];
    for(var i=0;i<names.length;i++){
        var fn=vm[names[i]];
        if(fn&&typeof fn==='function'){
            result[names[i]]=fn.toString().substring(0,300);
        }
    }
    return result;
})()""")
if isinstance(methods_src, dict):
    for k,v in methods_src.items():
        print(f"  {k}: {v[:200]}")
else:
    print(f"  {methods_src}")

# ============================================================
# Step 2: 查看tne-data-picker的selected和dataList
# ============================================================
print("\nStep 2: selected和dataList状态")
state = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    var d=vm.$data||{};
    return {
        isOpened:d.isOpened,
        inputSelected:d.inputSelected,
        checkValue:d.checkValue,
        loading:d.loading,
        errorMessage:d.errorMessage,
        dataListLen:Array.isArray(d.dataList)?d.dataList.length:0,
        dataListFirst3:Array.isArray(d.dataList)?d.dataList.slice(0,3).map(function(x){return JSON.stringify(x).substring(0,40)}):[],
        selected:d.selected,
        selectedIndex:d.selectedIndex,
        value:vm.value||vm.$props?.value,
        // v-model绑定
        modelExpr:vm.$vnode?.data?.model?.expression||'',
        modelValue:vm.$vnode?.data?.model?.value||''
    };
})()""")
print(f"  {json.dumps(state, ensure_ascii=False)[:500] if isinstance(state,dict) else state}")

# ============================================================
# Step 3: 调用updateSelected和updateBindData
# ============================================================
print("\nStep 3: 同步值")
sync_result = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    
    // 设置selected
    vm.$set(vm.$data,'selected',['450000','450100','450103']);
    vm.$set(vm.$data,'inputSelected','广西壮族自治区/南宁市/青秀区');
    vm.$set(vm.$data,'checkValue',['450000','450100','450103']);
    
    // 调用updateSelected
    try{vm.updateSelected()}catch(e){}
    // 调用updateBindData
    try{vm.updateBindData(['450000','450100','450103'])}catch(e){}
    
    // 触发change事件
    vm.$emit('change',['450000','450100','450103']);
    vm.$emit('input',['450000','450100','450103']);
    
    // 找到父form-item并清除验证
    var parent=vm.$parent;
    while(parent){
        if(parent.$options?.name==='ElFormItem'||parent.clearValidate){
            try{parent.clearValidate()}catch(e){}
            break;
        }
        parent=parent.$parent;
    }
    
    // 也找ElForm清除验证
    parent=vm.$parent;
    while(parent){
        if(parent.$options?.name==='ElForm'){
            try{parent.clearValidate()}catch(e){}
            break;
        }
        parent=parent.$parent;
    }
    
    return {synced:true,selected:vm.$data?.selected,inputSelected:vm.$data?.inputSelected};
})()""")
print(f"  {sync_result}")

# ============================================================
# Step 4: 找到guide组件的form model并设置地址
# ============================================================
print("\nStep 4: 设置guide form model")
form_set = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    
    // 找v-model绑定的表达式
    var modelExpr=vm.$vnode?.data?.model?.expression||'';
    if(!modelExpr)return{noModelExpr:true};
    
    // 找到父组件
    var parent=vm.$parent;
    while(parent){
        // 尝试在parent.$data中设置
        var keys=modelExpr.split('.');
        var target=parent;
        var found=true;
        for(var i=0;i<keys.length-1;i++){
            if(target[keys[i]]===undefined&&target.$data?.[keys[i]]===undefined){found=false;break;}
            target=target[keys[i]]||target.$data?.[keys[i]];
        }
        if(found&&target){
            var lastKey=keys[keys.length-1];
            parent.$set(target,lastKey,['450000','450100','450103']);
            return {set:true,expr:modelExpr,parentName:parent.$options?.name};
        }
        parent=parent.$parent;
    }
    return {notFound:true,expr:modelExpr};
})()""")
print(f"  {form_set}")

# ============================================================
# Step 5: 检查验证错误
# ============================================================
print("\nStep 5: 验证错误")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  {errors}")

# ============================================================
# Step 6: 点击下一步
# ============================================================
print("\nStep 6: 点击下一步")
click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('下一步')&&!all[i].disabled){
            all[i].click();
            return {clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  点击: {click}")
time.sleep(5)

errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误(后): {errors2}")

cur = ev("location.hash")
print(f"  路由: {cur}")

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    return {flowControl:!!fc,withoutName:!!wn,hash:location.hash};
})()""")
print(f"  组件: {comps}")

if isinstance(comps, dict) and comps.get('withoutName'):
    ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0);
        if(wn)wn.toNotName();
    })()""")
    time.sleep(5)
    comps2 = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        return {flowControl:!!fc,hash:location.hash};
    })()""")
    print(f"  toNotName后: {comps2}")

print("\n✅ 完成")
