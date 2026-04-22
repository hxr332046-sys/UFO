#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step11: 设置Authorization到localStorage → 刷新SPA → 导航"""
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

# 1. 检查当前localStorage
print("=== 1. 当前localStorage ===")
ls = ev("""(function(){
    var r={};
    for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);r[k]=localStorage.getItem(k)}
    return r;
})()""")
print(f"  keys: {list((ls or {}).keys())}")
for k,v in (ls or {}).items():
    print(f"  {k}: {str(v)[:40]}")

# 2. 关键：设置 Authorization = top-token 的值
print("\n=== 2. 设置Authorization ===")
top_token = (ls or {}).get("top-token", "")
if top_token:
    ev(f"localStorage.setItem('Authorization', '{top_token}')")
    # 验证
    auth = ev("localStorage.getItem('Authorization')")
    print(f"  Authorization set: {auth[:20]}... (len={len(auth or '')})")
else:
    print("  ERROR: top-token is empty!")
    sys.exit(1)

# 3. 刷新页面让SPA重新初始化（带Authorization）
print("\n=== 3. 刷新SPA ===")
ev("location.reload()")
time.sleep(8)

# 4. 检查刷新后状态
print("\n=== 4. 刷新后状态 ===")
state = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    var text=document.body.innerText||'';
    return{
        hash:location.hash,
        isLogin:text.includes('扫码登录'),
        hasVue:!!vm,
        hasStore:!!store,
        loginToken:store?.state?.login?.token?'exists('+String(store.state.login.token).length+')':'empty',
        loginUserInfo:store?.state?.login?.userInfo?Object.keys(store.state.login.userInfo).length+'keys':'empty',
        formCount:document.querySelectorAll('.el-form-item').length,
        Authorization:localStorage.getItem('Authorization')?.substring(0,20)||'NONE',
        topToken:localStorage.getItem('top-token')?.substring(0,20)||'NONE',
        textPreview:text.substring(0,150)
    };
})()""")
print(f"  hash: {state.get('hash')}")
print(f"  isLogin: {state.get('isLogin')}")
print(f"  loginToken: {state.get('loginToken')}")
print(f"  loginUserInfo: {state.get('loginUserInfo')}")
print(f"  formCount: {state.get('formCount')}")
print(f"  text: {(state.get('textPreview','') or '')[:120]}")

# 5. 如果登录成功，尝试导航
if not state.get('isLogin'):
    print("\n=== 5. Vue Router导航 ===")
    # 先检查路由是否已注册
    routes_check = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        if(!router)return{error:'no_router'};
        var paths=['/index/enterprise/enterprise-zone','/index/enterprise/establish','/company/my-space/space-index','/index/name-check'];
        return paths.map(function(p){
            var m=router.resolve(p);
            return{path:p,resolved:m.route.path,name:m.route.name||'',matched:m.route.matched?.length||0};
        });
    })()""")
    print(f"  routes: {json.dumps(routes_check, ensure_ascii=False)[:400]}")

    # 导航到企业开办专区
    nav = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(!vm?.$router)return{error:'no_router'};
        try{vm.$router.push('/index/enterprise/enterprise-zone');return{ok:true}}catch(e){return{error:e.message}}
    })()""")
    print(f"  nav: {nav}")
    time.sleep(5)

    page = ev("""(function(){
        return{
            hash:location.hash,
            formCount:document.querySelectorAll('.el-form-item').length,
            is404:(document.body.innerText||'').includes('页面不存在'),
            text:(document.body.innerText||'').substring(0,300)
        };
    })()""")
    print(f"  page: hash={page.get('hash')} forms={page.get('formCount')} is404={page.get('is404')}")
    print(f"  text: {(page.get('text','') or '')[:200]}")

    # 6. 如果成功导航，探查表单
    if page.get('formCount',0) > 0:
        print("\n=== 6. 表单探查 ===")
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
            for(var i=0;i<steps.length;i++){stepList.push({i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||'',active:steps[i].className.includes('is-active')})}
            return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,15)};
        })()""")
        log("21.设立登记页面", {
            "formCount": len(form.get("fields",[])),
            "steps": form.get("steps",[]),
            "buttons": form.get("buttons",[]),
        })
        log("21a.字段详情", {"fields": form.get("fields",[])[:40]})

        # 7. 逐字段填写
        MATERIALS = {
            "公司名称":"广西智信数据科技有限公司","名称":"广西智信数据科技有限公司",
            "注册资本":"100","经营范围":"软件开发、信息技术咨询服务",
            "住所":"南宁市青秀区民族大道166号","法定代表人":"陈明辉",
            "身份证":"450103199001151234","联系电话":"13877151234",
            "邮箱":"chenmh@example.com","监事":"李芳","财务负责人":"张丽华",
        }
        results = []
        for kw, val in MATERIALS.items():
            r = ev(f"""(function(){{
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
        ok = [r for r in results if r and r.get("ok")]
        fail = [r for r in results if r and not r.get("ok")]
        log("22.填写测试", {"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])

        # 8. 检查认证要求
        auth = ev("""(function(){
            var t=document.body.innerText||'';
            return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证')};
        })()""")
        log("23.认证检测", auth)

    elif not page.get('is404'):
        # 不是404也不是表单，可能是中间页面
        print(f"\n  中间页面，继续探查...")
        # 找可点击元素
        clicks = ev("""(function(){
            var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li');
            var r=[];
            for(var i=0;i<all.length;i++){
                var t=all[i].textContent?.trim()||'';
                if((t.includes('设立')||t.includes('开办')||t.includes('登记')||t.includes('下一步'))&&t.length<20&&all[i].offsetParent!==null){
                    r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,30)||'',text:t});
                }
            }
            return r;
        })()""")
        print(f"  clickable: {clicks}")
        
        # 点击设立登记
        if clicks:
            for c in clicks:
                if '设立' in c.get('text','') or '开办' in c.get('text',''):
                    ev(f"""(function(){{
                        var all=document.querySelectorAll('{c.get("tag","div")}');
                        for(var i=0;i<all.length;i++){{
                            if(all[i].textContent?.trim()?.includes('{c.get("text","")}')&&all[i].offsetParent!==null){{
                                all[i].click();return;
                            }}
                        }}
                    }})()""")
                    time.sleep(5)
                    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
                    print(f"  after click: {page2}")
                    break
else:
    print("\n  ⚠️ 刷新后显示登录页！Authorization=top-token方案失败")
    log("20b.刷新后登录页", {"isLogin": True, "conclusion": "Authorization=top-token无效，需要真正的登录token"})

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
                    p = os.path.join(os.path.dirname(__file__),"..","data","e2e_step11.png")
                    with open(p,"wb") as f: f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except: break
except: pass

ws.close()
print("\n✅ Step11 完成")
