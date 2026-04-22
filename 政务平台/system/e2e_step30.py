#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step30: 诊断SPA状态 → 恢复 → 导航到设立登记表单（不再离开）"""
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
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    for _ in range(20):
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r.get("result",{}).get("result",{}).get("value")
        except:
            return None
    return None

# 1. 诊断SPA状态
print("=== 1. SPA诊断 ===")
diag = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var store=vm?.$store;
    var router=vm?.$router;
    return{
        hasVue:!!vm,
        hasStore:!!store,
        hasRouter:!!router,
        loginToken:store?.state?.login?.token?'exists('+String(store.state.login.token).length+')':'empty',
        loginUserInfo:store?.state?.login?.userInfo?Object.keys(store.state.login.userInfo).length+'keys':'empty',
        currentRoute:router?.currentRoute?.path||'',
        routeCount:router?.options?.routes?.length||0,
        lsTopToken:localStorage.getItem('top-token')?.substring(0,15)||'NULL',
        lsAuth:localStorage.getItem('Authorization')?.substring(0,15)||'NULL',
        hash:location.hash,
        bodyText:(document.body.innerText||'').substring(0,100)
    };
})()""")
print(f"  hasVue: {diag.get('hasVue')}")
print(f"  hasStore: {diag.get('hasStore')}")
print(f"  hasRouter: {diag.get('hasRouter')}")
print(f"  loginToken: {diag.get('loginToken')}")
print(f"  loginUserInfo: {diag.get('loginUserInfo')}")
print(f"  currentRoute: {diag.get('currentRoute')}")
print(f"  lsTopToken: {diag.get('lsTopToken')}")
print(f"  lsAuth: {diag.get('lsAuth')}")
print(f"  hash: {diag.get('hash')}")
print(f"  text: {diag.get('bodyText','')[:80]}")

# 2. 完整恢复Vuex登录态
print("\n=== 2. 完整恢复Vuex登录态 ===")
restore = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(!store)return{error:'no_store'};
    
    var topToken=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    
    // 设置token（用top-token）
    store.commit('login/SET_TOKEN',topToken);
    
    // 尝试获取userInfo
    var userInfoStr=localStorage.getItem('_topnet_userInfo')||'';
    if(userInfoStr.startsWith('_topnet_')){
        try{
            var parsed=JSON.parse(userInfoStr.substring(8));
            // userInfo可能是userId
        }catch(e){}
    }
    
    // 通过API获取userInfo
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',topToken);
    xhr.setRequestHeader('Authorization',auth||topToken);
    try{xhr.send()}catch(e){return{apiError:e.message}}
    
    var userInfo=null;
    if(xhr.status===200){
        try{
            var resp=JSON.parse(xhr.responseText);
            if(resp.code==='00000'&&resp.data?.busiData){
                userInfo=resp.data.busiData;
                store.commit('login/SET_USER_INFO',userInfo);
            }
        }catch(e){}
    }
    
    return{
        tokenSet:String(store.state.login.token).substring(0,10)+'...',
        userInfoSet:!!store.state.login.userInfo,
        apiStatus:xhr.status,
        userInfoKeys:userInfo?Object.keys(userInfo).slice(0,10):[]
    };
})()""")
print(f"  restore: {restore}")

# 3. 检查路由是否可用
print("\n=== 3. 路由检查 ===")
route_check = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var router=vm?.$router;
    if(!router)return{error:'no_router'};
    var paths=[
        '/index/page',
        '/namenotice/declaration-instructions',
        '/flow/base/basic-info',
        '/index/enterprise/enterprise-zone',
        '/index/select-prise'
    ];
    return paths.map(function(p){
        var m=router.resolve(p);
        return{path:p,resolved:m.route.path,name:m.route.name||'',matched:m.route.matched?.length||0};
    });
})()""")
for r in (route_check or []):
    status = "✅" if r.get('resolved') != '/404' else "❌"
    print(f"  {status} {r.get('path')} → {r.get('resolved')} (matched={r.get('matched',0)})")

# 4. 导航到设立登记表单
print("\n=== 4. 导航到设立登记表单 ===")
# 先回首页
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router){
        try{vm.$router.push('/index/page')}catch(e){}
    }
})()""")
time.sleep(3)

home = ev("({hash:location.hash, hasUser:(document.body.innerText||'').includes('裕')})")
print(f"  首页: hash={home.get('hash')} hasUser={home.get('hasUser')}")

# 然后导航到申报须知
nav = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(!vm?.$router)return{error:'no_router'};
    try{vm.$router.push('/namenotice/declaration-instructions?busiType=02&entType=1100');return{ok:true}}catch(e){return{error:e.message}}
})()""")
print(f"  nav: {nav}")
time.sleep(8)

# 5. 检查是否到了表单
page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  hash: {(page or {}).get('hash','?')}")
print(f"  forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:200]}")

# 等待
fc = (page or {}).get('formCount',0)
if fc == 0:
    for attempt in range(8):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
        fc = (check or {}).get('formCount',0)
        print(f"  {attempt+1}: hash={(check or {}).get('hash')} forms={fc}")
        if fc > 0: break

if fc > 0:
    # 6. 表单探查
    print("\n=== 5. 表单探查 ===")
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
            if(input){info.ph=input.placeholder||'';info.disabled=input.disabled;info.val=(input.value||'').substring(0,20)}
            r.push(info);
        }
        var steps=document.querySelectorAll('.el-step');
        var stepList=[];
        for(var i=0;i<steps.length;i++){
            var title=steps[i].querySelector('.el-step__title');
            stepList.push({i:i,title:title?.textContent?.trim()||'',active:steps[i].className?.includes('is-active')||steps[i].className?.includes('is-finish')});
        }
        var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,20);
        return{fields:r,steps:stepList,buttons:btns};
    })()""")
    if form:
        log("66.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("66a.字段详情", {"fields":form.get("fields",[])[:60]})
        print(f"  步骤: {form.get('steps',[])}")
        print(f"  按钮: {form.get('buttons',[])}")
        for f in form.get("fields",[])[:50]:
            print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')} val={f.get('val','')}")

    # 7. 填写
    print("\n=== 6. 填写 ===")
    MATERIALS = {
        "公司名称":"广西智信数据科技有限公司","企业名称":"广西智信数据科技有限公司",
        "名称":"广西智信数据科技有限公司","注册资本":"100",
        "经营范围":"软件开发、信息技术咨询服务","住所":"南宁市青秀区民族大道166号",
        "法定代表人":"陈明辉","身份证":"450103199001151234",
        "联系电话":"13877151234","邮箱":"chenmh@example.com",
        "邮政编码":"530028","监事":"李芳","财务负责人":"张丽华",
        "联络员":"王小明","从业人数":"5",
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
                    return{{ok:false,label:label.textContent.trim(),reason:'no_input_or_disabled'}};
                }}
            }}
            return{{ok:false,label:kw,reason:'not_found'}};
        }})()""")
        results.append(r or {"ok":False,"label":kw,"reason":"cdp_err"})
    ok=[r for r in results if r and r.get("ok")]
    fail=[r for r in results if r and not r.get("ok")]
    log("67.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
        issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
    print(f"  ok={len(ok)} fail={len(fail)}")
    for r in ok: print(f"    ✅ {r.get('label','')}")
    for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

    # 8. 找下一步按钮
    print("\n=== 7. 下一步按钮 ===")
    btns = ev("""(function(){
        var btns=document.querySelectorAll('button,.el-button');
        var r=[];
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if(t&&(t.includes('下一步')||t.includes('保存')||t.includes('暂存')||t.includes('提交')||t.includes('预览'))&&btns[i].offsetParent!==null){
                r.push({i:i,text:t});
            }
        }
        return r;
    })()""")
    print(f"  buttons: {btns}")

    # 点击下一步
    for b in (btns or []):
        if '下一步' in b.get('text',''):
            print(f"\n  点击下一步...")
            ev("""(function(){
                var btns=document.querySelectorAll('button,.el-button');
                for(var i=0;i<btns.length;i++){
                    if(btns[i].textContent?.trim()?.includes('下一步')&&btns[i].offsetParent!==null){
                        btns[i].click();return;
                    }
                }
            })()""")
            time.sleep(5)
            break

    # 9. 检查下一步页面
    page2 = ev("""(function(){
        return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        text:(document.body.innerText||'').substring(0,300)};
    })()""")
    print(f"  下一步: hash={(page2 or {}).get('hash')} forms={(page2 or {}).get('formCount',0)}")
    print(f"  text: {(page2 or {}).get('text','')[:200]}")

    # 10. 认证检测
    auth=ev("""(function(){
        var t=document.body.innerText||'';
        var html=document.body.innerHTML||'';
        return{
            faceAuth:t.includes('人脸')||html.includes('faceAuth'),
            smsAuth:t.includes('验证码')||t.includes('短信'),
            realName:t.includes('实名认证')||t.includes('实名'),
            signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),
            digitalCert:t.includes('数字证书')||t.includes('CA锁'),
            caAuth:t.includes('CA认证')||html.includes('caAuth'),
        };
    })()""")
    log("68.认证检测",auth)
    print(f"  认证: {auth}")

    # 错误检测
    errors = ev("""(function(){
        var msgs=document.querySelectorAll('.el-message,.el-message-box,[class*="error"],[class*="warning"]');
        var r=[];
        for(var i=0;i<msgs.length;i++){
            var t=msgs[i].textContent?.trim()||'';
            if(t&&t.length<100&&t.length>2)r.push(t);
        }
        return r.slice(0,5);
    })()""")
    if errors: print(f"  错误: {errors}")

else:
    print("\n  ❌ 表单未加载！")
    print("  可能需要用户手动刷新页面重新登录")
    log("66.表单加载失败", {"reason":"Vuex状态可能已损坏，需要刷新页面"})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step30.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step30 完成")
