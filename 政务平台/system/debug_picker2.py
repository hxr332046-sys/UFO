#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试生产经营地址的tne-data-picker"""
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

# 1. 检查两个picker的当前状态
r1 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return 'no_ri';
    
    var pickers=[];
    function scan(vm,d){
        if(d>12)return;
        if(vm.$options?.name==='tne-data-picker')pickers.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1);
    }
    scan(ri,0);
    
    var result=[];
    for(var i=0;i<pickers.length;i++){
        var p=pickers[i];
        result.push({
            idx:i,
            selected:p.selected,
            selectedIndex:p.selectedIndex,
            inputSelected:p.inputSelected,
            checkValue:p.checkValue,
            dataListLen:(p.dataList||[]).length,
            isOpened:p.isOpened,
            inputValue:p.$el?.querySelector('input')?.value||'',
            title:p.$props?.title||'',
            requiredLevel:p.$props?.requiredSelectedLevel,
            props_value:p.$props?.props?.value,
            props_text:p.$props?.props?.text,
            props_children:p.$props?.props?.children
        });
    }
    
    // residenceForm状态
    var form=ri.residenceForm||ri.$data?.residenceForm;
    var formState={
        distCode:form?.distCode||'',
        distCodeName:form?.distCodeName||'',
        fisDistCode:form?.fisDistCode||'',
        provinceCode:form?.provinceCode||'',
        cityCode:form?.cityCode||'',
        isSelectDistCode:form?.isSelectDistCode||'',
        detAddress:form?.detAddress||'',
        detBusinessAddress:form?.detBusinessAddress||''
    };
    
    return {pickers:result, formState:formState};
})()""")

print("=== PICKER STATE ===")
print(json.dumps(r1, ensure_ascii=False, indent=2))

# 2. 尝试用getNodeData设置第二个picker
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
    
    var picker2=pickers[1];
    if(!picker2)return 'no_picker2';
    
    // 设置selected
    picker2.selected=[
        {value:'450000',text:'广西壮族自治区'},
        {value:'450100',text:'南宁市'},
        {value:'450103',text:'青秀区'}
    ];
    picker2.selectedIndex=2;
    picker2.inputSelected=picker2.selected;
    picker2.checkValue=['450000','450100','450103'];
    
    // 设置residenceForm
    var form=ri.residenceForm||ri.$data?.residenceForm;
    ri.$set(form,'fisDistCode','450103');
    ri.$set(form,'detBusinessAddress','民大道100号');
    
    // 尝试调用方法
    try{picker2.updateBindData()}catch(e){}
    try{picker2.updateSelected()}catch(e){}
    
    ri.$forceUpdate();
    picker2.$forceUpdate();
    
    return {
        selected:picker2.selected,
        inputValue:picker2.$el?.querySelector('input')?.value||'',
        fisDistCode:form?.fisDistCode||''
    };
})()""")

print("\n=== AFTER SET PICKER2 ===")
print(json.dumps(r2, ensure_ascii=False, indent=2))

# 3. 检查验证错误
r3 = ev("""(function(){
    var msgs=document.querySelectorAll('.el-form-item__error');
    var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}
    return r;
})()""")
print(f"\n验证错误: {r3}")

# 4. 如果还有生产经营地址错误，尝试点击保存看看
r4 = ev("""(function(){
    window.__save_result=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||'',body:body?.substring(0,500)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    
    // 调用save
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var comp=find(vm,0);
    if(comp){try{comp.save(null,null,'working');return 'save_called'}catch(e){return 'error:'+e.message}}
    return 'no_comp';
})()""", timeout=15)

print(f"\n保存: {r4}")

import time; time.sleep(8)

r5 = ev("window.__save_result")
if r5:
    print(f"API status={r5.get('status')}")
    try:
        p = json.loads(r5.get('resp', '{}'))
        print(f"code={p.get('code','')} msg={p.get('msg','')[:60]}")
    except:
        print(f"raw: {r5.get('resp','')[:200]}")
else:
    errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}return r})()""")
    print(f"无API响应, 验证: {errs}")

ws.close()
