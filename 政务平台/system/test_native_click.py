#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用原生DOM点击方式测试tne-data-picker cascader"""
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

# Step 0: 确认页面状态
page_state = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, url:location.href})")
print(f"页面状态: {page_state}")

if 'basic-info' not in str(page_state.get('hash', '')):
    print("ERROR: 不在basic-info页面！")
    ws.close()
    exit()

# Step 1: 找企业住所的tne-data-picker，点击input打开
print("\n=== Step 1: 点击企业住所input ===")
r1 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业住所')&&!lb.textContent.includes('详细')){
            // 找tne-data-picker的input
            var input=items[i].querySelector('.tne-data-picker input, [class*="data-picker"] input');
            if(input){
                input.click();
                return {clicked:true, inputValue:input.value, className:input.className};
            }
            // 备选：找任何cascader input
            var casInput=items[i].querySelector('input');
            if(casInput){
                casInput.click();
                return {clicked:true, inputValue:casInput.value, alt:true};
            }
            return {clicked:false, reason:'no_input'};
        }
    }
    return {clicked:false, reason:'no_label'};
})()""")
print(f"  结果: {r1}")
time.sleep(3)

# Step 2: 观察弹出的面板结构
print("\n=== Step 2: 观察弹出面板 ===")
r2 = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper, .tne-data-picker-popover, [class*="data-picker-popover"]');
    var result=[];
    for(var i=0;i<poppers.length;i++){
        var p=poppers[i];
        if(p.offsetParent===null&&p.style.display==='none')continue;
        var html=p.innerHTML?.substring(0,200)||'';
        var classes=p.className||'';
        var menus=p.querySelectorAll('.tne-data-picker-list, .tne-data-picker-menu, [class*="picker-list"], [class*="picker-menu"]');
        var menuInfo=[];
        for(var j=0;j<menus.length;j++){
            var items=menus[j].querySelectorAll('li, [class*="picker-item"]');
            var itemTexts=[];
            for(var k=0;k<Math.min(items.length,5);k++){
                itemTexts.push(items[k].textContent?.trim()||'');
            }
            menuInfo.push({itemCount:items.length, sampleItems:itemTexts});
        }
        result.push({visible:true, classes:classes.substring(0,80), menuCount:menus.length, menus:menuInfo});
    }
    return result;
})()""")
print(f"  面板: {json.dumps(r2, ensure_ascii=False, indent=2)}")

# Step 3: 如果面板打开了，点击第一级"广西壮族自治区"
print("\n=== Step 3: 点击第一级 ===")
r3 = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper, .tne-data-picker-popover, [class*="data-picker-popover"]');
    for(var i=0;i<poppers.length;i++){
        var p=poppers[i];
        if(p.offsetParent===null&&p.style.display==='none')continue;
        var items=p.querySelectorAll('li, [class*="picker-item"]');
        for(var j=0;j<items.length;j++){
            var t=items[j].textContent?.trim()||'';
            if(t.includes('广西')){
                items[j].click();
                return {clicked:true, text:t};
            }
        }
    }
    return {clicked:false, reason:'not_found'};
})()""")
print(f"  结果: {r3}")
time.sleep(2)

# Step 4: 点击第二级"南宁市"
print("\n=== Step 4: 点击第二级 ===")
r4 = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper, .tne-data-picker-popover, [class*="data-picker-popover"]');
    for(var i=0;i<poppers.length;i++){
        var p=poppers[i];
        if(p.offsetParent===null&&p.style.display==='none')continue;
        // 找第二列
        var menus=p.querySelectorAll('.tne-data-picker-list, [class*="picker-list"], [class*="picker-menu"]');
        if(menus.length<2)continue;
        var items=menus[1].querySelectorAll('li, [class*="picker-item"]');
        for(var j=0;j<items.length;j++){
            var t=items[j].textContent?.trim()||'';
            if(t.includes('南宁')){
                items[j].click();
                return {clicked:true, text:t};
            }
        }
    }
    return {clicked:false, reason:'not_found'};
})()""")
print(f"  结果: {r4}")
time.sleep(2)

# Step 5: 点击第三级"青秀区"
print("\n=== Step 5: 点击第三级 ===")
r5 = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper, .tne-data-picker-popover, [class*="data-picker-popover"]');
    for(var i=0;i<poppers.length;i++){
        var p=poppers[i];
        if(p.offsetParent===null&&p.style.display==='none')continue;
        var menus=p.querySelectorAll('.tne-data-picker-list, [class*="picker-list"], [class*="picker-menu"]');
        if(menus.length<3)continue;
        var items=menus[2].querySelectorAll('li, [class*="picker-item"]');
        for(var j=0;j<items.length;j++){
            var t=items[j].textContent?.trim()||'';
            if(t.includes('青秀')){
                items[j].click();
                return {clicked:true, text:t};
            }
        }
    }
    return {clicked:false, reason:'not_found'};
})()""")
print(f"  结果: {r5}")
time.sleep(2)

# Step 6: 验证结果
print("\n=== Step 6: 验证 ===")
r6 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业住所')&&!lb.textContent.includes('详细')){
            var input=items[i].querySelector('input');
            var error=items[i].querySelector('.el-form-item__error');
            return {
                inputValue:input?.value||'',
                error:error?.textContent?.trim()||'',
                hasError:!!error
            };
        }
    }
})()""")
print(f"  企业住所: {r6}")

# 同时检查picker内部状态
r7 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    var form=ri.residenceForm;
    return {
        picker0_selected:p0?.selected,
        picker0_modelValue:p0?.$props?.modelValue,
        picker0_checkValue:p0?.checkValue,
        form_distCode:form?.distCode,
        form_distCodeName:form?.distCodeName,
        form_provinceCode:form?.provinceCode,
        form_isSelectDistCode:form?.isSelectDistCode
    };
})()""")
print(f"  内部状态: {json.dumps(r7, ensure_ascii=False, indent=2)}")

ws.close()
print("\n✅ 测试完成")
