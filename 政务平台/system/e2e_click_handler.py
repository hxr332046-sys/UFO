#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找到下一步按钮的真实click handler并调用"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
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

# ============================================================
# Step 1: 找按钮的vnode click handler
# ============================================================
print("Step 1: 按钮vnode click handler")
handler_info = ev("""(function(){
    var all=document.querySelectorAll('button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(!t.includes('下一步'))continue;
        var vm=all[i].__vue__;
        if(!vm)continue;
        // 查看vnode
        var vnode=vm.$vnode||vm._vnode;
        var data=vnode?.data||{};
        var on=data.on||{};
        var nativeOn=data.nativeOn||{};
        // 查看componentOptions
        var compOpts=vnode?.componentOptions||{};
        var listeners=compOpts.listeners||{};
        // 查看click handler
        var clickFn=on.click||listeners.click||nativeOn.click;
        var clickSrc='';
        if(clickFn){
            if(typeof clickFn==='function')clickSrc=clickFn.toString().substring(0,300);
            else if(clickFn.fns)clickSrc=clickFn.fns.toString().substring(0,300);
        }
        // 也看$attrs
        var attrs=vm.$attrs||{};
        var attrKeys=Object.keys(attrs);
        return {
            clickSrc:clickSrc,
            onKeys:Object.keys(on),
            listenerKeys:Object.keys(listeners),
            nativeOnKeys:Object.keys(nativeOn),
            attrKeys:attrKeys.slice(0,10),
            parentName:vm.$parent?.$options?.name||''
        };
    }
    return 'no_btn';
})()""")
print(f"  {json.dumps(handler_info, ensure_ascii=False)[:500] if isinstance(handler_info,dict) else handler_info}")

# ============================================================
# Step 2: 找index组件的render函数中的下一步按钮绑定
# ============================================================
print("\nStep 2: index render函数分析")
render_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    // 找有distList的index组件
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index'){
            return vm;
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var render=comp.$options?.render;
    if(!render)return'no_render';
    var src=render.toString();
    // 找下一步相关
    var idx=src.indexOf('下一步');
    if(idx<0)idx=src.indexOf('next');
    if(idx>=0){
        return {renderLen:src.length,context:src.substring(Math.max(0,idx-200),idx+200)};
    }
    return {renderLen:src.length,noNextFound:true,srcStart:src.substring(0,300)};
})()""", timeout=15)
print(f"  {json.dumps(render_src, ensure_ascii=False)[:500] if isinstance(render_src,dict) else render_src}")

# ============================================================
# Step 3: 尝试直接通过index组件的validateEntType+提交
# ============================================================
print("\nStep 3: index组件方法调用")
methods_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    
    // 查看完整方法列表
    var methods=Object.keys(comp.$options?.methods||{});
    // 查看每个方法的源码（找包含next/submit/validate的）
    var result={};
    for(var i=0;i<methods.length;i++){
        var m=methods[i];
        var src=comp.$options.methods[m].toString();
        if(src.includes('next')||src.includes('submit')||src.includes('router')||src.includes('push')||src.includes('entType')||src.includes('busiType')){
            result[m]=src.substring(0,200);
        }
    }
    result._allMethods=methods;
    return result;
})()""")
if isinstance(methods_result, dict):
    for k,v in methods_result.items():
        if k.startswith('_'): continue
        print(f"  {k}: {v[:150]}")
    print(f"  allMethods: {methods_result.get('_allMethods',[])}")
else:
    print(f"  {methods_result}")

# ============================================================
# Step 4: 查看validateEntType源码 - 可能是下一步的入口
# ============================================================
print("\nStep 4: validateEntType源码")
validate_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var fn=comp.$options?.methods?.validateEntType;
    if(!fn)return'no_method';
    return fn.toString().substring(0,800);
})()""")
print(f"  {validate_src}")

# ============================================================
# Step 5: 查看init方法源码
# ============================================================
print("\nStep 5: init源码")
init_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var fn=comp.$options?.methods?.init;
    if(!fn)return'no_method';
    return fn.toString().substring(0,500);
})()""")
print(f"  {init_src}")

# ============================================================
# Step 6: 查看index组件的完整data
# ============================================================
print("\nStep 6: index data")
idx_data = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var d=comp.$data;
    var result={};
    Object.keys(d).forEach(function(k){
        var v=d[k];
        if(v===null||v===undefined||v===''||v===false)return;
        if(Array.isArray(v))result[k]='A['+v.length+']:'+JSON.stringify(v).substring(0,40);
        else if(typeof v==='object')result[k]=JSON.stringify(v).substring(0,60);
        else result[k]=v;
    });
    return result;
})()""")
print(f"  {json.dumps(idx_data, ensure_ascii=False)[:600] if isinstance(idx_data,dict) else idx_data}")

# ============================================================
# Step 7: 调用validateEntType
# ============================================================
print("\nStep 7: 调用validateEntType")
val_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    try{
        comp.validateEntType();
        return {called:true};
    }catch(e){
        return {error:e.message.substring(0,100)};
    }
})()""", timeout=15)
print(f"  {val_result}")
time.sleep(5)

cur = ev("location.hash")
print(f"  路由: {cur}")

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    return {flowControl:!!fc,withoutName:!!wn,hash:location.hash};
})()""")
print(f"  组件: {comps}")

print("\n✅ 完成")
