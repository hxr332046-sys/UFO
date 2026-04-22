#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final6: 直接在当前表单页面 → 探查 → 填写 → 遍历步骤 → 认证检测"""
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

# ===== STEP 1: 诊断当前页面 =====
print("STEP 1: 诊断当前页面")
diag = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    return{
        hasVue:!!vm,hasStore:!!store,hasRouter:!!vm?.$router,
        loginToken:store?.state?.login?.token?'exists':'empty',
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        text:(document.body.innerText||'').substring(0,100)
    };
})()""")
print(f"  hasVue={diag.get('hasVue')} hash={diag.get('hash')} forms={diag.get('formCount',0)} inputs={diag.get('inputCount',0)}")
print(f"  loginToken={diag.get('loginToken')}")
print(f"  text={diag.get('text','')[:60]}")

# 恢复token
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

fc = diag.get('formCount',0)
if fc == 0:
    print("  ❌ 当前无表单！")
    ws.close()
    sys.exit(1)

# ===== STEP 2: 表单探查 =====
print("\nSTEP 2: 表单探查")
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
    log("100.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[]),"stepTitle":form.get("stepTitle","")})
    log("100a.字段详情", {"fields":form.get("fields",[])[:60]})
    print(f"  步骤: {json.dumps(form.get('steps',[]), ensure_ascii=False)}")
    print(f"  当前步骤: {form.get('stepTitle','')}")
    print(f"  按钮: {form.get('buttons',[])}")
    print(f"  字段({len(form.get('fields',[]))}个):")
    for f in form.get("fields",[]):
        print(f"    [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')} val={f.get('val','')}")

# ===== STEP 3: 填写 =====
print("\nSTEP 3: 逐字段填写")
MATERIALS = {
    "企业名称":"广西智信数据科技有限公司","注册资本":"100",
    "经营范围":"软件开发","住所":"南宁市","详细地址":"民族大道166号",
    "生产经营地详细地址":"民族大道166号","联系电话":"13877151234",
    "邮政编码":"530028","从业人数":"5",
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
log("101.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
    issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
for r in ok: print(f"    ✅ {r.get('label','')}")
for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

screenshot("step3_filled")

# ===== STEP 4: 遍历所有步骤直到提交页 =====
print("\nSTEP 4: 遍历步骤直到提交页（不点提交）")
all_auth_findings = []
for step in range(10):
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
        var hasSave=btns.some(function(t){return t.includes('保存')||t.includes('暂存')});
        return{step:active,hasSubmit:hasSubmit,hasNext:hasNext,hasSave:hasSave,
        buttons:btns.filter(function(t){return t.includes('下一步')||t.includes('提交')||t.includes('保存')||t.includes('暂存')||t.includes('预览')}).slice(0,5),
        formCount:document.querySelectorAll('.el-form-item').length,
        hash:location.hash,
        text:(document.body.innerText||'').substring(0,200)};
    })()""")
    
    step_info = current.get('step') or {}
    print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)} hash={current.get('hash','')[:30]}")
    print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
    
    # 认证检测
    auth=ev("""(function(){
        var t=document.body.innerText||'';var html=document.body.innerHTML||'';
        return{faceAuth:t.includes('人脸')||html.includes('faceAuth'),smsAuth:t.includes('验证码')||t.includes('短信'),
        realName:t.includes('实名认证')||t.includes('实名'),signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),
        digitalCert:t.includes('数字证书')||t.includes('CA锁'),caAuth:t.includes('CA认证')||html.includes('caAuth'),
        ukeyAuth:t.includes('UKey')||t.includes('U盾')};
    })()""")
    if any(auth.values() if auth else []):
        print(f"  ⚠️ 认证要求: {auth}")
        finding = {"step":step,"title":step_info.get('title',''),"auth":auth}
        add_auth_finding(finding)
        all_auth_findings.append(finding)
    
    # 检测到提交按钮 → 停止
    if current.get('hasSubmit'):
        print(f"\n  🔴 检测到提交按钮！停止（不点击提交）")
        log("102.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
        screenshot("step4_submit_page")
        break
    
    # 点击"保存并下一步"或"下一步"
    clicked = False
    for btn_text in ['保存并下一步','保存至下一步','下一步']:
        if current.get('hasNext') or current.get('hasSave'):
            print(f"  尝试点击: {btn_text}")
            click_result = ev(f"""(function(){{
                var btns=document.querySelectorAll('button,.el-button');
                for(var i=0;i<btns.length;i++){{
                    if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{
                        btns[i].click();return{{clicked:true,text:'{btn_text}'}};
                    }}
                }}
                return{{clicked:false}};
            }})()""")
            if click_result and click_result.get('clicked'):
                print(f"  ✅ 点击成功: {btn_text}")
                clicked = True
                break
    
    if not clicked:
        print(f"  ⚠️ 无可点击按钮，停止")
        break
    
    time.sleep(5)
    
    # 检查错误
    errs = ev("""(function(){
        var msgs=document.querySelectorAll('.el-message,[class*="error"],.el-form-item__error');
        var r=[];
        for(var i=0;i<msgs.length;i++){
            var t=msgs[i].textContent?.trim()||'';
            if(t&&t.length<80&&t.length>2)r.push(t);
        }
        return r.slice(0,5);
    })()""")
    if errs:
        print(f"  ⚠️ 错误: {errs}")
        log(f"102b.step{step}_errors", {"errors":errs})
        # 如果是验证错误，可能需要填写更多字段
        # 但不中断流程

screenshot("step4_final")

# ===== 最终总结 =====
print("\n" + "=" * 60)
print("E2E 测试总结")
print("=" * 60)

# 读取报告
from e2e_report import load
load()
print(f"  总步骤数: {len(report.get('steps',[]))}")
print(f"  认证发现: {len(report.get('auth_findings',[]))}")
print(f"  问题数: {len(report.get('issues',[]))}")

for af in report.get('auth_findings',[]):
    print(f"  🔐 {af}")

log("103.E2E测试完成", {
    "totalSteps":len(report.get('steps',[])),
    "authFindings":len(report.get('auth_findings',[])),
    "issues":len(report.get('issues',[]))
})

ws.close()
print("\n✅ e2e_final6.py 完成")
