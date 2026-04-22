#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final5: 恢复SPA → 企业专区 → 开始办理 → toSelectName → getHandleBusiness注册路由 → 干净URL导航到表单 → 填写 → 认证"""
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

# ===== STEP 1: 恢复SPA + Vuex =====
print("STEP 1: 恢复SPA + Vuex")
cur = ev("({url:location.href,hasVue:!!document.getElementById('app')?.__vue__,hash:location.hash})")
print(f"  url={cur.get('url','')[:60]} hasVue={cur.get('hasVue')} hash={cur.get('hash')}")

if not cur.get('hasVue'):
    ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'")
    for attempt in range(10):
        time.sleep(3)
        check = ev("({hasVue:!!document.getElementById('app')?.__vue__,text:(document.body.innerText||'').substring(0,30)})")
        if check.get('hasVue'): break

ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")
verify = ev("(function(){var s=document.getElementById('app')?.__vue__?.$store;return{token:s?.state?.login?.token?'ok':'empty',userInfo:!!s?.state?.login?.userInfo}})()")
print(f"  token={verify.get('token') if verify else 'N/A'} userInfo={verify.get('userInfo') if verify else 'N/A'}")

# ===== STEP 2: 导航到企业开办专区 → 开始办理 =====
print("\nSTEP 2: 企业专区 → 开始办理")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm?.$router)try{vm.$router.push('/index/enterprise/enterprise-zone')}catch(e){}})()""")
time.sleep(5)
ev("""(function(){
    var all=document.querySelectorAll('button,div,span,a');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='开始办理'&&all[i].offsetParent!==null&&all[i].children.length<3){all[i].click();return}
    }
})()""")
time.sleep(5)
page2 = ev("({hash:location.hash})")
print(f"  hash={page2.get('hash')}")

# ===== STEP 3: toSelectName → getHandleBusiness（注册namenotice路由）=====
print("\nSTEP 3: toSelectName → getHandleBusiness")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var route=vm?.$route;var matched=route?.matched||[];
    for(var i=0;i<matched.length;i++){
        var m=matched[i];if(m.instances?.default){
            var inst=m.instances.default;
            if(typeof inst.toSelectName==='function'){inst.toSelectName();break}
        }
    }
})()""")
time.sleep(3)
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var route=vm?.$route;var matched=route?.matched||[];
    for(var i=0;i<matched.length;i++){
        var m=matched[i];if(m.instances?.default){
            var inst=m.instances.default;
            if(typeof inst.getHandleBusiness==='function'){inst.getHandleBusiness({entType:'1100'});return}
        }
    }
})()""")
time.sleep(3)

# 现在namenotice路由已注册，但当前页面因nameId=undefined异常
# 关键：用干净URL重新导航（不带nameId）
print("\nSTEP 4: 用干净URL导航到申报须知（不带nameId）")
# 先回首页避免路由冲突
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm?.$router)try{vm.$router.push('/index/page')}catch(e){}})()""")
time.sleep(2)

# 用干净URL导航
nav = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(!vm?.$router)return{error:'no_router'};
    try{vm.$router.push('/namenotice/declaration-instructions?busiType=02&entType=1100');return{ok:true}}catch(e){return{error:e.message}}
})()""")
print(f"  nav: {nav}")
time.sleep(8)

# 检查是否跳转到表单
page3 = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,200)};
})()""")
print(f"  hash={page3.get('hash')} forms={page3.get('formCount',0)} inputs={page3.get('inputCount',0)}")

# 等待
fc = page3.get('formCount',0)
if fc == 0:
    for attempt in range(10):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
        fc = (check or {}).get('formCount',0)
        h = (check or {}).get('hash','?')
        print(f"  wait {attempt+1}: hash={h} forms={fc}")
        if fc > 0: break

screenshot("step4_form")

if fc == 0:
    print("  ❌ 表单未加载！")
    debug = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var route=vm?.$route;
        return{route:route?.path,hash:location.hash,text:(document.body.innerText||'').substring(0,150)};
    })()""")
    print(f"  debug: {json.dumps(debug or {}, ensure_ascii=False)[:300]}")
    log("95.表单加载失败", debug or {})
    ws.close()
    sys.exit(1)

# ===== STEP 5: 表单探查 =====
print("\nSTEP 5: 表单探查")
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
    log("95.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[]),"stepTitle":form.get("stepTitle","")})
    log("95a.字段详情", {"fields":form.get("fields",[])[:60]})
    print(f"  步骤: {json.dumps(form.get('steps',[]), ensure_ascii=False)}")
    print(f"  当前步骤: {form.get('stepTitle','')}")
    print(f"  按钮: {form.get('buttons',[])}")
    print(f"  字段({len(form.get('fields',[]))}个):")
    for f in form.get("fields",[]):
        print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')} val={f.get('val','')}")

# ===== STEP 6: 填写 =====
print("\nSTEP 6: 逐字段填写")
MATERIALS = {
    "公司名称":"广西智信数据科技有限公司","企业名称":"广西智信数据科技有限公司",
    "名称":"广西智信数据科技有限公司","注册资本":"100",
    "经营范围":"软件开发、信息技术咨询服务","住所":"南宁市青秀区民族大道166号",
    "法定代表人":"陈明辉","身份证":"450103199001151234",
    "联系电话":"13877151234","邮箱":"chenmh@example.com",
    "邮政编码":"530028","监事":"李芳","财务负责人":"张丽华",
    "联络员":"王小明","从业人数":"5","股东":"陈明辉",
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
log("96.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
    issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
for r in ok: print(f"    ✅ {r.get('label','')}")
for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

screenshot("step6_filled")

# ===== STEP 7: 遍历步骤直到提交页 =====
print("\nSTEP 7: 遍历步骤直到提交页（不点提交）")
for step in range(8):
    current = ev("""(function(){
        var steps=document.querySelectorAll('.el-step');
        var active=null;
        for(var i=0;i<steps.length;i++){
            if(steps[i].className?.includes('is-active')){
                active={i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||''};break;
            }
        }
        var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20});
        var hasSubmit=btns.some(function(t){return t.includes('提交')&&!t.includes('暂存')});
        var hasNext=btns.some(function(t){return t.includes('下一步')});
        return{step:active,hasSubmit:hasSubmit,hasNext:hasNext,
        buttons:btns.filter(function(t){return t.includes('下一步')||t.includes('提交')||t.includes('保存')||t.includes('暂存')||t.includes('预览')}).slice(0,5),
        formCount:document.querySelectorAll('.el-form-item').length};
    })()""")
    
    step_info = current.get('step') or {}
    print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)}")
    print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
    
    auth=ev("""(function(){
        var t=document.body.innerText||'';var html=document.body.innerHTML||'';
        return{faceAuth:t.includes('人脸')||html.includes('faceAuth'),smsAuth:t.includes('验证码')||t.includes('短信'),
        realName:t.includes('实名认证')||t.includes('实名'),signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),
        digitalCert:t.includes('数字证书')||t.includes('CA锁'),caAuth:t.includes('CA认证')||html.includes('caAuth')};
    })()""")
    if any(auth.values() if auth else []):
        print(f"  ⚠️ 认证要求: {auth}")
        add_auth_finding({"step":step,"title":step_info.get('title',''),"auth":auth})
    
    if current.get('hasSubmit'):
        print(f"\n  🔴 检测到提交按钮！停止（不点击提交）")
        log("97.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
        screenshot("step7_submit_page")
        break
    
    if current.get('hasNext'):
        print(f"  点击下一步...")
        ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].textContent?.trim()?.includes('下一步')&&btns[i].offsetParent!==null){btns[i].click();return}
            }
        })()""")
        time.sleep(5)
        errs = ev("""(function(){var msgs=document.querySelectorAll('.el-message,[class*="error"]');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,3)})()""")
        if errs:
            print(f"  ⚠️ 验证错误: {errs}")
            log(f"97b.step{step}_errors", {"errors":errs})
            break
    else:
        print(f"  无下一步按钮，停止")
        break

screenshot("step7_final")
print("\n" + "=" * 60)
print("E2E 测试完成")
print("=" * 60)
ws.close()
print("\n✅ e2e_final5.py 完成")
