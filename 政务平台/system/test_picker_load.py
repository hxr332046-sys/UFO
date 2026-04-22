#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""触发picker数据加载后测试原生点击"""
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

# 找picker并触发数据加载
print("\n=== Step 1: 触发picker数据加载 ===")
r1 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    if(!p0)return 'no_picker';
    
    // 触发数据加载
    try{p0.loadData()}catch(e){return 'loadError:'+e.message}
    
    return {
        dataListLen:(p0.dataList||[]).length,
        treeDataLen:(p0.treeData||[]).length,
        selectedLen:(p0.selected||[]).length,
        isOpened:p0.isOpened
    };
})()""")
print(f"  加载后: {r1}")
time.sleep(2)

# 检查dataList内容
print("\n=== Step 2: 检查dataList ===")
r2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    var dl=p0.dataList||[];
    var result=[];
    for(var i=0;i<dl.length;i++){
        var level=dl[i]||[];
        var items=[];
        for(var j=0;j<Math.min(level.length,5);j++){
            items.push({name:level[j]?.name||'',value:level[j]?.uniqueId||level[j]?.value||'',isLeaf:level[j]?.isLeaf||false});
        }
        result.push({level:i,count:level.length,sample:items});
    }
    return result;
})()""")
print(f"  dataList: {json.dumps(r2, ensure_ascii=False, indent=2)}")

# 打开picker popover
print("\n=== Step 3: 打开picker ===")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业住所')&&!lb.textContent.includes('详细')){
            var input=items[i].querySelector('input');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)

# 检查popover中的列表项
print("\n=== Step 4: 检查popover列表项 ===")
r4 = ev("""(function(){
    var popovers=document.querySelectorAll('.tne-data-picker-popover');
    for(var i=0;i<popovers.length;i++){
        var p=popovers[i];
        if(p.offsetParent===null)continue;
        // 找所有可点击项
        var allItems=p.querySelectorAll('li, [class*="item"], [class*="option"]');
        var itemTexts=[];
        for(var j=0;j<allItems.length;j++){
            itemTexts.push(allItems[j].textContent?.trim()?.substring(0,30)||'');
        }
        // 找scrollbar内容
        var wraps=p.querySelectorAll('.el-scrollbar__wrap');
        var wrapHTML=[];
        for(var j=0;j<wraps.length;j++){
            wrapHTML.push(wraps[j].innerHTML?.substring(0,300)||'empty');
        }
        return {itemCount:allItems.length, itemTexts:itemTexts.slice(0,10), wrapCount:wraps.length, wrapHTML:wrapHTML};
    }
    return 'no_visible_popover';
})()""")
print(f"  popover内容: {json.dumps(r4, ensure_ascii=False, indent=2)}")

# 如果列表为空，尝试直接点击treeData中的项
print("\n=== Step 5: 尝试通过Vue方法选择 ===")
r5 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    if(!p0)return 'no_picker';
    
    // 设置selected并调用updateBindData
    p0.selected=[
        {value:'450000',text:'广西壮族自治区'},
        {value:'450100',text:'南宁市'},
        {value:'450103',text:'青秀区'}
    ];
    p0.selectedIndex=2;
    
    // 调用updateBindData来同步dataList
    try{p0.updateBindData()}catch(e){}
    try{p0.updateSelected()}catch(e){}
    
    // 设置inputSelected
    p0.inputSelected=JSON.parse(JSON.stringify(p0.selected));
    p0.checkValue=['450000','450100','450103'];
    
    // 关键：触发picker的change事件，让父组件(residence-information)更新residenceForm
    p0.$emit('input', ['450000','450100','450103']);
    p0.$emit('change', p0.selected);
    
    p0.$forceUpdate();
    ri.$forceUpdate();
    
    // 检查residenceForm是否更新
    var form=ri.residenceForm;
    return {
        selected:p0.selected,
        inputValue:p0.$el?.querySelector('input')?.value||'',
        formDistCode:form?.distCode,
        formDistCodeName:form?.distCodeName,
        formProvinceCode:form?.provinceCode,
        modelValue:p0.$props?.modelValue
    };
})()""")
print(f"  Vue选择后: {json.dumps(r5, ensure_ascii=False, indent=2)}")

# 检查验证
time.sleep(2)
errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}return r})()""")
print(f"\n验证错误: {errs}")

ws.close()
