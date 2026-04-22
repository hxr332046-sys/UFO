#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析save事件流: flow-save-basic-info如何收集子组件数据"""
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: 分析basic-info组件的save事件处理
# ============================================================
print("Step 1: basic-info save事件")
bi_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return{{error:'no_bi'}};
    // 搜索flow-save相关方法
    var methods=Object.keys(bi.$options?.methods||{{}});
    var created=bi.$options?.created?.toString()?.substring(0,300)||'';
    var mounted=bi.$options?.mounted?.toString()?.substring(0,300)||'';
    // 找$on('flow-save')的监听
    var listeners=bi._events||{{}};
    var listenerKeys=Object.keys(listeners);
    return{{methods:methods,created:created,mounted:mounted,listenerKeys:listenerKeys.slice(0,20)}};
}})()""")
print(f"  basic-info: {json.dumps(bi_src, ensure_ascii=False)[:400] if isinstance(bi_src,dict) else bi_src}")

# ============================================================
# Step 2: 分析index组件(root/0/0/1/0/4/0/0)的save处理
# ============================================================
print("\nStep 2: index组件save处理")
idx_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var idx=findComp(vm,'index',0);
    if(!idx)return{{error:'no_idx'}};
    var methods=Object.keys(idx.$options?.methods||{{}});
    // 找flow-save相关
    var saveRelated=methods.filter(function(m){{return m.includes('save')||m.includes('Save')}});
    var listeners=idx._events||{{}};
    var listenerKeys=Object.keys(listeners);
    return{{methods:methods.slice(0,20),saveRelated:saveRelated,listenerKeys:listenerKeys.slice(0,20)}};
}})()""")
print(f"  index: {json.dumps(idx_src, ensure_ascii=False)[:400] if isinstance(idx_src,dict) else idx_src}")

# ============================================================
# Step 3: 分析regist-info的save回调
# ============================================================
print("\nStep 3: regist-info save回调")
ri_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return{{error:'no_ri'}};
    var methods=Object.keys(ri.$options?.methods||{{}});
    var saveRelated=methods.filter(function(m){{return m.includes('save')||m.includes('Save')||m.includes('submit')}});
    var listeners=ri._events||{{}};
    var listenerKeys=Object.keys(listeners).filter(function(k){{return k.includes('save')}});
    return{{methods:methods.slice(0,20),saveRelated:saveRelated,saveListeners:listenerKeys}};
}})()""")
print(f"  regist-info: {json.dumps(ri_src, ensure_ascii=False)[:300] if isinstance(ri_src,dict) else ri_src}")

# ============================================================
# Step 4: 分析residence-information的save回调
# ============================================================
print("\nStep 4: residence-information save")
res_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return{{error:'no_ri'}};
    var methods=Object.keys(ri.$options?.methods||{{}});
    var saveRelated=methods.filter(function(m){{return m.includes('save')||m.includes('Save')||m.includes('submit')}});
    return{{methods:methods.slice(0,20),saveRelated:saveRelated}};
}})()""")
print(f"  residence-info: {json.dumps(res_src, ensure_ascii=False)[:300] if isinstance(res_src,dict) else res_src}")

# ============================================================
# Step 5: 拦截flow-save事件看数据流
# ============================================================
print("\nStep 5: 拦截flow-save事件")
ev("""(function(){
    window.__save_events=[];
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var origEmit=fc.eventBus.$emit;
    fc.eventBus.$emit=function(){
        var name=arguments[0]||'';
        if(name.includes('flow-save')){
            window.__save_events.push({event:name,data:JSON.stringify(arguments).substring(0,200)});
        }
        return origEmit.apply(this,arguments);
    };
})()""")

# 触发save
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{}}
}})()""", timeout=15)
time.sleep(3)

events = ev("window.__save_events")
print(f"  save事件: {events}")

# ============================================================
# Step 6: 分析regist-info的form如何被收集
# ============================================================
print("\nStep 6: regist-info form收集方式")
ri_collect = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return{{error:'no_ri'}};
    // 获取registForm完整数据
    var form=ri.registForm||ri.$data?.registForm||{{}};
    var keys=Object.keys(form);
    var nonNull=keys.filter(function(k){{return form[k]!==null&&form[k]!==undefined&&form[k]!==''}});
    return{{totalKeys:keys.length,nonNull:nonNull.length,nonNullKeys:nonNull.slice(0,20)}};
}})()""")
print(f"  registForm: {ri_collect}")

# ============================================================
# Step 7: 分析residence-information的form
# ============================================================
print("\nStep 7: residence-information form")
res_form = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return{{error:'no_ri'}};
    var form=ri.residenceForm||ri.$data?.residenceForm||{{}};
    var keys=Object.keys(form);
    var nonNull=keys.filter(function(k){{return form[k]!==null&&form[k]!==undefined&&form[k]!==''}});
    return{{totalKeys:keys.length,nonNull:nonNull.length,nonNullKeys:nonNull.slice(0,20)}};
}})()""")
print(f"  residenceForm: {res_form}")

print("\n✅ 完成")
