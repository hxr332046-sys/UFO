#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析tne-data-picker和tne-select-tree的方法源码和内部状态"""
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

# 1. tne-data-picker: updateSelected源码 + 内部状态
r1 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return 'no_ri';
    
    // 找tne-data-picker
    var pickers=[];
    function scan(vm,d){
        if(d>12)return;
        if(vm.$options?.name==='tne-data-picker')pickers.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1);
    }
    scan(ri,0);
    if(pickers.length===0)return 'no_picker';
    
    var picker=pickers[0];
    // 读取关键方法源码
    var methods=picker.$options?.methods||{};
    var src={};
    var keys=['updateSelected','updateBindData','loadData','loadAllData','onPropsChange','getNodeData','getTreePath'];
    for(var i=0;i<keys.length;i++){
        if(methods[keys[i]])src[keys[i]]=methods[keys[i]].toString().substring(0,500);
    }
    
    // 读取内部状态
    var data=picker.$data||{};
    var dataKeys=Object.keys(data);
    var dataSample={};
    for(var i=0;i<dataKeys.length;i++){
        var v=data[dataKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')dataSample[dataKeys[i]]=v;
        else if(t==='object'&&v!==null)dataSample[dataKeys[i]]=t+':'+(Array.isArray(v)?'Array('+v.length+')':'Object('+Object.keys(v).length+')');
        else dataSample[dataKeys[i]]=t;
    }
    
    // 读取props
    var props=picker.$props||{};
    var propKeys=Object.keys(props);
    var propSample={};
    for(var i=0;i<propKeys.length;i++){
        var v=props[propKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')propSample[propKeys[i]]=v;
        else if(t==='object'&&v!==null)propSample[propKeys[i]]=t+':'+(Array.isArray(v)?'Array('+v.length+')':'Object('+Object.keys(v).length+')');
    }
    
    return {
        pickerCount:pickers.length,
        methodsSrc:src,
        dataKeys:dataKeys,
        dataSample:dataSample,
        propKeys:propKeys,
        propSample:propSample
    };
})()""", timeout=20)

print("=== tne-data-picker 分析 ===")
if r1 and not isinstance(r1, str):
    print(f"picker数量: {r1.get('pickerCount')}")
    print("\n--- 方法源码 ---")
    for k, v in r1.get('methodsSrc', {}).items():
        print(f"\n  [{k}]:")
        print(f"  {v}")
    print("\n--- 内部状态 ---")
    for k, v in r1.get('dataSample', {}).items():
        print(f"  {k}: {v}")
    print("\n--- Props ---")
    for k, v in r1.get('propSample', {}).items():
        print(f"  {k}: {v}")
else:
    print(f"ERROR: {r1}")

# 2. tne-select-tree: chooseNode/onChange源码 + 内部状态
r2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return 'no_bi';
    
    function findTreeSelect(vm,d){
        if(d>12)return null;
        if(vm.$options?.name==='tne-select-tree')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findTreeSelect(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var treeComp=findTreeSelect(bi,0);
    if(!treeComp)return 'no_tree_comp';
    
    // 读取关键方法源码
    var methods=treeComp.$options?.methods||{};
    var src={};
    var keys=['chooseNode','onChange','handleNodeClick','dropdownHandle','filterNode','clearHandle','initView','initTreeView'];
    for(var i=0;i<keys.length;i++){
        if(methods[keys[i]])src[keys[i]]=methods[keys[i]].toString().substring(0,600);
    }
    
    // 读取内部状态
    var data=treeComp.$data||{};
    var dataKeys=Object.keys(data);
    var dataSample={};
    for(var i=0;i<dataKeys.length;i++){
        var v=data[dataKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')dataSample[dataKeys[i]]=v;
        else if(t==='object'&&v!==null)dataSample[dataKeys[i]]=t+':'+(Array.isArray(v)?'Array('+v.length+')':'Object('+Object.keys(v).length+')');
        else dataSample[dataKeys[i]]=t;
    }
    
    // 读取props
    var props=treeComp.$props||{};
    var propKeys=Object.keys(props);
    var propSample={};
    for(var i=0;i<propKeys.length;i++){
        var v=props[propKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')propSample[propKeys[i]]=v;
        else if(t==='object'&&v!==null)propSample[propKeys[i]]=t+':'+(Array.isArray(v)?'Array('+v.length+')':'Object('+Object.keys(v).length+')');
    }
    
    return {
        methodsSrc:src,
        dataKeys:dataKeys,
        dataSample:dataSample,
        propKeys:propKeys,
        propSample:propSample
    };
})()""", timeout=20)

print("\n\n=== tne-select-tree 分析 ===")
if r2 and not isinstance(r2, str):
    print("\n--- 方法源码 ---")
    for k, v in r2.get('methodsSrc', {}).items():
        print(f"\n  [{k}]:")
        print(f"  {v}")
    print("\n--- 内部状态 ---")
    for k, v in r2.get('dataSample', {}).items():
        print(f"  {k}: {v}")
    print("\n--- Props ---")
    for k, v in r2.get('propSample', {}).items():
        print(f"  {k}: {v}")
else:
    print(f"ERROR: {r2}")

ws.close()
print("\n✅ 分析完成")
