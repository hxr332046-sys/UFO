#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断当前页面Vue组件结构"""
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

# 基本状态
cur = ev("({hash:location.hash,forms:document.querySelectorAll('.el-form-item').length})")
print(f"页面: {cur}")

# 搜索所有Vue组件名
all_comps = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    if(!vm)return'no_vue';
    function walk(vm,d,path){
        if(d>8)return[];
        var name=vm.$options?.name||'';
        var r=[];
        if(name)r.push({name:name,path:path,d:d});
        for(var i=0;i<(vm.$children||[]).length;i++){
            r=r.concat(walk(vm.$children[i],d+1,path+'/'+i));
        }
        return r;
    }
    var all=walk(vm,0,'root');
    // 过滤出有意义的组件
    return all.filter(function(c){
        return c.name&&!c.name.startsWith('El')&&c.name!=='transition'&&c.name!=='Transition';
    }).slice(0,30);
})()""")
print(f"\n关键组件:")
if isinstance(all_comps, list):
    for c in all_comps:
        print(f"  {c['name']} path={c['path']} depth={c['d']}")

# 检查businessDataInfo
bdi = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return{found:false};
    var b=comp.$data.businessDataInfo;
    return{found:true,keys:Object.keys(b).length,entName:b.entName||'',distCode:b.distCode||'',itemIndustryTypeCode:b.itemIndustryTypeCode||''};
})()""")
print(f"\nbusinessDataInfo: {bdi}")

# 检查表单标签
form_labels = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var error=items[i].querySelector('.el-form-item__error')?.textContent?.trim()||'';
        if(label)r.push({label:label.substring(0,15),error:error.substring(0,20)});
    }
    return r;
})()""")
print(f"\n表单项({len(form_labels) if isinstance(form_labels,list) else '?'}):")
if isinstance(form_labels, list):
    for f in form_labels[:15]:
        err = f" ❌{f['error']}" if f.get('error') else ""
        print(f"  {f['label']}{err}")
