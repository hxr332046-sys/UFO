#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step28: 导航到设立登记表单 → 探查全部字段 → 填写 → 下一步 → 记录认证"""
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

# 1. 恢复token
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
})()""")

# 2. 导航到申报须知页面（会自动跳转到表单）
print("=== 1. 导航到设立登记表单 ===")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/namenotice/declaration-instructions?busiType=02&entType=1100');
})()""")
time.sleep(8)

page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  hash: {(page or {}).get('hash','?')}")
print(f"  forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:200]}")

# 等待加载
fc = (page or {}).get('formCount',0)
if fc == 0:
    print("  等待加载...")
    for attempt in range(8):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
        fc = (check or {}).get('formCount',0)
        print(f"  {attempt+1}: hash={(check or {}).get('hash')} forms={fc}")
        if fc > 0:
            break

if fc == 0:
    print("  ❌ 表单未加载！")
    ws.close()
    sys.exit(1)

# 3. 详细探查表单
print("\n=== 2. 表单详细探查 ===")
form = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<fi.length;i++){
        var item=fi[i],label=item.querySelector('.el-form-item__label');
        var input=item.querySelector('.el-input__inner,.el-textarea__inner');
        var sel=item.querySelector('.el-select');
        var upload=item.querySelector('.el-upload');
        var radio=item.querySelector('.el-radio');
        var checkbox=item.querySelector('.el-checkbox');
        var tp='unknown';
        if(input)tp=input.tagName==='TEXTAREA'?'textarea':'input';
        if(sel)tp='select';
        if(upload)tp='upload';
        if(radio)tp='radio';
        if(checkbox)tp='checkbox';
        var info={i:i,label:label?.textContent?.trim()||'',type:tp,required:item.className.includes('is-required')};
        if(input){info.ph=input.placeholder||'';info.disabled=input.disabled;info.val=(input.value||'').substring(0,20)}
        if(sel){info.disabled=sel.className?.includes('disabled')}
        r.push(info);
    }
    // 步骤条
    var steps=document.querySelectorAll('.el-step');
    var stepList=[];
    for(var i=0;i<steps.length;i++){
        var title=steps[i].querySelector('.el-step__title');
        var active=steps[i].className?.includes('is-active')||steps[i].className?.includes('is-finish');
        stepList.push({i:i,title:title?.textContent?.trim()||'',active:active});
    }
    // 按钮
    var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){
        return b.textContent?.trim()||'';
    }).filter(function(t){return t&&t.length<20}).slice(0,20);
    // 当前步骤标题
    var stepTitle=document.querySelector('.el-step.is-active .el-step__title')?.textContent?.trim()||'';
    return{fields:r,steps:stepList,buttons:btns,stepTitle:stepTitle,pageTitle:document.querySelector('h3,h4,.page-title,[class*="title"]')?.textContent?.trim()||''};
})()""")
if form:
    log("60.设立登记表单", {
        "formCount":len(form.get("fields",[])),
        "steps":form.get("steps",[]),
        "buttons":form.get("buttons",[]),
        "stepTitle":form.get("stepTitle",""),
        "pageTitle":form.get("pageTitle","")
    })
    log("60a.字段详情", {"fields":form.get("fields",[])[:60]})
    print(f"  步骤: {form.get('steps',[])}")
    print(f"  当前步骤: {form.get('stepTitle','')}")
    print(f"  按钮: {form.get('buttons',[])}")
    print(f"  字段:")
    for f in form.get("fields",[])[:50]:
        print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')} val={f.get('val','')}")

# 4. 逐字段填写
print("\n=== 3. 逐字段填写 ===")
# 更全面的材料映射
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
log("61.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
    issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
for r in ok: print(f"    ✅ {r.get('label','')}")
for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

# 5. 截图（填写后）
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step28_filled.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

# 6. 找下一步按钮并点击
print("\n=== 4. 找下一步/保存按钮 ===")
btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    var r=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t&&(t.includes('下一步')||t.includes('保存')||t.includes('暂存')||t.includes('提交')||t.includes('预览'))&&btns[i].offsetParent!==null){
            r.push({i:i,text:t,type:btns[i].getAttribute('type')||'',cls:btns[i].className?.substring(0,30)||''});
        }
    }
    return r;
})()""")
print(f"  buttons: {btns}")

# 安装XHR拦截器
ev("""(function(){
    window.__apiLogs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(method,url){
        this.__url=url;this.__method=method;
        return origOpen.apply(this,arguments);
    };
    XMLHttpRequest.prototype.send=function(){
        var xhr=this;
        xhr.addEventListener('loadend',function(){
            window.__apiLogs.push({method:xhr.__method,url:xhr.__url,status:xhr.status,response:xhr.responseText?.substring(0,150)||''});
        });
        return origSend.apply(this,arguments);
    };
})()""")

# 点击"下一步"（不点"提交"！）
for b in (btns or []):
    if '下一步' in b.get('text','') or '暂存' in b.get('text','') or '保存' in b.get('text',''):
        print(f"\n=== 5. 点击 {b.get('text')} ===")
        ev(f"""(function(){{
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){{
                if(btns[i].textContent?.trim()?.includes('{b.get("text")}')&&btns[i].offsetParent!==null){{
                    btns[i].click();return;
                }}
            }}
        }})()""")
        time.sleep(5)
        break

# 7. 检查API日志
logs = ev("window.__apiLogs.slice(-10)")
if logs:
    print("\n=== 6. API日志 ===")
    for l in logs:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1]
        print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:80]}")

# 8. 检查下一步页面
page2 = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"\n=== 7. 下一步页面 ===")
print(f"  hash: {(page2 or {}).get('hash','?')}")
print(f"  forms: {(page2 or {}).get('formCount',0)} inputs: {(page2 or {}).get('inputCount',0)}")
print(f"  text: {(page2 or {}).get('text','')[:250]}")

# 9. 认证检测
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
        caAuth:t.includes('CA认证')||t.includes('CA锁')||html.includes('caAuth'),
        ukeyAuth:t.includes('UKey')||t.includes('U盾'),
        passwordAuth:t.includes('密码')
    };
})()""")
log("62.认证检测",auth)
print(f"  认证: {auth}")

# 10. 如果有错误消息
errors = ev("""(function(){
    var msgs=document.querySelectorAll('.el-message,.el-message-box,.el-notification,.el-alert,[class*="error"],[class*="warning"]');
    var r=[];
    for(var i=0;i<msgs.length;i++){
        var t=msgs[i].textContent?.trim()||'';
        if(t&&(t.includes('错误')||t.includes('失败')||t.includes('必填')||t.includes('请')||t.includes('不能为空'))&&t.length<100){
            r.push({cls:msgs[i].className?.substring(0,25)||'',text:t});
        }
    }
    return r.slice(0,10);
})()""")
if errors:
    print(f"  错误: {errors}")
    log("62b.表单错误", {"errors":errors})

# 截图
try:
    ws.send(json.dumps({"id":8889,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8889:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step28_next.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step28 完成")
