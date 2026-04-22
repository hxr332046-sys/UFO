#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析下一步按钮的处理逻辑"""
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
# Step 1: 找下一步按钮的Vue组件和click handler
# ============================================================
print("Step 1: 下一步按钮分析")
btn_info = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('下一步')){
            var vm=all[i].__vue__;
            if(!vm)continue;
            // 查看vnode的事件绑定
            var vnode=vm.$vnode||vm._vnode;
            var listeners=vnode?.data?.on||vm.$listeners||{};
            var clickHandler=listeners.click||vm.$attrs?.click;
            // 向上找有handleNext/nextBtn方法的父组件
            var parent=vm.$parent;
            var found={};
            while(parent){
                var methods=Object.keys(parent.$options?.methods||{});
                var nextMethods=methods.filter(function(m){return m.includes('next')||m.includes('Next')||m.includes('submit')||m.includes('Submit')||m.includes('handle')});
                if(nextMethods.length>0){
                    found={parentName:parent.$options?.name,methods:nextMethods};
                    break;
                }
                parent=parent.$parent;
            }
            return {
                btnName:vm.$options?.name,
                btnText:t,
                btnDisabled:all[i].disabled,
                parentInfo:found,
                hasClickHandler:!!clickHandler,
                listeners:Object.keys(listeners)
            };
        }
    }
    return 'no_btn';
})()""")
print(f"  {btn_info}")

# ============================================================
# Step 2: 找guide页面组件的next/handleNext方法源码
# ============================================================
print("\nStep 2: next方法源码")
# 找ElCard的父组件
next_src = ev("""(function(){
    var card=document.querySelector('.el-card');
    if(!card)return'no_card';
    var vm=card.__vue__;
    // 向上找有next相关方法的组件
    var parent=vm;
    while(parent){
        var methods=parent.$options?.methods||{};
        var names=Object.keys(methods);
        for(var i=0;i<names.length;i++){
            var n=names[i];
            if(n.includes('next')||n.includes('Next')||n.includes('submit')||n.includes('Submit')||n.includes('handleNext')){
                return {name:n,src:methods[n].toString().substring(0,500),parentName:parent.$options?.name};
            }
        }
        parent=parent.$parent;
    }
    return 'no_next_method';
})()""")
print(f"  {json.dumps(next_src, ensure_ascii=False)[:400] if isinstance(next_src,dict) else next_src}")

# ============================================================
# Step 3: 找所有有next相关方法的组件
# ============================================================
print("\nStep 3: 所有next方法")
all_next = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var result=[];
    function walk(vm,d){
        if(d>12)return;
        var methods=vm.$options?.methods||{};
        var names=Object.keys(methods);
        for(var i=0;i<names.length;i++){
            var n=names[i];
            if(n.includes('next')||n.includes('Next')||n.includes('submit')||n.includes('Submit')||n.includes('handleNext')||n.includes('toNotName')){
                result.push({name:vm.$options?.name||'',method:n,src:methods[n].toString().substring(0,200)});
            }
        }
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }
    walk(vm,0);
    return result;
})()""")
if isinstance(all_next, list):
    for a in all_next:
        print(f"  {a.get('name','')}.{a.get('method','')}: {a.get('src','')[:150]}")
else:
    print(f"  {all_next}")

# ============================================================
# Step 4: 找到guide页面的实际组件实例
# ============================================================
print("\nStep 4: guide组件实例")
guide_vm = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    // 找有distList属性的组件
    var result=[];
    function walk(vm,d){
        if(d>12)return;
        var data=vm.$data||{};
        if(data.distList!==undefined){
            result.push({
                name:vm.$options?.name||'',
                d:d,
                distList:JSON.stringify(data.distList).substring(0,60),
                methods:Object.keys(vm.$options?.methods||{}).slice(0,15)
            });
        }
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }
    walk(vm,0);
    return result;
})()""")
print(f"  {json.dumps(guide_vm, ensure_ascii=False)[:500] if isinstance(guide_vm,list) else guide_vm}")

# ============================================================
# Step 5: 调用找到的next方法
# ============================================================
print("\nStep 5: 调用next方法")
if isinstance(guide_vm, list) and guide_vm:
    comp_name = guide_vm[0].get('name','')
    methods = guide_vm[0].get('methods',[])
    next_methods = [m for m in methods if 'next' in m.lower() or 'submit' in m.lower() or 'handle' in m.lower()]
    print(f"  组件: {comp_name}, next方法: {next_methods}")
    
    for m in next_methods:
        call_result = ev(f"""(function(){{
            var vm=document.getElementById('app').__vue__;
            function findComp(vm,name,d){{if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var comp=findComp(vm,'{comp_name}',0);
            if(!comp)return'no_comp';
            try{{
                comp.{m}();
                return {{called:true,method:'{m}'}};
            }}catch(e){{
                return {{error:e.message.substring(0,80),method:'{m}'}};
            }}
        }})()""")
        print(f"  {m}: {call_result}")
        time.sleep(3)
        
        cur = ev("location.hash")
        print(f"    路由: {cur}")
        
        comps = ev("""(function(){
            var vm=document.getElementById('app').__vue__;
            function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var fc=findComp(vm,'flow-control',0);
            var wn=findComp(vm,'without-name',0);
            return {flowControl:!!fc,withoutName:!!wn};
        })()""")
        if isinstance(comps, dict) and (comps.get('flowControl') or comps.get('withoutName')):
            print("    ✅ 到达表单！")
            break

print("\n✅ 完成")
