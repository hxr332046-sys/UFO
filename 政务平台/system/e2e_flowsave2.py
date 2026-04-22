#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""获取flowSave完整源码并分析router.push目标"""
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
# Step 1: flowSave完整源码
# ============================================================
print("Step 1: flowSave完整源码")
src = ev("""(function(){
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
    var fn=comp.$options?.methods?.flowSave;
    if(!fn)return'no_method';
    return fn.toString();
})()""", timeout=15)

if isinstance(src, str) and len(src) > 50:
    with open(r'g:\UFO\政务平台\data\flowSave_src.js', 'w', encoding='utf-8') as f:
        f.write(src)
    print(f"  源码长度: {len(src)}，已保存")
    
    # 找router.push
    idx = src.find('router')
    if idx >= 0:
        print(f"\n  === router上下文 (pos {idx}) ===")
        print(f"  {src[max(0,idx-50):idx+200]}")
    
    idx2 = src.find('push')
    if idx2 >= 0:
        print(f"\n  === push上下文 (pos {idx2}) ===")
        print(f"  {src[max(0,idx2-80):idx2+200]}")
    
    idx3 = src.find('name-register')
    if idx3 >= 0:
        print(f"\n  === name-register上下文 (pos {idx3}) ===")
        print(f"  {src[max(0,idx3-80):idx3+200]}")
    
    idx4 = src.find('namenot')
    if idx4 >= 0:
        print(f"\n  === namenot上下文 (pos {idx4}) ===")
        print(f"  {src[max(0,idx4-80):idx4+200]}")
    
    idx5 = src.find('validate')
    if idx5 >= 0:
        print(f"\n  === validate上下文 (pos {idx5}) ===")
        print(f"  {src[max(0,idx5-50):idx5+150]}")
else:
    print(f"  ERROR: {src}")

# ============================================================
# Step 2: fzjgFlowSave源码（分支机构流程）
# ============================================================
print("\n\nStep 2: fzjgFlowSave源码")
src2 = ev("""(function(){
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
    var fn=comp.$options?.methods?.fzjgFlowSave;
    if(!fn)return'no_method';
    return fn.toString().substring(0,500);
})()""")
print(f"  {src2[:300]}")

# ============================================================
# Step 3: 拦截router.push并调用flowSave
# ============================================================
print("\nStep 3: 拦截router.push + flowSave")
ev("""(function(){
    window.__router_push_args=[];
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router||vm.$root?.$router;
    if(!router)return'no_router';
    var origPush=router.push.bind(router);
    router.push=function(){
        window.__router_push_args.push({
            args:Array.from(arguments).map(function(a){
                if(typeof a==='string')return a;
                if(typeof a==='object')return JSON.stringify(a).substring(0,200);
                return String(a);
            })
        });
        return origPush.apply(router,arguments);
    };
    return 'intercepted';
})()""")

# 调用flowSave
save_result = ev("""(function(){
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
        comp.flowSave();
        return {called:true};
    }catch(e){
        return {error:e.message.substring(0,100)};
    }
})()""", timeout=20)
print(f"  flowSave: {save_result}")
time.sleep(5)

# 检查router.push参数
push_args = ev("window.__router_push_args")
print(f"  router.push参数: {push_args}")

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

# ============================================================
# Step 4: 如果router.push没触发，直接构造目标URL
# ============================================================
if not isinstance(push_args, list) or not push_args:
    print("\nStep 4: 直接构造目标URL")
    # 从flowSave源码分析，构造正确的URL
    # busiType从02_4变为01_4（未申请名称）
    direct_result = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        var router=vm.$router||vm.$root?.$router;
        if(!router)return'no_router';
        // 尝试各种可能的URL
        var urls=[
            '/name/namenotice?busiType=01_4&entType=1100',
            '/flow?busiType=01_4&entType=1100',
            '/name/namenotice?busiType=02_4&entType=1100',
        ];
        var results=[];
        for(var i=0;i<urls.length;i++){
            try{
                router.push(urls[i]);
                results.push({url:urls[i],pushed:true});
            }catch(e){
                results.push({url:urls[i],error:e.message.substring(0,50)});
            }
        }
        return results;
    })()""")
    print(f"  {direct_result}")
    time.sleep(3)
    
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
