#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找出save()从哪些form收集数据，设置缺失字段"""
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

# 1. 找出所有子组件的form数据
r1 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    
    var fc=find(vm,0);
    var ri=findComp(vm,'residence-information',0);
    var bi=findComp(vm,'businese-info',0);
    
    // busineseForm字段
    var bf=bi?.busineseForm||bi?.$data?.busineseForm||{};
    var bfKeys=Object.keys(bf);
    var bfSample={};
    for(var i=0;i<bfKeys.length;i++){
        var v=bf[bfKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')bfSample[bfKeys[i]]=v;
        else if(t==='object'&&v!==null)bfSample[bfKeys[i]]=t+':'+(Array.isArray(v)?'Array('+v.length+')':'Object('+Object.keys(v).length+')');
        else bfSample[bfKeys[i]]=t+':'+String(v);
    }
    
    // fc的data中与行业类型相关的字段
    var bdi=fc?.$data?.businessDataInfo||{};
    var industryKeys=['itemIndustryTypeCode','industryTypeName','industryType','industryCode','industryId','multiIndustry','multiIndustryName','areaCategory'];
    var industryData={};
    for(var i=0;i<industryKeys.length;i++){
        industryData[industryKeys[i]]=bdi[industryKeys[i]];
    }
    
    // ri的form
    var rf=ri?.residenceForm||ri?.$data?.residenceForm||{};
    
    // fc的save方法源码（看它如何收集数据）
    var saveSrc=fc?.save?.toString()?.substring(0,800)||'no_save';
    
    // 找其他可能的form组件
    var allForms=[];
    function findForms(vm,d){
        if(d>15)return;
        var name=vm.$options?.name||'';
        if(name&&vm.$data){
            var keys=Object.keys(vm.$data);
            var formKeys=keys.filter(function(k){return k.toLowerCase().includes('form')||k.toLowerCase().includes('info')});
            if(formKeys.length>0){
                allForms.push({name:name,formKeys:formKeys});
            }
        }
        for(var i=0;i<(vm.$children||[]).length;i++)findForms(vm.$children[i],d+1);
    }
    findForms(fc,0);
    
    return {
        busineseForm:bfSample,
        industryData:industryData,
        residenceFormKeys:Object.keys(rf),
        allForms:allForms,
        saveSrc:saveSrc
    };
})()""", timeout=20)

print("=== busineseForm ===")
if r1 and not isinstance(r1, str):
    for k,v in r1.get('busineseForm',{}).items():
        print(f"  {k}: {v}")
    
    print("\n=== industryData (bdi) ===")
    for k,v in r1.get('industryData',{}).items():
        print(f"  {k}: {v}")
    
    print("\n=== allForms ===")
    for f in r1.get('allForms',[]):
        print(f"  {f['name']}: {f['formKeys']}")
    
    print("\n=== save() source ===")
    print(r1.get('saveSrc','')[:800])

ws.close()
