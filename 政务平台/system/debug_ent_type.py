#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查找企业类型等缺失字段的组件和选项"""
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

# 查找所有form-item的label和组件类型
r = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(!lb)continue;
        var text=lb.textContent.trim();
        // 找关键缺失字段
        if(text.includes('企业类型')||text.includes('核算方式')||text.includes('经营期限')||
           text.includes('设立方式')||text.includes('营业执照')||text.includes('副本')||
           text.includes('登记机关')||text.includes('自贸区')){
            var comp=items[i].__vue__;
            var prop=comp?.prop||'';
            // 找内部组件
            var select=items[i].querySelector('select, .el-select, .el-radio-group, .el-input');
            var compType='';
            if(items[i].querySelector('.el-select'))compType='el-select';
            else if(items[i].querySelector('.el-radio-group'))compType='el-radio-group';
            else if(items[i].querySelector('.el-input'))compType='el-input';
            else if(items[i].querySelector('select'))compType='native-select';
            
            // 获取当前值
            var val='';
            var sel=items[i].querySelector('.el-select');
            if(sel){
                var sv=sel.__vue__;
                val=sv?.value||sv?.selectedLabel||'';
            }
            var radio=items[i].querySelector('.el-radio-group');
            if(radio){
                var rv=radio.__vue__;
                val=rv?.value||rv?.$props?.value||'';
            }
            var inp=items[i].querySelector('input');
            if(inp&&!sel&&!radio)val=inp.value||'';
            
            result.push({label:text,prop:prop,compType:compType,value:val});
        }
    }
    return result;
})()""")
print("=== 缺失字段 ===")
for f in (r or []):
    print(f"  {f['label']}: type={f['compType']}, prop={f['prop']}, value='{f['value']}'")

# 查bdi中企业类型相关字段
r2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var fc=find(vm,0);
    var bdi=fc?.$data?.businessDataInfo||{};
    var keys=['entType','entTypeName','accountType','accountTypeName','setWay','setWayName',
              'busiPeriod','busiDateStart','busiDateEnd','licenseRadio','copyCerNum',
              'organize','businessModeGT','secretaryServiceEnt','namePreFlag',
              'moneyKindCode','moneyKindName','subCapital'];
    var result={};
    for(var i=0;i<keys.length;i++){
        result[keys[i]]=bdi[keys[i]];
    }
    return result;
})()""")
print("\n=== bdi关键字段 ===")
for k,v in (r2 or {}).items():
    print(f"  {k}: {v}")

# 查企业类型的select选项
r3 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业类型')){
            var sel=items[i].querySelector('.el-select');
            if(sel){
                var sv=sel.__vue__;
                var opts=sv?.options||sv?.$children||[];
                var optList=[];
                for(var j=0;j<opts.length;j++){
                    var o=opts[j];
                    if(o.label||o.$props?.label){
                        optList.push({value:o.value||o.$props?.value,label:o.label||o.$props?.label});
                    }
                }
                // 也查dropdown
                var dropdown=items[i].querySelector('.el-select-dropdown__item');
                return {type:'el-select',optionCount:optList.length,options:optList.slice(0,10),
                        currentValue:sv?.value,selectedLabel:sv?.selectedLabel,
                        hasDropdown:!!dropdown};
            }
            var radio=items[i].querySelector('.el-radio-group');
            if(radio){
                var radios=items[i].querySelectorAll('.el-radio');
                var rList=[];
                for(var j=0;j<radios.length;j++){
                    rList.push(radios[j].textContent?.trim()||'');
                }
                return {type:'el-radio-group',radios:rList,value:radio.__vue__?.value};
            }
            return {type:'unknown'};
        }
    }
    return 'not_found';
})()""")
print(f"\n=== 企业类型组件 ===")
print(json.dumps(r3, ensure_ascii=False, indent=2))

ws.close()
