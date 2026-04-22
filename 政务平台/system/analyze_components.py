#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析cascader和行业类型select组件结构"""
import json, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)

def ev(js, t=15):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": t * 1000}}))
    ws.settimeout(t + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r.get("result", {}).get("result", {}).get("value")

# 1. 分析cascader
r = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(!lb)continue;
        var t=lb.textContent.trim();
        if(t.includes('企业住所')||t.includes('生产经营地址')){
            var cas=items[i].querySelectorAll('[class*="cascader"],[class*="Cascader"]');
            var casInfo=[];
            for(var j=0;j<cas.length;j++){
                var el=cas[j];
                var comp=el.__vue__;
                casInfo.push({
                    tag:el.tagName,
                    cls:el.className?.substring(0,100),
                    compName:comp?comp.$options?.name:'no_vue',
                    methods:comp?Object.keys(comp.$options?.methods||{}).filter(function(m){return !m.startsWith('_')}).slice(0,20):[],
                    inputValue:el.querySelector('input')?.value||'',
                    childCount:comp?comp.$children.length:0
                });
            }
            result.push({label:t.replace(/:$/,''),casCount:cas.length,casInfo:casInfo});
        }
    }
    return result;
})()""")
print("=== CASADER ANALYSIS ===")
print(json.dumps(r, ensure_ascii=False, indent=2))

# 2. 分析行业类型select
r2 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(!lb)continue;
        if(lb.textContent.trim().includes('行业类型')){
            var sel=items[i].querySelectorAll('.el-select,[class*="tne-select"]');
            var selInfo=[];
            for(var j=0;j<sel.length;j++){
                var comp=sel[j].__vue__;
                selInfo.push({
                    cls:sel[j].className?.substring(0,100),
                    compName:comp?comp.$options?.name:'no_vue',
                    methods:comp?Object.keys(comp.$options?.methods||{}).filter(function(m){return !m.startsWith('_')}).slice(0,25):[],
                    value:comp?(comp.value||comp.$data?.value||comp.$attrs?.value):'no_data',
                    inputValue:sel[j].querySelector('input')?.value||'',
                    childCount:comp?comp.$children.length:0
                });
            }
            return {label:'行业类型',selInfo:selInfo};
        }
    }
})()""")
print("\n=== INDUSTRY SELECT ANALYSIS ===")
print(json.dumps(r2, ensure_ascii=False, indent=2))

# 3. 深入分析residence-information的cascader子组件
r3 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return 'no_ri';
    
    // 遍历子组件找cascader相关
    var found=[];
    function scan(vm,d,path){
        if(d>12)return;
        var name=vm.$options?.name||'';
        var cls=vm.$el?.className||'';
        if(name.toLowerCase().includes('cascader')||cls.includes('cascader')||cls.includes('Cascader')){
            found.push({
                depth:d,
                name:name,
                cls:cls.substring(0,80),
                path:path,
                methods:Object.keys(vm.$options?.methods||{}).filter(function(m){return !m.startsWith('_')}).slice(0,15),
                value:vm.value||vm.$data?.value||vm.$attrs?.value||'',
                inputValue:vm.$el?.querySelector('input')?.value||''
            });
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            scan(vm.$children[i],d+1,path+'>'+i);
        }
    }
    scan(ri,0,'ri');
    return found;
})()""")
print("\n=== RESIDENCE CASCADER SUB-COMPONENTS ===")
print(json.dumps(r3, ensure_ascii=False, indent=2))

# 4. 深入分析行业类型select子组件
r4 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return 'no_bi';
    
    var found=[];
    function scan(vm,d,path){
        if(d>12)return;
        var name=vm.$options?.name||'';
        var cls=vm.$el?.className||'';
        if(name.toLowerCase().includes('select')||name.toLowerCase().includes('tree')||cls.includes('tne-select')){
            found.push({
                depth:d,
                name:name,
                cls:cls.substring(0,80),
                path:path,
                methods:Object.keys(vm.$options?.methods||{}).filter(function(m){return !m.startsWith('_')}).slice(0,20),
                value:vm.value||vm.$data?.value||vm.$attrs?.value||'',
                inputValue:vm.$el?.querySelector('input')?.value||''
            });
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            scan(vm.$children[i],d+1,path+'>'+i);
        }
    }
    scan(bi,0,'bi');
    return found;
})()""")
print("\n=== BUSINESS SELECT SUB-COMPONENTS ===")
print(json.dumps(r4, ensure_ascii=False, indent=2))

ws.close()
print("\n✅ 分析完成")
