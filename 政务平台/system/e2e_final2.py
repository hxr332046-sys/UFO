#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final2: 完整流程 企业专区→开始办理→select-prise→getHandleBusiness→表单→填写→认证"""
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

# ===== STEP 1: 恢复Vuex token =====
print("STEP 1: 恢复Vuex token")
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
    // 获取userInfo
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
verify = ev("(function(){var s=document.getElementById('app')?.__vue__?.$store;return{token:s?.state?.login?.token?'ok':'empty',userInfo:!!s?.state?.login?.userInfo,hash:location.hash}})()")
print(f"  token={verify.get('token')} userInfo={verify.get('userInfo')} hash={verify.get('hash')}")

# ===== STEP 2: 导航到企业开办专区 =====
print("\nSTEP 2: 导航到企业开办专区")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/enterprise/enterprise-zone');
})()""")
time.sleep(5)
page2 = ev("({hash:location.hash, text:(document.body.innerText||'').substring(0,100)})")
print(f"  hash={page2.get('hash')} text={page2.get('text','')[:60]}")

# ===== STEP 3: 点击开始办理 =====
print("\nSTEP 3: 点击开始办理")
ev("""(function(){
    var all=document.querySelectorAll('button,div,span,a');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='开始办理'&&all[i].offsetParent!==null&&all[i].children.length<3){
            all[i].click();return{clicked:'开始办理'};
        }
    }
    // 也找包含"开始办理"的按钮
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){
            btns[i].click();return{clicked:'btn_开始办理'};
        }
    }
    return{error:'not_found'};
})()""")
time.sleep(3)
page3 = ev("({hash:location.hash, text:(document.body.innerText||'').substring(0,100)})")
print(f"  hash={page3.get('hash')} text={page3.get('text','')[:60]}")

# ===== STEP 4: 导航到select-prise并调用toSelectName =====
print("\nSTEP 4: 导航到select-prise")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/select-prise?entType=1100');
})()""")
time.sleep(5)

# 调用toSelectName进入名称选择模式
print("  调用toSelectName...")
ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(inst&&inst.toSelectName)inst.toSelectName();
    // 也检查select-prise
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(inst&&inst.toSelectName)inst.toSelectName();
})()""")
time.sleep(5)

page4 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,100)})")
print(f"  hash={page4.get('hash')} forms={page4.get('formCount',0)} text={page4.get('text','')[:60]}")

# ===== STEP 5: 调用getHandleBusiness（关键！注册namenotice路由并导航到表单）=====
print("\nSTEP 5: 调用getHandleBusiness（注册namenotice路由）")
result = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    // 找select-prise组件
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst||!inst.getHandleBusiness){
        // 也找without-name组件
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
        }
    }
    if(!inst||!inst.getHandleBusiness)return{error:'no_getHandleBusiness',routeName:route?.name};
    
    // 调用getHandleBusiness，参数格式参考源码
    inst.getHandleBusiness({entType:'1100'});
    return{called:true,routeName:route?.name};
})()""")
print(f"  result: {result}")
time.sleep(8)

# 检查是否到了表单
page5 = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,200)};
})()""")
print(f"  hash={page5.get('hash')} forms={page5.get('formCount',0)} inputs={page5.get('inputCount',0)}")

# 等待加载
fc = page5.get('formCount',0)
if fc == 0:
    for attempt in range(10):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
        fc = (check or {}).get('formCount',0)
        h = (check or {}).get('hash','?')
        print(f"  wait {attempt+1}: hash={h} forms={fc}")
        if fc > 0: break

screenshot("step5_form")

if fc == 0:
    print("  ❌ 表单未加载！尝试直接导航到flow路由...")
    # 如果namenotice路由已注册，直接导航
    nav2 = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(!vm?.$router)return{error:'no_router'};
        // 检查flow路由是否可用
        var m=vm.$router.resolve('/flow/base/basic-info');
        if(m.route.path!=='/404'){
            try{vm.$router.push('/flow/base/basic-info');return{ok:true}}catch(e){return{error:e.message}}
        }
        return{error:'flow_route_404'};
    })()""")
    print(f"  direct nav: {nav2}")
    time.sleep(5)
    
    page6 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
    fc = page6.get('formCount',0)
    print(f"  after direct nav: hash={page6.get('hash')} forms={fc}")

if fc == 0:
    print("\n  ❌ 所有方法失败！需要手动操作")
    log("80.表单加载失败", {"reason":"getHandleBusiness未导航到表单"})
    ws.close()
    sys.exit(1)

# ===== STEP 6: 表单详细探查 =====
print("\nSTEP 6: 表单详细探查")
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
    log("80.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[]),"stepTitle":form.get("stepTitle","")})
    log("80a.字段详情", {"fields":form.get("fields",[])[:60]})
    print(f"  步骤: {json.dumps(form.get('steps',[]), ensure_ascii=False)}")
    print(f"  当前步骤: {form.get('stepTitle','')}")
    print(f"  按钮: {form.get('buttons',[])}")
    print(f"  字段({len(form.get('fields',[]))}个):")
    for f in form.get("fields",[]):
        print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')} val={f.get('val','')}")

# ===== STEP 7: 逐字段填写 =====
print("\nSTEP 7: 逐字段填写")
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
log("81.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
    issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
for r in ok: print(f"    ✅ {r.get('label','')}")
for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

screenshot("step7_filled")

# ===== STEP 8: 遍历步骤直到提交页 =====
print("\nSTEP 8: 遍历步骤直到提交页（不点提交）")
for step in range(8):
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
        var hasSubmit=btns.some(function(t){return t.includes('提交')&&!t.includes('暂存')});
        var hasNext=btns.some(function(t){return t.includes('下一步')});
        return{step:active,hasSubmit:hasSubmit,hasNext:hasNext,
        buttons:btns.filter(function(t){return t.includes('下一步')||t.includes('提交')||t.includes('保存')||t.includes('暂存')||t.includes('预览')}).slice(0,5),
        formCount:document.querySelectorAll('.el-form-item').length,
        text:(document.body.innerText||'').substring(0,200)};
    })()""")
    
    step_info = current.get('step') or {}
    print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)}")
    print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
    
    # 认证检测
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
    if any(auth.values() if auth else []):
        print(f"  ⚠️ 认证要求: {auth}")
        add_auth_finding(f"步骤{step}-{step_info.get('title','')}", auth)
        log(f"82.step{step}_auth", auth)
    
    # 检测到提交按钮 → 停止
    if current.get('hasSubmit'):
        print(f"\n  🔴 检测到提交按钮！停止（不点击提交）")
        log("83.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
        screenshot("step8_submit_page")
        break
    
    # 点击下一步
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
                if(t&&t.length<80&&t.length>2)r.push(t);
            }
            return r.slice(0,3);
        })()""")
        if errs:
            print(f"  ⚠️ 验证错误: {errs}")
            log(f"82b.step{step}_errors", {"errors":errs})
            break
    else:
        print(f"  无下一步按钮，停止")
        break

screenshot("step8_final")

print("\n" + "=" * 60)
print("E2E 测试完成")
print("=" * 60)
ws.close()
print("\n✅ e2e_final2.py 完成")
