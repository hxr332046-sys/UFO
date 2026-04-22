#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析guide/base页面，找到进入flow-control的路径"""
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
# Step 1: 当前页面状态
# ============================================================
print("Step 1: 页面状态")
page_state = ev("""(function(){
    return {
        hash:location.hash,
        title:document.title,
        bodyText:document.body?.innerText?.substring(0,300)||''
    };
})()""")
print(f"  hash: {page_state.get('hash','') if isinstance(page_state,dict) else page_state}")
if isinstance(page_state, dict):
    print(f"  text: {page_state.get('bodyText','')[:200]}")

# ============================================================
# Step 2: Vue组件树
# ============================================================
print("\nStep 2: Vue组件树")
comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function walk(vm,d,list){
        if(d>8)return list;
        var n=vm.$options?.name||'';
        if(n&&n!=='ElRow'&&n!=='ElCol'&&n!=='ElFormItem'&&n!=='ElInput'&&n!=='ElButton')list.push({name:n,d:d});
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1,list);
        return list;
    }
    return walk(vm,0,[]);
})()""")
if isinstance(comps, list):
    for c in comps[:30]:
        print(f"  {'  '*c.get('d',0)}{c.get('name','')}")
else:
    print(f"  {comps}")

# ============================================================
# Step 3: 查找guide/base组件
# ============================================================
print("\nStep 3: guide组件")
guide_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    // 尝试各种名称
    var names=['guide','guide-base','base','guideNew','guide-new','guideBase'];
    var found=null;
    for(var i=0;i<names.length;i++){{
        var c=findComp(vm,names[i],0);
        if(c){{found=c;break;}}
    }}
    if(!found)return'no_guide';
    var methods=Object.keys(found.$options?.methods||{{}});
    var data=found.$data||{{}};
    var dataKeys=Object.keys(data);
    var dataVals={{}};
    for(var i=0;i<dataKeys.length;i++){{
        var v=data[dataKeys[i]];
        if(v===null||v===undefined||v==='')continue;
        if(Array.isArray(v))dataVals[dataKeys[i]]='A['+v.length+']';
        else if(typeof v==='object')dataVals[dataKeys[i]]=JSON.stringify(v).substring(0,60);
        else dataVals[dataKeys[i]]=v;
    }}
    return {{name:found.$options?.name,methods:methods,dataVals:dataVals}};
}})()""")
print(f"  {json.dumps(guide_info, ensure_ascii=False)[:500] if isinstance(guide_info,dict) else guide_info}")

# ============================================================
# Step 4: 查找页面上的按钮
# ============================================================
print("\nStep 4: 页面按钮")
btns = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button,a');
    var result=[];
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        var visible=all[i].offsetParent!==null;
        if(t.length>0&&t.length<30&&visible){
            result.push({idx:i,text:t,disabled:all[i].disabled,cls:(all[i].className||'').substring(0,30)});
        }
    }
    return result.slice(0,15);
})()""")
if isinstance(btns, list):
    for b in btns:
        print(f"  {b}")

# ============================================================
# Step 5: 查找路由参数和query
# ============================================================
print("\nStep 5: 路由参数")
route_info = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var route=vm.$route||vm.$root?.$route;
    if(!route)return'no_route';
    return {path:route.path,query:route.query,params:route.params,name:route.name};
})()""")
print(f"  {route_info}")

# ============================================================
# Step 6: 查找页面上的链接/导航元素
# ============================================================
print("\nStep 6: 导航元素")
nav_items = ev("""(function(){
    var result=[];
    var all=document.querySelectorAll('a,button,[role=button],[role=link],.step-item,.guide-item,.next-step');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()?.substring(0,30)||'';
        var href=all[i].getAttribute('href')||all[i].dataset?.href||'';
        var onclick=all[i].getAttribute('onclick')||'';
        var visible=all[i].offsetParent!==null;
        if(visible&&(t||href)){
            result.push({text:t,href:href.substring(0,40),tag:all[i].tagName});
        }
    }
    return result.slice(0,15);
})()""")
if isinstance(nav_items, list):
    for n in nav_items:
        print(f"  {n}")

# ============================================================
# Step 7: 尝试直接导航到flow页面
# ============================================================
print("\nStep 7: 尝试导航到flow")
# 基于query参数构造flow URL
nav_attempts = [
    "/name/namenotice?busiType=02_4&entType=1100",
    "/flow/base/basic-info?busiType=02_4&entType=1100",
    "/flow?busiType=02_4&entType=1100",
]
for url in nav_attempts:
    ev(f"""(function(){{document.getElementById('app').__vue__.$router.push('{url}')}})()""")
    time.sleep(3)
    comps = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        var wn=findComp(vm,'without-name',0);
        return {{flowControl:!!fc,withoutName:!!wn,hash:location.hash}};
    }})()""")
    print(f"  push('{url}') → {comps}")
    if isinstance(comps, dict) and (comps.get('flowControl') or comps.get('withoutName')):
        print("  ✅ 找到了！")
        break

print("\n✅ 完成")
