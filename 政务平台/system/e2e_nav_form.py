#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从首页找到设立登记入口并导航"""
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
# Step 1: 导航到首页
# ============================================================
print("Step 1: 首页")
ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    vm.$router.push('/index/page');
})()""")
time.sleep(2)
cur = ev("location.hash")
print(f"  路由: {cur}")

# ============================================================
# Step 2: 查找首页上的所有可点击元素
# ============================================================
print("\nStep 2: 首页元素")
elements = ev("""(function(){
    var result=[];
    // 查找所有带data属性的元素
    var all=document.querySelectorAll('[data-url],[data-path],[data-code],[data-type],[data-project]');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()?.substring(0,30)||'';
        var url=all[i].dataset?.url||all[i].dataset?.path||'';
        var code=all[i].dataset?.code||all[i].dataset?.type||all[i].dataset?.project||'';
        if(t||url||code){
            result.push({text:t,url:url.substring(0,60),code:code,tag:all[i].tagName});
        }
    }
    // 也查找所有链接和按钮
    var links=document.querySelectorAll('a[href],button,.el-button,.card-item,.service-card,.grid-item');
    for(var i=0;i<links.length;i++){
        var t=links[i].textContent?.trim()?.substring(0,30)||'';
        var href=links[i].getAttribute('href')||'';
        if((t.includes('设立')||t.includes('登记')||t.includes('名称')||t.includes('内资'))&&t.length<40){
            result.push({text:t,href:href.substring(0,60),tag:links[i].tagName,cls:links[i].className?.substring(0,30)||''});
        }
    }
    return result.slice(0,20);
})()""")
if isinstance(elements, list):
    for e in elements:
        print(f"  {e}")
else:
    print(f"  {elements}")

# ============================================================
# Step 3: 查找index组件的方法和数据
# ============================================================
print("\nStep 3: index组件")
idx_info = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>10)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var idx=findComp(vm,'index',0)||findComp(vm,'page',0);
    if(!idx)return'no_index';
    var methods=Object.keys(idx.$options?.methods||{});
    var data=Object.keys(idx.$data||{});
    return {methods:methods.slice(0,20),dataKeys:data.slice(0,20),name:idx.$options?.name};
})()""")
print(f"  {idx_info}")

# ============================================================
# Step 4: 查找iframe
# ============================================================
print("\nStep 4: iframe检查")
iframes = ev("""(function(){
    var ifs=document.querySelectorAll('iframe');
    var result=[];
    for(var i=0;i<ifs.length;i++){
        result.push({src:(ifs[i].src||'').substring(0,80),id:ifs[i].id||'',name:ifs[i].name||'',visible:ifs[i].offsetParent!==null});
    }
    return result;
})()""")
print(f"  iframes: {iframes}")

# ============================================================
# Step 5: 尝试直接通过URL导航（之前成功的方式）
# ============================================================
print("\nStep 5: 尝试URL导航")
# 之前成功的URL格式
test_urls = [
    '/index/page?fromProject=name-register&fromPage=%2Fnamenot',
    '/index/page?fromProject=name-register',
]
for url in test_urls:
    ev(f"""(function(){{document.getElementById('app').__vue__.$router.push('{url}')}})()""")
    time.sleep(3)
    cur = ev("location.hash")
    print(f"  push('{url}') → {cur}")
    
    # 检查组件
    comps = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        var wn=findComp(vm,'without-name',0);
        var est=findComp(vm,'establish',0);
        var np=findComp(vm,'name-precheck',0);
        return {flowControl:!!fc,withoutName:!!wn,establish:!!est,namePrecheck:!!np};
    })()""")
    print(f"    组件: {comps}")
    
    if isinstance(comps, dict) and (comps.get('flowControl') or comps.get('withoutName') or comps.get('establish')):
        print("  ✅ 找到表单组件！")
        break

# ============================================================
# Step 6: 如果还没找到，尝试通过菜单点击
# ============================================================
if not isinstance(comps, dict) or not (comps.get('flowControl') or comps.get('withoutName') or comps.get('establish')):
    print("\nStep 6: 尝试菜单点击")
    # 回到首页
    ev("""(function(){document.getElementById('app').__vue__.$router.push('/index/page')})()""")
    time.sleep(2)
    
    # 查找并点击所有可能的入口
    click_result = ev("""(function(){
        var all=document.querySelectorAll('*');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            var rect=all[i].getBoundingClientRect();
            // 只看可见元素
            if(rect.width<10||rect.height<10)continue;
            if(t.includes('企业设立登记')||t.includes('内资公司设立')||t.includes('名称登记')){
                all[i].click();
                return {clicked:t.substring(0,30),tag:all[i].tagName};
            }
        }
        return 'no_match';
    })()""")
    print(f"  点击: {click_result}")
    time.sleep(3)
    
    cur = ev("location.hash")
    print(f"  路由: {cur}")
    
    comps = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        var wn=findComp(vm,'without-name',0);
        var est=findComp(vm,'establish',0);
        return {flowControl:!!fc,withoutName:!!wn,establish:!!est};
    })()""")
    print(f"  组件: {comps}")

print("\n✅ 完成")
