#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航回设立登记表单"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=8)
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
# Step 1: 检查当前状态
# ============================================================
print("Step 1: 当前状态")
cur = ev("({hash:location.hash,url:location.href})")
print(f"  {cur}")

# ============================================================
# Step 2: 检查Vue Router可用路由
# ============================================================
print("\nStep 2: Vue Router路由")
routes = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    var router=vm.$router;
    if(!router)return 'no_router';
    var r=router.options?.routes||[];
    var names=[];
    for(var i=0;i<r.length;i++){
        if(r[i].path&&r[i].path.includes('flow'))names.push(r[i].path);
    }
    // 也检查currentRoute
    var cur=router.currentRoute?.path||router.history?.current?.path||'';
    return{flowRoutes:names.slice(0,10),currentRoute:cur};
})()""")
print(f"  routes: {routes}")

# ============================================================
# Step 3: 通过完整URL导航
# ============================================================
print("\nStep 3: 通过完整URL导航")

# 先回到入口页
ev("""window.location.href='https://zhjg.scjdgjlj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page?fromProject=name-register&fromPage=%2Fnamenot'""")
time.sleep(5)

cur = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  入口页: {cur}")

# ============================================================
# Step 4: 找设立登记入口并点击
# ============================================================
print("\nStep 4: 找设立登记入口")

# 检查页面内容
page_info = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,a,[class*="btn"]');
    var links=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('设立')||t.includes('登记')||t.includes('名称')){
            links.push({idx:i,text:t.substring(0,30),tag:btns[i].tagName,href:btns[i].href||''});
        }
    }
    // 也检查router-link
    var rls=document.querySelectorAll('[class*="router-link"],a');
    for(var i=0;i<rls.length;i++){
        var t=rls[i].textContent?.trim()||'';
        if(t.includes('设立')||t.includes('登记')){
            links.push({idx:i,text:t.substring(0,30),tag:'a',href:rls[i].href||''});
        }
    }
    return{links:links,pageTitle:document.title};
})()""")
print(f"  页面: {page_info}")

# ============================================================
# Step 5: 检查是否有已保存的草稿
# ============================================================
print("\nStep 5: 检查草稿")
draft_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    if(comp)return{found:true,hash:location.hash};
    return{found:false};
})()""")
print(f"  草稿: {draft_info}")

# 如果已经在表单页面
if isinstance(draft_info, dict) and draft_info.get('found'):
    print("  已在表单页面!")
else:
    # 尝试直接导航到core.html
    print("  尝试core.html路由...")
    ev("""window.location.href='https://zhjg.scjdgjlj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info'""")
    time.sleep(5)
    
    cur = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  core.html: {cur}")
    
    if (cur or {}).get('formCount', 0) == 0:
        # 尝试portal.html
        ev("""window.location.href='https://zhjg.scjdgjlj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/flow/base/basic-info'""")
        time.sleep(5)
        cur = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  portal: {cur}")

print("\n✅ 完成")
