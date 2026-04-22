#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""原生DOM点击测试tne-data-picker"""
import json, requests, websocket, time

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

# 刷新
print("刷新页面...")
ev("location.reload()")
time.sleep(8)

# Step 1: 点击企业住所input打开picker
print("\n=== Step 1: 打开picker ===")
r1 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业住所')&&!lb.textContent.includes('详细')){
            var input=items[i].querySelector('input');
            if(input)input.click();
            return 'clicked';
        }
    }
})()""")
print(f"  {r1}")
time.sleep(2)

# Step 2: 点击"广西壮族自治区"
print("\n=== Step 2: 点击广西壮族自治区 ===")
r2 = ev("""(function(){
    var popovers=document.querySelectorAll('.tne-data-picker-popover');
    for(var i=0;i<popovers.length;i++){
        var p=popovers[i];
        if(p.offsetParent===null)continue;
        var sampleItems=p.querySelectorAll('.sample-item, .item');
        for(var j=0;j<sampleItems.length;j++){
            var t=sampleItems[j].textContent?.trim()||'';
            if(t==='广西壮族自治区'){
                sampleItems[j].click();
                return {clicked:true, text:t, className:sampleItems[j].className};
            }
        }
    }
    return 'not_found';
})()""")
print(f"  结果: {r2}")
time.sleep(2)

# Step 3: 检查picker状态和第二列
print("\n=== Step 3: 检查picker状态 ===")
r3 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    
    // 检查popover中的列表
    var popovers=document.querySelectorAll('.tne-data-picker-popover');
    var popoverInfo=null;
    for(var i=0;i<popovers.length;i++){
        var p=popovers[i];
        if(p.offsetParent===null)continue;
        var sampleItems=p.querySelectorAll('.sample-item');
        var texts=[];
        for(var j=0;j<sampleItems.length;j++){
            texts.push(sampleItems[j].textContent?.trim()||'');
        }
        var tabs=p.querySelectorAll('.tab-c, .list');
        popoverInfo={sampleItemCount:sampleItems.length,texts:texts.slice(0,15),tabCount:tabs.length};
    }
    
    return {
        selected:p0?.selected,
        selectedIndex:p0?.selectedIndex,
        dataListLen:(p0?.dataList||[]).length,
        popoverInfo:popoverInfo
    };
})()""")
print(f"  {json.dumps(r3, ensure_ascii=False, indent=2)}")

# Step 4: 点击"南宁市"（如果有第二列）
print("\n=== Step 4: 点击南宁市 ===")
r4 = ev("""(function(){
    var popovers=document.querySelectorAll('.tne-data-picker-popover');
    for(var i=0;i<popovers.length;i++){
        var p=popovers[i];
        if(p.offsetParent===null)continue;
        var sampleItems=p.querySelectorAll('.sample-item');
        for(var j=0;j<sampleItems.length;j++){
            var t=sampleItems[j].textContent?.trim()||'';
            if(t==='南宁市'){
                sampleItems[j].click();
                return {clicked:true, text:t};
            }
        }
    }
    return 'not_found';
})()""")
print(f"  结果: {r4}")
time.sleep(2)

# Step 5: 点击"青秀区"
print("\n=== Step 5: 点击青秀区 ===")
r5 = ev("""(function(){
    var popovers=document.querySelectorAll('.tne-data-picker-popover');
    for(var i=0;i<popovers.length;i++){
        var p=popovers[i];
        if(p.offsetParent===null)continue;
        var sampleItems=p.querySelectorAll('.sample-item');
        for(var j=0;j<sampleItems.length;j++){
            var t=sampleItems[j].textContent?.trim()||'';
            if(t==='青秀区'){
                sampleItems[j].click();
                return {clicked:true, text:t};
            }
        }
    }
    return 'not_found';
})()""")
print(f"  结果: {r5}")
time.sleep(2)

# Step 6: 验证
print("\n=== Step 6: 验证 ===")
r6 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    var form=ri.residenceForm;
    
    var items=document.querySelectorAll('.el-form-item');
    var inputVal='';
    var errorText='';
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业住所')&&!lb.textContent.includes('详细')){
            inputVal=items[i].querySelector('input')?.value||'';
            var err=items[i].querySelector('.el-form-item__error');
            errorText=err?.textContent?.trim()||'';
        }
    }
    
    return {
        inputValue:inputVal,
        error:errorText,
        selected:p0?.selected,
        modelValue:p0?.$props?.modelValue,
        formDistCode:form?.distCode,
        formDistCodeName:form?.distCodeName,
        formProvinceCode:form?.provinceCode,
        formProvinceName:form?.provinceName,
        formCityCode:form?.cityCode,
        formCityName:form?.cityName,
        formIsSelectDistCode:form?.isSelectDistCode
    };
})()""")
print(f"  {json.dumps(r6, ensure_ascii=False, indent=2)}")

ws.close()
