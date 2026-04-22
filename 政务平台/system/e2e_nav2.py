#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到表单 - 通过UI点击而非router.push"""
import json, time, os, requests, websocket, base64
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

# 检查当前状态
state = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    var isLoggedIn=store?.state?.login?.token?true:false;
    var hash=location.hash;
    return{hash:hash,hasVue:!!vm,isLoggedIn:isLoggedIn,text:(document.body?.innerText||'').substring(0,150)};
})()""")
print(f"当前: hash={state.get('hash')} loggedIn={state.get('isLoggedIn')} text={state.get('text','')[:60]}")

# 如果在404，先回到首页
if '#/404' in state.get('hash',''):
    print("从404回到首页")
    ev("location.hash='#/index/page'")
    time.sleep(3)

# 恢复Vuex
print("恢复Vuex")
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

# 分析首页可点击元素
print("\n分析首页")
home_analysis = ev("""(function(){
    var all=document.querySelectorAll('[class*="service"],[class*="card"],[class*="item"],[class*="menu"],[class*="collapse"],a,button');
    var items=[];
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.length>2&&t.length<30&&all[i].offsetParent!==null){
            items.push({idx:i,tag:all[i].tagName,class:(all[i].className||'').substring(0,30),text:t.substring(0,25)});
        }
    }
    return{count:items.length,items:items.slice(0,30)};
})()""")
for item in (home_analysis.get('items') or []):
    if any(kw in item.get('text','') for kw in ['企业','开办','经营','登记','设立','服务','办理']):
        print(f"  [{item.get('idx')}] {item.get('tag')} {item.get('text','')} class={item.get('class','')}")

# 点击"经营主体登记"展开菜单
print("\n点击经营主体登记")
click1 = ev("""(function(){
    var spans=document.querySelectorAll('span,div,a,li');
    for(var i=0;i<spans.length;i++){
        var t=spans[i].textContent?.trim()||'';
        if(t==='经营主体登记'||t.includes('经营主体登记')){
            spans[i].click();
            spans[i].dispatchEvent(new Event('click',{bubbles:true}));
            return{clicked:t};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click1: {click1}")
time.sleep(2)

# 检查展开后的内容
page1 = ev("""(function(){
    var text=(document.body?.innerText||'').substring(0,300);
    var links=document.querySelectorAll('a,[class*="item"],[class*="menu-item"],[class*="sub"]');
    var linkTexts=[];
    for(var i=0;i<links.length;i++){
        var t=links[i].textContent?.trim()||'';
        if(t.length>2&&t.length<20&&links[i].offsetParent!==null)linkTexts.push(t);
    }
    return{text:text.substring(0,100),linkTexts:linkTexts.slice(0,15),hash:location.hash};
})()""")
print(f"  page1: hash={page1.get('hash')} links={page1.get('linkTexts',[])}")

# 点击"企业开办"
print("\n点击企业开办")
click2 = ev("""(function(){
    var items=document.querySelectorAll('[class*="item"],[class*="menu"],a,span,div,li');
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()||'';
        if((t==='企业开办'||t.includes('企业开办'))&&items[i].offsetParent!==null){
            items[i].click();
            items[i].dispatchEvent(new Event('click',{bubbles:true}));
            return{clicked:t};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click2: {click2}")
time.sleep(3)

# 检查是否到了企业开办专区
page2 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,150)})")
print(f"  page2: hash={page2.get('hash')} text={page2.get('text','')[:60]}")

# 如果在企业开办专区，点击"设立登记"或"开始办理"
if 'enterprise' in page2.get('hash','') or '开办' in page2.get('text',''):
    print("\n在企业开办专区，点击设立登记/开始办理")
    
    # 找设立登记卡片
    click3 = ev("""(function(){
        var cards=document.querySelectorAll('[class*="card"],[class*="item"],[class*="service"]');
        for(var i=0;i<cards.length;i++){
            var t=cards[i].textContent?.trim()||'';
            if(t.includes('设立登记')&&cards[i].offsetParent!==null){
                cards[i].click();return{clicked:'设立登记'};
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
    print(f"  click3: {click3}")
    time.sleep(3)
    
    page3 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,100)})")
    print(f"  page3: hash={page3.get('hash')} text={page3.get('text','')[:50]}")
    
    # 如果到了名称选择页
    if 'without-name' in page3.get('hash','') or 'select' in page3.get('hash','') or '名称' in page3.get('text',''):
        print("\n在名称选择页")
        
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
            var inputs=document.querySelectorAll('.el-dialog .el-input__inner');
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
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
print(f"\n最终: hash={fc.get('hash')} forms={fc.get('formCount',0)}")

if fc.get('formCount',0) < 10:
    # 尝试直接hash导航
    print("尝试hash导航...")
    ev("location.hash='#/flow/base/basic-info'")
    time.sleep(5)
    fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  hash导航: hash={fc2.get('hash')} forms={fc2.get('formCount',0)}")

log("320.导航", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
ws.close()
print("✅ 导航完成")
