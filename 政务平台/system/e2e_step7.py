#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step7: 精确点击首页卡片导航"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)

_mid = 0
def ev(js, mid=None):
    global _mid
    if mid is None: mid = _mid + 1; _mid = mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":10000}}))
    while True:
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None

# 回首页
ev("location.hash='#/index/page'")
time.sleep(3)

# 1. 精确分析首页DOM结构 - 找到卡片点击的精确路径
print("=== 1. 首页卡片DOM精确分析 ===")
dom_analysis = ev("""(function(){
    var r={swiperSlides:[],featuredItems:[],allClickable:[]};
    
    // swiper slides
    var slides=document.querySelectorAll('.swiper-slide');
    for(var i=0;i<slides.length;i++){
        var t=slides[i].textContent?.trim()||'';
        if(t.length<50)r.swiperSlides.push({i:i,cls:slides[i].className,text:t,childHtml:slides[i].innerHTML?.substring(0,100)});
    }
    
    // featured-service items
    var fs=document.querySelectorAll('.featured-service .item,.featured-service [class*="item"]');
    for(var i=0;i<fs.length;i++){
        var t=fs[i].textContent?.trim()||'';
        r.featuredItems.push({i:i,cls:fs[i].className,text:t.substring(0,30),tag:fs[i].tagName});
    }
    
    // 所有带 @click 或 onclick 的元素
    var all=document.querySelectorAll('*');
    for(var i=0;i<Math.min(all.length,2000);i++){
        var el=all[i];
        var t=el.textContent?.trim()||'';
        if((t.includes('企业开办')||t.includes('设立'))&&t.length<30){
            var parent=el;
            var chain=[];
            for(var j=0;j<5&&parent;j++){
                chain.push(parent.tagName+'.'+(parent.className||'').split(' ')[0]);
                parent=parent.parentElement;
            }
            r.allClickable.push({
                tag:el.tagName,
                cls:(el.className||'').substring(0,40),
                text:t.substring(0,25),
                childCount:el.children?.length,
                chain:chain.reverse().join('>')
            });
        }
    }
    return r;
})()""")
print(f"  swiperSlides: {dom_analysis.get('swiperSlides',[])}")
print(f"  featuredItems: {dom_analysis.get('featuredItems',[])}")
print(f"  clickable elements with '企业开办/设立':")
for c in (dom_analysis.get('allClickable') or []):
    print(f"    {c}")

# 2. 尝试点击 swiper-slide 中的"企业开办一件事"
print("\n=== 2. 点击swiper-slide ===")
click1 = ev("""(function(){
    var slides=document.querySelectorAll('.swiper-slide');
    for(var i=0;i<slides.length;i++){
        var t=slides[i].textContent?.trim()||'';
        if(t.includes('企业开办一件事')&&t.length<20){
            // 找到里面的a或可点击元素
            var a=slides[i].querySelector('a');
            if(a){
                a.click();
                return{method:'a.click',text:t,href:a.getAttribute('href')||''};
            }
            // 直接点击slide
            slides[i].click();
            return{method:'slide.click',text:t};
        }
    }
    return{error:'not_found_in_slides'};
})()""")
print(f"  click1: {click1}")
time.sleep(5)
page1 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  after click1: {page1}")

# 3. 如果没变，尝试点击 featured-service 中的卡片
if page1.get('formCount',0) == 0 and page1.get('hash') == '#/index/page':
    print("\n=== 3. 点击featured-service卡片 ===")
    click2 = ev("""(function(){
        // 找所有div，精确匹配"企业开办一件事"
        var all=document.querySelectorAll('div');
        for(var i=0;i<all.length;i++){
            if(all[i].children.length===0||all[i].children.length===1){
                var t=all[i].textContent?.trim()||'';
                if(t==='企业开办一件事'){
                    // 模拟完整点击事件链
                    var events=['mousedown','mouseup','click'];
                    for(var j=0;j<events.length;j++){
                        all[i].dispatchEvent(new MouseEvent(events[j],{bubbles:true,cancelable:true,view:window}));
                    }
                    return{method:'div.dispatchEvent',text:t,tag:all[i].tagName,cls:all[i].className?.substring(0,30)||''};
                }
            }
        }
        return{error:'not_found_exact'};
    })()""")
    print(f"  click2: {click2}")
    time.sleep(5)
    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after click2: {page2}")

# 4. 分析Vue组件的点击处理
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 4. 分析Vue组件事件处理 ===")
    vue_events = ev("""(function(){
        var r=[];
        // 找所有包含"企业开办"的Vue组件
        var all=document.querySelectorAll('*');
        for(var i=0;i<Math.min(all.length,1000);i++){
            var el=all[i];
            var t=el.textContent?.trim()||'';
            if(t.includes('企业开办')&&t.length<30&&el.__vue__){
                var vm=el.__vue__;
                var handlers=[];
                // 检查 $listeners
                if(vm.$listeners){
                    for(var k in vm.$listeners){
                        handlers.push('listener:'+k);
                    }
                }
                // 检查 $options._parentListeners
                if(vm.$options&&vm.$options._parentListeners){
                    for(var k in vm.$options._parentListeners){
                        handlers.push('parent:'+k);
                    }
                }
                // 检查 _events
                if(vm._events){
                    for(var k in vm._events){
                        handlers.push('event:'+k+'('+vm._events[k].length+')');
                    }
                }
                r.push({tag:el.tagName,cls:(el.className||'').substring(0,30),text:t.substring(0,20),handlers:handlers,vueTag:vm.$options?.name||vm.$options?.tag||'unknown'});
            }
        }
        return r;
    })()""")
    print(f"  Vue components with events:")
    for v in (vue_events or []):
        print(f"    {v}")

    # 5. 尝试通过Vue组件触发事件
    print("\n=== 5. 通过Vue $emit触发 ===")
    emit_result = ev("""(function(){
        var all=document.querySelectorAll('*');
        for(var i=0;i<all.length;i++){
            var el=all[i];
            var t=el.textContent?.trim()||'';
            if(t.includes('企业开办')&&t.length<30&&el.__vue__){
                var vm=el.__vue__;
                // 尝试触发click
                vm.$emit('click');
                vm.$emit('click',t);
                // 也尝试调用 $router.push
                if(vm.$router){
                    vm.$router.push('/index/enterprise/enterprise-zone');
                    return{method:'vm.$router.push',text:t};
                }
                // 尝试调用handleClick之类的方法
                if(vm.handleClick){vm.handleClick();return{method:'handleClick'}}
                if(vm.onClick){vm.onClick();return{method:'onClick'}}
                if(vm.goTo){vm.goTo('/index/enterprise/enterprise-zone');return{method:'goTo'}}
                if(vm.navigate){vm.navigate('/index/enterprise/enterprise-zone');return{method:'navigate'}}
                // 查看vm的所有方法
                var methods=[];
                for(var k in vm){
                    if(typeof vm[k]==='function'&&k.charAt(0)!=='_'&&k!=='$'){
                        methods.push(k);
                    }
                }
                return{methods:methods.slice(0,20),text:t};
            }
        }
        return{error:'no_vue_component_found'};
    })()""")
    print(f"  emit: {emit_result}")
    time.sleep(5)
    page3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after emit: {page3}")

# 6. 最终检查 - 如果还是首页，尝试最底层方式
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 6. 最终尝试：直接访问完整URL ===")
    # 先恢复登录态到Vuex
    ev("""(function(){
        var app=document.getElementById('app');
        var vm=app&&app.__vue__;
        var store=vm&&vm.$store;
        if(store){
            var t=localStorage.getItem('top-token')||'';
            store.commit('login/SET_TOKEN',t);
        }
    })()""")
    time.sleep(1)
    
    # 用Page.navigate加载完整URL
    ws.send(json.dumps({"id":500,"method":"Page.navigate","params":{"url":"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"}}))
    time.sleep(8)
    page4 = ev("""(function(){
        return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
        isLogin:(document.body.innerText||'').includes('扫码登录'),
        text:(document.body.innerText||'').substring(0,300)};
    })()""")
    print(f"  after Page.navigate: {page4}")

    # 如果到了登录页，说明Page.navigate会丢失Vuex状态
    if page4.get('isLogin'):
        print("\n  ⚠️ Page.navigate导致页面刷新，Vuex状态丢失→回到登录页")
        print("  结论：需要通过Vue Router内部导航，不能刷新页面")
        
        # 重新登录恢复
        ev("location.hash='#/index/page'")
        time.sleep(3)
        ev("""(function(){
            var app=document.getElementById('app');
            var vm=app&&app.__vue__;
            var store=vm&&vm.$store;
            if(store){
                var t=localStorage.getItem('top-token')||'';
                store.commit('login/SET_TOKEN',t);
            }
        })()""")
        
        # 检查Vue Router所有注册的路由
        print("\n=== 6b. 检查Vue Router注册的路由 ===")
        routes = ev("""(function(){
            var app=document.getElementById('app');
            var vm=app&&app.__vue__;
            var router=vm&&vm.$router;
            if(!router)return{error:'no_router'};
            var all=[];
            function collect(rs,prefix){
                for(var i=0;i<rs.length;i++){
                    var r=rs[i];
                    var p=(prefix||'')+(r.path||'');
                    if(r.name||r.path)all.push({path:p,name:r.name||'',meta:r.meta||{}});
                    if(r.children)collect(r.children,p);
                }
            }
            collect(router.options.routes||[],'');
            // 只返回企业相关的
            return all.filter(function(r){return r.path.includes('enterprise')||r.path.includes('establish')||r.path.includes('company')});
        })()""")
        print(f"  enterprise/establish routes: {json.dumps(routes, ensure_ascii=False, indent=2)[:500]}")

# 最终状态
final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
log("17.导航测试最终状态", {
    "hash": final.get("hash"),
    "formCount": final.get("formCount"),
    "textPreview": (final.get("text","") or "")[:200],
})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10)
            r = json.loads(ws.recv())
            if r.get("id") == 8888:
                d = r.get("result",{}).get("data","")
                if d:
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_step7.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step7 完成")
