#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深入分析设立登记入口点击后的行为"""
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: all-services组件分析
# ============================================================
print("Step 1: all-services组件")
as_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_all_services';
    var methods=Object.keys(as.$options?.methods||{{}});
    var data=Object.keys(as.$data||{{}});
    // 查看data中的服务列表
    var serviceList=as.$data?.serviceList||as.$data?.menuList||as.$data?.businessList||[];
    var listLen=Array.isArray(serviceList)?serviceList.length:0;
    // 查看所有data值
    var dataVals={{}};
    for(var i=0;i<data.length;i++){{
        var v=as.$data[data[i]];
        if(Array.isArray(v))dataVals[data[i]]='A['+v.length+']';
        else if(typeof v==='object'&&v!==null)dataVals[data[i]]='O:'+Object.keys(v).length;
        else dataVals[data[i]]=v;
    }}
    return{{methods:methods,dataVals:dataVals,serviceListLen:listLen}};
}})()""")
print(f"  {as_info}")

# ============================================================
# Step 2: 查看all-services的方法源码
# ============================================================
print("\nStep 2: 关键方法源码")
for method_name in ['handleClick', 'goToService', 'goTo', 'toService', 'clickMenu', 'selectService', 'handleSelect']:
    src = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var as=findComp(vm,'all-services',0);
        if(!as)return'no_comp';
        var fn=as.$options?.methods?.{method_name};
        if(!fn)return'no_method';
        return fn.toString().substring(0,300);
    }})()""")
    if isinstance(src, str) and 'no_' not in src:
        print(f"  {method_name}: {src[:200]}")

# ============================================================
# Step 3: 查看sec-menu点击事件
# ============================================================
print("\nStep 3: sec-menu点击事件")
menu_info = ev("""(function(){
    var menus=document.querySelectorAll('.sec-menu');
    var result=[];
    for(var i=0;i<menus.length;i++){
        var t=menus[i].textContent?.trim()?.substring(0,30)||'';
        var events=getEventListeners(menus[i]);
        var eventTypes=Object.keys(events||{});
        result.push({text:t,events:eventTypes,clickHandlers:(events?.click||[]).length||0});
    }
    return result.slice(0,10);
})()""")
print(f"  {menu_info}")

# ============================================================
# Step 4: 查看index组件的compName
# ============================================================
print("\nStep 4: index组件状态")
idx_state = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var idx=findComp(vm,'index',0);
    if(!idx)return'no_idx';
    return {{
        compName:idx.$data?.compName,
        styleMode:idx.$data?.styleMode,
        childNames:(idx.$children||[]).map(function(c){{return c.$options?.name||''}}).slice(0,10)
    }};
}})()""")
print(f"  {idx_state}")

# ============================================================
# Step 5: 点击设立登记后查看变化
# ============================================================
print("\nStep 5: 点击设立登记并观察")
# 先记录当前状态
before = ev("location.hash")
# 点击
ev("""(function(){
    var menus=document.querySelectorAll('.sec-menu');
    for(var i=0;i<menus.length;i++){
        var t=menus[i].textContent?.trim()||'';
        if(t.includes('设立登记')){
            menus[i].click();
            return 'clicked';
        }
    }
})()""")
time.sleep(2)

after = ev("location.hash")
print(f"  路由: {before} → {after}")

# 检查是否有对话框弹出
dialogs = ev("""(function(){
    var ds=document.querySelectorAll('.el-dialog,.el-drawer,.el-message-box');
    var result=[];
    for(var i=0;i<ds.length;i++){
        var visible=ds[i].style?.display!=='none'&&ds[i].offsetParent!==null;
        var t=ds[i].textContent?.trim()?.substring(0,50)||'';
        if(visible)result.push({text:t.substring(0,30),visible:visible});
    }
    return result;
})()""")
print(f"  对话框: {dialogs}")

# 检查组件变化
comps_after = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    var est=findComp(vm,'establish',0);
    var nn=findComp(vm,'namenotice',0);
    var idx=findComp(vm,'index',0);
    var as=findComp(vm,'all-services',0);
    return {{
        flowControl:!!fc,withoutName:!!wn,establish:!!est,namenotice:!!nn,
        indexCompName:idx?.$data?.compName,allServices:!!as,
        hash:location.hash
    }};
}})()""")
print(f"  组件: {comps_after}")

# ============================================================
# Step 6: 尝试直接修改compName触发组件切换
# ============================================================
print("\nStep 6: 修改compName")
comp_change = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var idx=findComp(vm,'index',0);
    if(!idx)return'no_idx';
    // 尝试切换到name-register组件
    var oldComp=idx.$data?.compName;
    idx.$set(idx.$data,'compName','name-register');
    idx.$forceUpdate();
    return {{old:oldComp,new:idx.$data?.compName}};
}})()""")
print(f"  compName切换: {comp_change}")
time.sleep(3)

comps_after2 = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    var est=findComp(vm,'establish',0);
    var idx=findComp(vm,'index',0);
    return {{flowControl:!!fc,withoutName:!!wn,establish:!!est,compName:idx?.$data?.compName,hash:location.hash}};
}})()""")
print(f"  组件: {comps_after2}")

# ============================================================
# Step 7: 尝试all-services的handleClick方法
# ============================================================
print("\nStep 7: all-services方法调用")
# 查看all-services的完整方法列表
all_methods = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_comp';
    return Object.keys(as.$options?.methods||{{}});
}})()""")
print(f"  all-services methods: {all_methods}")

# 尝试调用每个看起来相关的方法
for m in ['handleClick', 'goToService', 'toService', 'handleSelect', 'selectMenu', 'clickItem', 'goPage', 'toPage']:
    result = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var as=findComp(vm,'all-services',0);
        if(!as||!as.$options?.methods?.{m})return'no_method';
        try{{
            as.{m}({{businessModuleCode:'name-register',code:'name-register'}});
            return 'called';
        }}catch(e){{return 'err:'+e.message.substring(0,80)}}
    }})()""")
    if isinstance(result, str) and 'no_method' not in result:
        print(f"  {m}: {result}")
        time.sleep(2)
        comps = ev(f"""(function(){{
            var vm=document.getElementById('app').__vue__;
            {FC}
            var fc=findComp(vm,'flow-control',0);
            var wn=findComp(vm,'without-name',0);
            return {{flowControl:!!fc,withoutName:!!wn,hash:location.hash}};
        }})()""")
        print(f"    组件: {comps}")
        if isinstance(comps, dict) and (comps.get('flowControl') or comps.get('withoutName')):
            print("  ✅ 找到了！")
            break

print("\n✅ 完成")
