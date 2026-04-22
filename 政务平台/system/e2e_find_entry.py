#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深入查找首页业务入口"""
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
# Step 1: 查看首页完整DOM结构
# ============================================================
print("Step 1: 首页DOM")
dom_info = ev("""(function(){
    var body=document.body;
    var result=[];
    // 递归查找所有可见文本
    function walk(el,d){
        if(d>8)return;
        var children=el.children;
        var text=(el.textContent||'').trim();
        var tag=el.tagName;
        var cls=el.className;
        if(typeof cls==='string')cls=cls.substring(0,30);
        var rect=el.getBoundingClientRect();
        var visible=rect.width>0&&rect.height>0;
        // 只记录有短文本的可见元素
        if(visible&&text.length>0&&text.length<40&&children.length===0){
            result.push({d:d,tag:tag,text:text.substring(0,30),cls:cls});
        }
        for(var i=0;i<children.length;i++){
            walk(children[i],d+1);
        }
    }
    walk(body,0);
    return result.slice(0,40);
})()""")
if isinstance(dom_info, list):
    for d in dom_info:
        print(f"  {'  '*d.get('d',0)}{d.get('tag','')} {d.get('text','')} [{d.get('cls','')}]")
else:
    print(f"  {dom_info}")

# ============================================================
# Step 2: 查找所有Vue组件
# ============================================================
print("\nStep 2: Vue组件树")
comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function walk(vm,d,list){
        if(d>6)return list;
        var n=vm.$options?.name||'';
        if(n)list.push({name:n,d:d,childCount:vm.$children?.length||0});
        for(var i=0;i<(vm.$children||[]).length;i++){
            walk(vm.$children[i],d+1,list);
        }
        return list;
    }
    return walk(vm,0,[]);
})()""")
if isinstance(comps, list):
    for c in comps:
        indent = '  ' * c.get('d',0)
        print(f"  {indent}{c.get('name','')} ({c.get('childCount',0)} children)")
else:
    print(f"  {comps}")

# ============================================================
# Step 3: 查找page组件的详情
# ============================================================
print("\nStep 3: page组件详情")
page_info = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var pg=findComp(vm,'page',0);
    if(!pg)return'no_page_comp';
    var data=pg.$data||{};
    var keys=Object.keys(data);
    var compName=data.compName||data.currentComp||'';
    // 查看fromProject参数
    var query=pg.$route?.query||{};
    return {dataKeys:keys.slice(0,15),compName:compName,query:query,childNames:(pg.$children||[]).map(function(c){return c.$options?.name||''}).slice(0,10)};
})()""")
print(f"  {page_info}")

# ============================================================
# Step 4: 查找selectBusinessModules API调用
# ============================================================
print("\nStep 4: 业务模块API")
biz_modules = ev("""(function(){
    // 拦截API调用
    var origFetch=window.fetch;
    window.__biz_api_calls=[];
    window.fetch=function(){
        var url=arguments[0]||'';
        if(typeof url==='string'){
            window.__biz_api_calls.push(url.substring(0,80));
        }
        return origFetch.apply(this,arguments);
    };
    
    // 调用selectBusinessModules
    var vm=document.getElementById('app').__vue__;
    var api=vm.$api;
    if(api&&api.enterprise&&api.enterprise.selectBusinessModules){
        return api.enterprise.selectBusinessModules({}).then(function(r){
            return JSON.stringify(r).substring(0,500);
        }).catch(function(e){return 'api_error:'+e.message});
    }
    return 'no_api';
})()""", timeout=15)
print(f"  modules: {biz_modules}")

# ============================================================
# Step 5: 尝试通过API获取业务模块列表
# ============================================================
print("\nStep 5: 直接fetch业务模块")
modules = ev("""(function(){
    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    return fetch('/icpsp/enterprise/selectBusinessModules',{
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
        body:JSON.stringify({})
    }).then(function(r){return r.json()}).then(function(d){
        if(d.data&&Array.isArray(d.data)){
            return d.data.map(function(m){return {code:m.businessModuleCode||m.code||'',name:m.businessModuleName||m.name||''}});
        }
        return JSON.stringify(d).substring(0,300);
    }).catch(function(e){return 'err:'+e.message});
})()""", timeout=15)
print(f"  {modules}")

# ============================================================
# Step 6: 查找首页上的服务卡片/网格
# ============================================================
print("\nStep 6: 服务卡片")
cards = ev("""(function(){
    var result=[];
    // 查找所有可能的卡片/网格项
    var selectors=['.service-card','.grid-item','.card-item','.business-item','.module-item','.el-card','.item-card','.func-item','.menu-card'];
    for(var s=0;s<selectors.length;s++){
        var els=document.querySelectorAll(selectors[s]);
        for(var i=0;i<els.length;i++){
            var t=els[i].textContent?.trim()?.substring(0,30)||'';
            if(t)result.push({sel:selectors[s],text:t});
        }
    }
    // 也查找所有带background-image的div
    var divs=document.querySelectorAll('div[style*="background"]');
    for(var i=0;i<divs.length;i++){
        var t=divs[i].textContent?.trim()?.substring(0,30)||'';
        var bg=divs[i].style?.background||'';
        if(t&&t.length<30&&bg.includes('url'))result.push({sel:'bg-div',text:t});
    }
    return result.slice(0,20);
})()""")
if isinstance(cards, list):
    for c in cards:
        print(f"  {c}")
else:
    print(f"  {cards}")

# ============================================================
# Step 7: 查看页面截图信息 (通过CDP)
# ============================================================
print("\nStep 7: 页面文本概览")
page_text = ev("""(function(){
    return document.body?.innerText?.substring(0,500)||'empty';
})()""")
print(f"  {page_text}")

print("\n✅ 完成")
