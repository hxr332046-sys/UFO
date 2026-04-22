#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step12: 不刷新！在当前已登录会话中导航 → 探查表单 → 填写"""
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

# 1. 确认当前登录状态（不刷新！）
print("=== 1. 当前状态 ===")
state = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    var text=document.body.innerText||'';
    var userName='';
    // 从页面提取用户名
    var m=text.match(/黄永裕|用户[:：]\s*\S+/);
    if(m)userName=m[0];
    return{
        hash:location.hash,
        isLogin:text.includes('扫码登录'),
        hasUserName:text.includes('黄永裕'),
        loginToken:store?.state?.login?.token?'exists('+String(store.state.login.token).length+')':'empty',
        routes_sample:(function(){
            var router=vm?.$router;
            if(!router)return[];
            var paths=['/index/enterprise/enterprise-zone','/index/enterprise/establish','/company/my-space/space-index','/index/name-check','/index/guidelines'];
            return paths.map(function(p){var m=router.resolve(p);return{path:p,resolved:m.route.path,name:m.route.name||''}});
        })()
    };
})()""")
print(f"  hash: {state.get('hash')}")
print(f"  isLogin: {state.get('isLogin')}")
print(f"  hasUserName: {state.get('hasUserName')}")
print(f"  loginToken: {state.get('loginToken')}")
print(f"  routes: {json.dumps(state.get('routes_sample',[]), ensure_ascii=False)[:300]}")

# 如果路由还是404，说明上次刷新破坏了路由注册
# 需要用户重新登录
if state.get('isLogin'):
    print("\n  ⚠️ 页面显示登录页！需要用户重新登录")
    log("24.会话已失效", {"isLogin": True, "needRelogin": True})
    ws.close()
    sys.exit(1)

# 如果路由resolve到404
all_404 = all(r.get('resolved') == '/404' for r in (state.get('routes_sample') or []))
if all_404:
    print("\n  ⚠️ 所有路由resolve到404，路由未注册")
    print("  原因：SPA刷新后丢失了动态注册的路由")
    print("  解决方案：需要用户重新登录，然后不刷新直接操作")
    log("24.路由未注册", {"all_404": True, "reason": "SPA刷新后动态路由丢失"})
    
    # 尝试通过首页卡片点击导航（不通过Vue Router）
    print("\n=== 1b. 通过首页卡片点击 ===")
    # 先回首页
    ev("location.hash='#/index/page'")
    time.sleep(2)
    
    # 找到"企业开办一件事"的精确DOM路径并点击
    card = ev("""(function(){
        var slides=document.querySelectorAll('.swiper-slide');
        for(var i=0;i<slides.length;i++){
            var t=slides[i].textContent?.trim()||'';
            if(t.includes('企业开办一件事')&&t.length<15){
                // 找到Vue实例
                var vm=slides[i].__vue__;
                if(vm){
                    // 检查组件方法
                    var methods=[];
                    var proto=Object.getPrototypeOf(vm);
                    for(var k in proto){
                        if(typeof proto[k]==='function'&&k.charAt(0)!=='_'&&k!=='$')methods.push(k);
                    }
                    // 检查$attrs和$listeners
                    return{
                        hasVue:true,
                        methods:methods.slice(0,15),
                        attrs:Object.keys(vm.$attrs||{}),
                        listeners:Object.keys(vm.$listeners||{}),
                        parentName:vm.$parent?.$options?.name||'',
                        parentMethods:Object.getOwnPropertyNames(vm.$parent?.$options?.methods||{}).slice(0,10)
                    };
                }
                return{hasVue:false,text:t};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  card vue: {json.dumps(card, ensure_ascii=False)[:400]}")
    
    # 尝试触发父组件的方法
    if card and card.get('hasVue'):
        parent_click = ev("""(function(){
            var slides=document.querySelectorAll('.swiper-slide');
            for(var i=0;i<slides.length;i++){
                var t=slides[i].textContent?.trim()||'';
                if(t.includes('企业开办一件事')&&t.length<15&&slides[i].__vue__){
                    var vm=slides[i].__vue__;
                    var parent=vm.$parent;
                    // 遍历父组件链找handleClick/goTo等
                    var p=parent;
                    for(var j=0;j<5&&p;j++){
                        if(p.handleClick){
                            p.handleClick({text:'企业开办一件事',route:'/index/enterprise/enterprise-zone'});
                            return{called:'handleClick',on:p.$options?.name||''};
                        }
                        if(p.goTo){
                            p.goTo('/index/enterprise/enterprise-zone');
                            return{called:'goTo',on:p.$options?.name||''};
                        }
                        if(p.handleCardClick){
                            p.handleCardClick({text:'企业开办一件事'});
                            return{called:'handleCardClick',on:p.$options?.name||''};
                        }
                        p=p.$parent;
                    }
                    // 最后尝试emit click给parent
                    vm.$parent?.$emit('click',slides[i]);
                    return{method:'emit_to_parent'};
                }
            }
        })()""")
        print(f"  parent_click: {parent_click}")
        time.sleep(5)
        page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  after: {page}")

    ws.close()
    sys.exit(0)

# === 路由已注册！继续导航 ===
print("\n=== 2. Vue Router导航到企业开办专区 ===")
nav = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(!vm?.$router)return{error:'no_router'};
    try{vm.$router.push('/index/enterprise/enterprise-zone');return{ok:true}}catch(e){return{error:e.message}}
})()""")
print(f"  nav: {nav}")
time.sleep(5)

page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    is404:(document.body.innerText||'').includes('页面不存在'),
    text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  page: hash={page.get('hash')} forms={page.get('formCount')} is404={page.get('is404')}")
print(f"  text: {(page.get('text','') or '')[:200]}")

# 如果到了企业开办专区
if not page.get('is404') and page.get('formCount',0) >= 0:
    # 找设立登记入口
    print("\n=== 3. 找设立登记入口 ===")
    entries = ev("""(function(){
        var all=document.querySelectorAll('*');
        var r=[];
        for(var i=0;i<Math.min(all.length,2000);i++){
            var t=all[i].textContent?.trim()||'';
            if((t.includes('设立')||t.includes('情景导办'))&&t.length<20&&all[i].offsetParent!==null&&all[i].children.length<3){
                r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,30)||'',text:t});
            }
        }
        return r;
    })()""")
    print(f"  entries: {entries}")
    
    # 点击设立登记
    for e in (entries or []):
        if '设立' in e.get('text',''):
            ev(f"""(function(){{
                var all=document.querySelectorAll('{e.get("tag","div")}');
                for(var i=0;i<all.length;i++){{
                    if(all[i].textContent?.trim()?.includes('{e.get("text","")}')&&all[i].offsetParent!==null&&all[i].children.length<3){{
                        all[i].click();return;
                    }}
                }}
            }})()""")
            time.sleep(5)
            break

    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after click: hash={page2.get('hash')} forms={page2.get('formCount')}")
    print(f"  text: {(page2.get('text','') or '')[:150]}")

    # 如果有表单，详细探查
    if page2.get('formCount',0) > 0:
        form = ev("""(function(){
            var fi=document.querySelectorAll('.el-form-item');
            var r=[];
            for(var i=0;i<fi.length;i++){
                var item=fi[i],label=item.querySelector('.el-form-item__label');
                var input=item.querySelector('.el-input__inner,.el-textarea__inner');
                var sel=item.querySelector('.el-select');
                var upload=item.querySelector('.el-upload');
                var tp='unknown';
                if(input)tp=input.tagName==='TEXTAREA'?'textarea':'input';
                if(sel)tp='select';if(upload)tp='upload';
                var info={i:i,label:label?.textContent?.trim()||'',type:tp,required:item.className.includes('is-required')};
                if(input){info.ph=input.placeholder||'';info.disabled=input.disabled}
                r.push(info);
            }
            var steps=document.querySelectorAll('.el-step');
            var stepList=[];
            for(var i=0;i<steps.length;i++){stepList.push(steps[i].querySelector('.el-step__title')?.textContent?.trim()||'')}
            return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,15)};
        })()""")
        log("25.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("25a.字段详情", {"fields":form.get("fields",[])[:50]})

        # 逐字段填写
        MATERIALS = {
            "公司名称":"广西智信数据科技有限公司","名称":"广西智信数据科技有限公司",
            "注册资本":"100","经营范围":"软件开发","住所":"南宁市青秀区民族大道166号",
            "法定代表人":"陈明辉","身份证":"450103199001151234","联系电话":"13877151234",
            "邮箱":"chenmh@example.com","监事":"李芳","财务负责人":"张丽华",
        }
        results=[]
        for kw,val in MATERIALS.items():
            r=ev(f"""(function(){{
                var kw='{kw}',val='{val}';
                var fi=document.querySelectorAll('.el-form-item');
                for(var i=0;i<fi.length;i++){{
                    var label=fi[i].querySelector('.el-form-item__label');
                    if(label&&label.textContent.trim().includes(kw)){{
                        var input=fi[i].querySelector('.el-input__inner,.el-textarea__inner');
                        if(input&&!input.disabled){{
                            var setter=Object.getOwnPropertyDescriptor(window[input.tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                            setter.call(input,val);input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));
                            return{{ok:true,label:label.textContent.trim()}};
                        }}
                        return{{ok:false,label:label.textContent.trim(),reason:'no_input'}};
                    }}
                }}
                return{{ok:false,label:kw,reason:'not_found'}};
            }})()""")
            results.append(r or {"ok":False,"label":kw,"reason":"cdp_err"})
        ok=[r for r in results if r and r.get("ok")]
        fail=[r for r in results if r and not r.get("ok")]
        log("26.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])

        # 认证检测
        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证')}})()""")
        log("27.认证检测",auth)

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step12.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step12 完成")
