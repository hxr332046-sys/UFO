#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final: 一次性完成 导航→表单探查→填写→下一步→认证检测→报告"""
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

def screenshot(name):
    try:
        ws.send(json.dumps({"id":9900+hash(name)%100,"method":"Page.captureScreenshot","params":{"format":"png"}}))
        for _ in range(10):
            try:
                ws.settimeout(10);r=json.loads(ws.recv())
                if r.get("id",0)>=9900:
                    d=r.get("result",{}).get("data","")
                    if d:
                        p=os.path.join(os.path.dirname(__file__),"..","data",f"e2e_{name}.png")
                        with open(p,"wb") as f:f.write(base64.b64decode(d))
                        print(f"  📸 {p}")
                    break
            except:break
    except:pass

# ===== STEP 1: 诊断SPA状态 =====
print("=" * 60)
print("STEP 1: 诊断SPA状态")
print("=" * 60)
diag = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    var router=vm?.$router;
    return{
        hasVue:!!vm,hasStore:!!store,hasRouter:!!router,
        loginToken:store?.state?.login?.token?'exists('+String(store.state.login.token).length+')':'empty',
        currentRoute:router?.currentRoute?.path||'',
        lsTopToken:(localStorage.getItem('top-token')||'').substring(0,15),
        hash:location.hash,
        bodyText:(document.body.innerText||'').substring(0,100)
    };
})()""")
print(f"  Vue={diag.get('hasVue')} Store={diag.get('hasStore')} Router={diag.get('hasRouter')}")
print(f"  loginToken={diag.get('loginToken')} lsToken={diag.get('lsTopToken')}")
print(f"  hash={diag.get('hash')} route={diag.get('currentRoute')}")
print(f"  text={diag.get('bodyText','')[:60]}")

# ===== STEP 2: 确保Vuex token =====
print("\n" + "=" * 60)
print("STEP 2: 恢复Vuex token")
print("=" * 60)
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
    // 也获取userInfo
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{
        xhr.send();
        if(xhr.status===200){
            var resp=JSON.parse(xhr.responseText);
            if(resp.code==='00000'&&resp.data?.busiData){
                store.commit('login/SET_USER_INFO',resp.data.busiData);
            }
        }
    }catch(e){}
})()""")
verify = ev("(function(){var s=document.getElementById('app')?.__vue__?.$store;return{token:s?.state?.login?.token?'ok':'empty',userInfo:!!s?.state?.login?.userInfo}})()")
print(f"  verify: {verify}")

# ===== STEP 3: 导航到设立登记表单 =====
print("\n" + "=" * 60)
print("STEP 3: 导航到设立登记表单")
print("=" * 60)
# 先确认首页
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router){
        try{vm.$router.push('/index/page')}catch(e){}
    }
})()""")
time.sleep(3)

# 导航到申报须知→自动跳转到表单
nav = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(!vm?.$router)return{error:'no_router'};
    try{vm.$router.push('/namenotice/declaration-instructions?busiType=02&entType=1100');return{ok:true}}catch(e){return{error:e.message}}
})()""")
print(f"  nav: {nav}")
time.sleep(8)

# 检查
page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,200)};
})()""")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)} inputs={page.get('inputCount',0)}")

# 等待加载
fc = page.get('formCount',0)
if fc == 0:
    for attempt in range(10):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
        fc = (check or {}).get('formCount',0)
        h = (check or {}).get('hash','?')
        print(f"  wait {attempt+1}: hash={h} forms={fc}")
        if fc > 0: break

screenshot("step3_form")

if fc == 0:
    print("  ❌ 表单未加载！")
    log("70.表单加载失败", {"hash":page.get("hash"),"formCount":0})
    ws.close()
    sys.exit(1)

# ===== STEP 4: 表单详细探查 =====
print("\n" + "=" * 60)
print("STEP 4: 表单详细探查")
print("=" * 60)
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
    var stepTitle=document.querySelector('.el-step.is-active .el-step__title')?.textContent?.trim()||'';
    return{fields:r,steps:stepList,buttons:btns,stepTitle:stepTitle};
})()""")
if form:
    log("70.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[]),"stepTitle":form.get("stepTitle","")})
    log("70a.字段详情", {"fields":form.get("fields",[])[:60]})
    print(f"  步骤: {json.dumps(form.get('steps',[]), ensure_ascii=False)}")
    print(f"  当前步骤: {form.get('stepTitle','')}")
    print(f"  按钮: {form.get('buttons',[])}")
    print(f"  字段({len(form.get('fields',[]))}个):")
    for f in form.get("fields",[]):
        print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')} val={f.get('val','')}")

# ===== STEP 5: 逐字段填写 =====
print("\n" + "=" * 60)
print("STEP 5: 逐字段填写")
print("=" * 60)
MATERIALS = {
    "公司名称":"广西智信数据科技有限公司","企业名称":"广西智信数据科技有限公司",
    "名称":"广西智信数据科技有限公司","字号":"智信数据",
    "行业":"科技","组织形式":"有限公司",
    "注册资本":"100","出资方式":"货币","币种":"人民币",
    "经营范围":"软件开发、信息技术咨询服务、数据处理服务",
    "住所":"南宁市青秀区民族大道166号","生产经营地":"南宁市青秀区民族大道166号",
    "法定代表人":"陈明辉","负责人":"陈明辉",
    "身份证":"450103199001151234","证件号码":"450103199001151234",
    "联系电话":"13877151234","手机":"13877151234",
    "邮箱":"chenmh@example.com","邮政编码":"530028",
    "监事":"李芳","财务负责人":"张丽华",
    "联络员":"王小明","联络员电话":"13977160001",
    "从业人数":"5","股东":"陈明辉",
    "认缴出资":"100","实缴出资":"0",
    "出资比例":"100","出资时间":"2026-12-31",
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
log("71.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
    issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
print(f"\n  填写结果: ok={len(ok)} fail={len(fail)}")
print("  ✅ 成功:")
for r in ok: print(f"    {r.get('label','')}")
print("  ❌ 失败:")
for r in fail: print(f"    {r.get('label','')} ({r.get('reason','')})")

screenshot("step5_filled")

# ===== STEP 6: 点击下一步 =====
print("\n" + "=" * 60)
print("STEP 6: 点击下一步")
print("=" * 60)
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
print(f"  可用按钮: {btns}")

clicked_next = False
for b in (btns or []):
    if '下一步' in b.get('text',''):
        print(f"  点击: {b.get('text')}")
        ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].textContent?.trim()?.includes('下一步')&&btns[i].offsetParent!==null){
                    btns[i].click();return;
                }
            }
        })()""")
        time.sleep(5)
        clicked_next = True
        break

if not clicked_next:
    print("  ⚠️ 未找到下一步按钮")

# 检查下一步页面
page2 = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"  下一步: hash={page2.get('hash')} forms={page2.get('formCount',0)} inputs={page2.get('inputCount',0)}")
print(f"  text: {page2.get('text','')[:200]}")

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

screenshot("step6_next")

# ===== STEP 7: 认证检测 =====
print("\n" + "=" * 60)
print("STEP 7: 认证检测")
print("=" * 60)
auth=ev("""(function(){
    var t=document.body.innerText||'';
    var html=document.body.innerHTML||'';
    return{
        faceAuth:t.includes('人脸')||html.includes('faceAuth')||html.includes('face-auth'),
        smsAuth:t.includes('验证码')||t.includes('短信'),
        bankAuth:t.includes('银行卡'),
        realName:t.includes('实名认证')||t.includes('实名'),
        signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),
        digitalCert:t.includes('数字证书')||t.includes('CA锁'),
        caAuth:t.includes('CA认证')||html.includes('caAuth'),
        ukeyAuth:t.includes('UKey')||t.includes('U盾'),
        passwordAuth:t.includes('密码'),
    };
})()""")
log("72.认证检测",auth)
add_auth_finding("设立登记流程", auth or {})
print(f"  认证检测结果:")
for k,v in (auth or {}).items():
    if v: print(f"    ⚠️ {k}: {v}")

if not any(auth.values() if auth else []):
    print("    当前页面未检测到认证要求（可能在后续步骤出现）")

# ===== STEP 8: 如果到了新步骤页面，继续探查 =====
if page2.get('formCount',0) > 0 and page2.get('formCount',0) != fc:
    print("\n" + "=" * 60)
    print("STEP 8: 新步骤表单探查")
    print("=" * 60)
    form2 = ev("""(function(){
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
        for(var i=0;i<steps.length;i++){
            var title=steps[i].querySelector('.el-step__title');
            stepList.push({i:i,title:title?.textContent?.trim()||'',active:steps[i].className?.includes('is-active')||steps[i].className?.includes('is-finish')});
        }
        var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,20);
        var stepTitle=document.querySelector('.el-step.is-active .el-step__title')?.textContent?.trim()||'';
        return{fields:r,steps:stepList,buttons:btns,stepTitle:stepTitle};
    })()""")
    if form2:
        log("73.第二步表单", {"formCount":len(form2.get("fields",[])),"steps":form2.get("steps",[]),"buttons":form2.get("buttons",[]),"stepTitle":form2.get("stepTitle","")})
        log("73a.字段详情", {"fields":form2.get("fields",[])[:60]})
        print(f"  步骤: {json.dumps(form2.get('steps',[]), ensure_ascii=False)}")
        print(f"  当前步骤: {form2.get('stepTitle','')}")
        print(f"  按钮: {form2.get('buttons',[])}")
        for f in form2.get("fields",[])[:30]:
            print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')}")

# ===== STEP 9: 继续走到提交步骤（不点提交）=====
print("\n" + "=" * 60)
print("STEP 9: 遍历所有步骤直到提交页")
print("=" * 60)
max_steps = 8
for step in range(max_steps):
    # 检查当前步骤
    current = ev("""(function(){
        var steps=document.querySelectorAll('.el-step');
        var active=null;
        for(var i=0;i<steps.length;i++){
            if(steps[i].className?.includes('is-active')){
                active={i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||''};
                break;
            }
        }
        var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20});
        var hasSubmit=btns.some(function(t){return t.includes('提交')});
        var hasNext=btns.some(function(t){return t.includes('下一步')});
        return{step:active,hasSubmit:hasSubmit,hasNext:hasNext,buttons:btns.filter(function(t){return t.includes('下一步')||t.includes('提交')||t.includes('保存')||t.includes('预览')}).slice(0,5),
        formCount:document.querySelectorAll('.el-form-item').length,
        text:(document.body.innerText||'').substring(0,200)};
    })()""")
    
    step_info = current.get('step') or {}
    print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)}")
    print(f"  按钮: {current.get('buttons',[])}")
    print(f"  hasSubmit={current.get('hasSubmit')} hasNext={current.get('hasNext')}")
    
    # 认证检测
    auth2=ev("""(function(){
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
    if any(auth2.values() if auth2 else []):
        print(f"  ⚠️ 认证要求: {auth2}")
        add_auth_finding(f"步骤{step}-{step_info.get('title','')}", auth2)
        log(f"74.step{step}_auth", auth2)
    
    # 如果有提交按钮，记录但**不点击**
    if current.get('hasSubmit'):
        print(f"\n  🔴 检测到提交按钮！停止前进（不点击提交）")
        log("75.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth2})
        screenshot("step9_submit_page")
        break
    
    # 如果有下一步，点击
    if current.get('hasNext'):
        print(f"  点击下一步...")
        ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].textContent?.trim()?.includes('下一步')&&btns[i].offsetParent!==null){
                    btns[i].click();return;
                }
            }
        })()""")
        time.sleep(5)
        
        # 检查错误
        errs = ev("""(function(){
            var msgs=document.querySelectorAll('.el-message,[class*="error"]');
            var r=[];
            for(var i=0;i<msgs.length;i++){
                var t=msgs[i].textContent?.trim()||'';
                if(t&&t.length<80)r.push(t);
            }
            return r.slice(0,3);
        })()""")
        if errs:
            print(f"  ⚠️ 错误: {errs}")
            log(f"75b.step{step}_errors", {"errors":errs})
            # 如果有验证错误，不继续
            break
    else:
        print(f"  没有下一步按钮，停止")
        break

screenshot("step9_final")

# ===== 最终报告 =====
print("\n" + "=" * 60)
print("E2E 测试完成")
print("=" * 60)

ws.close()
print("\n✅ e2e_final.py 完成")
