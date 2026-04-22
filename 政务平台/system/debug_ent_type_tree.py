#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查找企业类型tne-select-tree的选项和交互方式"""
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

# 1. 找企业类型的tne-select-tree组件
print("=== 企业类型 tne-select-tree ===")
r1 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'basic-info',0)||findComp(vm,'index',0);
    if(!fc)return 'no_fc';
    
    // 找所有tne-select-tree
    var trees=[];
    function scan(vm,d){
        if(d>12)return;
        if(vm.$options?.name==='tne-select-tree')trees.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1);
    }
    scan(fc,0);
    
    var result=[];
    for(var i=0;i<trees.length;i++){
        var t=trees[i];
        var props=t.$props||{};
        var data=t.$data||{};
        // 找placeholder区分是哪个tree
        var ph=props.placeholder||'';
        var valId=t.valueId||data.valueId||'';
        var valTitle=t.valueTitle||data.valueTitle||'';
        
        // 获取tree data
        var treeData=props.data||data.treeData||[];
        var roots=[];
        for(var j=0;j<Math.min(treeData.length,5);j++){
            roots.push({code:treeData[j]?.code||'',name:treeData[j]?.name||'',label:treeData[j]?.label||''});
        }
        
        result.push({
            idx:i,
            placeholder:ph,
            valueId:valId,
            valueTitle:valTitle,
            treeDataLen:treeData.length,
            roots:roots,
            onlyLeaf:props.onlyLeaf,
            filter:props.filter
        });
    }
    return result;
})()""", timeout=20)
print(json.dumps(r1, ensure_ascii=False, indent=2))

# 2. 点击企业类型input打开下拉
print("\n=== 点击企业类型input ===")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业类型')){
            var input=items[i].querySelector('input');
            if(input)input.click();
            return 'clicked';
        }
    }
})()""")
time.sleep(3)

# 3. 查看下拉面板内容
print("\n=== 下拉面板内容 ===")
r3 = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown, .el-popper');
    for(var i=0;i<dropdowns.length;i++){
        var d=dropdowns[i];
        if(d.offsetParent===null)continue;
        // 找tree节点
        var nodes=d.querySelectorAll('.el-tree-node__content, .tree-node');
        var nodeTexts=[];
        for(var j=0;j<Math.min(nodes.length,15);j++){
            nodeTexts.push(nodes[j].textContent?.trim()?.substring(0,40)||'');
        }
        if(nodeTexts.length>0){
            return {nodeCount:nodes.length, sampleNodes:nodeTexts};
        }
    }
    return 'no_visible_dropdown';
})()""")
print(json.dumps(r3, ensure_ascii=False, indent=2))

# 4. 查bdi中entType相关
r4 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var fc=find(vm,0);
    var bdi=fc.$data.businessDataInfo;
    return {
        entType:bdi.entType,
        entTypeName:bdi.entTypeName,
        entBaseInfo_entType:bdi.entBaseInfo?.entType,
        entBaseInfo_entTypeName:bdi.entBaseInfo?.entTypeName
    };
})()""")
print(f"\nbdi.entType: {r4}")

ws.close()
