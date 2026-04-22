#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化表单数据 - 找到正确的入口流程"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
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
# Step 1: 分析index组件(root/0/0/1/0/4/0/0)
# ============================================================
print("Step 1: 分析index组件")
idx_comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    // root/0/0/1/0/4/0/0
    var comp=vm.$children[0].$children[0].$children[1].$children[0].$children[4].$children[0].$children[0];
    if(!comp)return{error:'no_comp'};
    var name=comp.$options?.name||'';
    var dataKeys=Object.keys(comp.$data||{}).slice(0,15);
    var methods=Object.keys(comp.$options?.methods||{});
    var props=Object.keys(comp.$props||{});
    var refs=Object.keys(comp.$refs||{});
    // 检查关键数据
    var hasBdi=!!(comp.$data?.businessDataInfo);
    var hasParams=!!(comp.$data?.params);
    var paramsKeys=hasParams?Object.keys(comp.$data.params).slice(0,10):[];
    return{name:name,dataKeys:dataKeys,methods:methods.slice(0,15),props:props,refs:refs,hasBdi:hasBdi,hasParams:hasParams,paramsKeys:paramsKeys};
})()""")
print(f"  index组件: {idx_comp}")

# ============================================================
# Step 2: 分析basic-info组件(root/0/0/1/0/4)
# ============================================================
print("\nStep 2: 分析basic-info组件")
bi_comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var comp=vm.$children[0].$children[0].$children[1].$children[0].$children[4];
    if(!comp)return{error:'no_comp'};
    var name=comp.$options?.name||'';
    var dataKeys=Object.keys(comp.$data||{}).slice(0,15);
    var methods=Object.keys(comp.$options?.methods||{});
    var hasBdi=!!(comp.$data?.businessDataInfo);
    var bdi=comp.$data?.businessDataInfo;
    var bdiKeys=hasBdi?Object.keys(bdi).slice(0,10):[];
    return{name:name,dataKeys:dataKeys,methods:methods.slice(0,15),hasBdi:hasBdi,bdiKeys:bdiKeys};
})()""")
print(f"  basic-info组件: {bi_comp}")

# ============================================================
# Step 3: 深度搜索所有含businessDataInfo的组件
# ============================================================
print("\nStep 3: 搜索businessDataInfo")
bdi_search = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d,path){
        if(d>15)return[];
        var r=[];
        if(vm.$data&&vm.$data.businessDataInfo){
            r.push({path:path,name:vm.$options?.name||'',keysLen:Object.keys(vm.$data.businessDataInfo).length});
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            r=r.concat(find(vm.$children[i],d+1,path+'/'+i));
        }
        return r;
    }
    return find(vm,0,'root');
})()""")
print(f"  businessDataInfo: {bdi_search}")

# ============================================================
# Step 4: 检查Vuex store
# ============================================================
print("\nStep 4: Vuex store")
store_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var store=vm.$store;
    if(!store)return'no_store';
    var modules=Object.keys(store._modulesNamespaceMap||{});
    var state=store.state;
    var stateKeys=Object.keys(state);
    // 检查company模块
    var company=state.company||{};
    var companyKeys=Object.keys(company).slice(0,10);
    var busiData=company.busiData||company.businessData||{};
    return{modules:modules,stateKeys:stateKeys,companyKeys:companyKeys,busiDataKeys:Object.keys(busiData).slice(0,10)};
})()""")
print(f"  store: {store_info}")

# ============================================================
# Step 5: 检查flow-control组件(root/0/0/1/0)
# ============================================================
print("\nStep 5: flow-control组件")
fc_comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var comp=vm.$children[0].$children[0].$children[1].$children[0];
    if(!comp)return{error:'no_comp'};
    var name=comp.$options?.name||'';
    var dataKeys=Object.keys(comp.$data||{}).slice(0,15);
    var methods=Object.keys(comp.$options?.methods||{});
    var hasBdi=!!(comp.$data?.businessDataInfo);
    return{name:name,dataKeys:dataKeys,methods:methods.slice(0,15),hasBdi:hasBdi};
})()""")
print(f"  flow-control: {fc_comp}")

# ============================================================
# Step 6: 检查当前表单可见字段和值
# ============================================================
print("\nStep 6: 表单字段值")
form_vals = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        var select=items[i].querySelector('.el-select');
        var cascader=items[i].querySelector('.tne-data-picker');
        var value='';
        if(input)value=input.value||'';
        else if(select){
            var comp=select.__vue__;
            value=comp?.selectedLabel||comp?.value||'';
        }
        else if(cascader){
            var comp=cascader.__vue__;
            var sel=comp?.selected||comp?.inputSelected||[];
            value=sel.map(function(s){return s.text||s.allName||''}).join('/');
        }
        if(label)r.push({label:label.substring(0,15),value:String(value).substring(0,30)});
    }
    return r;
})()""")
if isinstance(form_vals, list):
    for f in form_vals:
        print(f"  {f['label']}: {f['value']}")

print("\n✅ 完成")
