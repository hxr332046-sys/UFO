#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到表单 - 从404恢复，通过UI点击注册动态路由"""
import json, time, os, requests, websocket
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 从404回到首页（用location.href完整刷新）
print("Step 1: 回到首页")
ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html'")
time.sleep(10)  # 等待SPA完全初始化

# 验证Vue就绪
for attempt in range(5):
    vue = ev("!!document.getElementById('app')?.__vue__")
    if vue:
        print(f"  Vue就绪 (attempt {attempt+1})")
        break
    print(f"  等待Vue... (attempt {attempt+1})")
    time.sleep(3)

# Step 2: 恢复Vuex
print("\nStep 2: 恢复Vuex")
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")
time.sleep(2)

# 检查首页
home = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,80)})")
print(f"  首页: hash={home.get('hash','')} text={home.get('text','')[:50] if home else 'None'}")

# Step 3: 点击"经营主体登记"展开菜单
print("\nStep 3: 点击经营主体登记")
click1 = ev("""(function(){
    var all=document.querySelectorAll('*');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t==='经营主体登记')&&all[i].offsetParent!==null&&all[i].children.length<3){
            all[i].click();return{clicked:t};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  result: {click1}")
time.sleep(2)

# Step 4: 点击"企业开办"
print("\nStep 4: 点击企业开办")
click2 = ev("""(function(){
    var all=document.querySelectorAll('*');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='企业开办'&&all[i].offsetParent!==null&&all[i].children.length<3){
            all[i].click();return{clicked:t};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  result: {click2}")
time.sleep(3)

# 检查页面
page2 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,80)})")
print(f"  page: hash={page2.get('hash','') if page2 else '?'} text={page2.get('text','')[:40] if page2 else 'None'}")

# Step 5: 如果在企业开办专区，点击"设立登记"或"开始办理"
print("\nStep 5: 点击设立登记/开始办理")
click3 = ev("""(function(){
    // 找设立登记卡片
    var all=document.querySelectorAll('[class*="card"],[class*="item"],[class*="service"],[class*="swiper"]');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30&&all[i].offsetParent!==null){
            all[i].click();return{clicked:'设立登记',text:t.substring(0,20)};
        }
    }
    // 找开始办理按钮
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){
            btns[i].click();return{clicked:'开始办理'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  result: {click3}")
time.sleep(3)

page3 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,80)})")
print(f"  page: hash={page3.get('hash','') if page3 else '?'} text={page3.get('text','')[:40] if page3 else 'None'}")

# Step 6: 处理名称选择页
if page3 and ('without-name' in page3.get('hash','') or '名称' in page3.get('text','')):
    print("\nStep 6: 名称选择页")
    
    # 点击"其他来源名称"
    ev("""(function(){
        var btns=document.querySelectorAll('button,.el-button,[class*="btn"]');
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if(t.includes('其他来源')&&btns[i].offsetParent!==null){btns[i].click();return}
        }
    })()""")
    time.sleep(2)
    
    # 填写名称和单号
    ev("""(function(){
        var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
        var inputs=document.querySelectorAll('.el-dialog .el-input__inner');
        for(var i=0;i<inputs.length;i++){
            var ph=inputs[i].placeholder||'';
            if(ph.includes('名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
            if(ph.includes('单号')||ph.includes('保留')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
        }
    })()""")
    time.sleep(1)
    
    # 点击确定
    ev("""(function(){var btns=document.querySelectorAll('.el-dialog button,.el-dialog .el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('确定')||btns[i].textContent?.trim()?.includes('确认')){btns[i].click();return}}})()""")
    time.sleep(2)
    
    # 调用getHandleBusiness注册动态路由
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,d){if(d>10)return null;if(vm.$options?.name==='select-prise')return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],d+1);if(r)return r}return null}
        var sp=findComp(vm,0);if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness();
    })()""")
    time.sleep(3)
    
    # 导航到表单
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base/basic-info')})()""")
    time.sleep(5)

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if fc and fc.get('formCount',0) < 10:
    print("等待表单...")
    time.sleep(5)
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  结果: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

log("330.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 导航完成")
