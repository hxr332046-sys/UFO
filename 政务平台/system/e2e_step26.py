#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step26: getData提交名称 → startSheli进入设立登记 → 填写 → 记录认证"""
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

# 2. 确保在select-prise页面
print("=== 1. 确认页面 ===")
state = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  hash: {(state or {}).get('hash','?')} forms: {(state or {}).get('formCount',0)}")

# 3. 确保在"其他来源名称"模式（isOther=true）
print("\n=== 2. 确保isOther模式 ===")
mode = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    if(!inst.$data.isOther){
        inst.toOther();
    }
    return{isOther:inst.$data.isOther,form:JSON.stringify(inst.$data.form)};
})()""")
print(f"  mode: {mode}")

# 4. 确保表单已填写
print("\n=== 3. 填写表单 ===")
fill = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    
    // 直接设置form数据
    inst.$data.form.name='广西智信数据科技有限公司';
    inst.$data.form.numbers='GX20260413001';
    inst.$forceUpdate();
    
    // 也通过input设置
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        var input=fi[i].querySelector('.el-input__inner');
        var lt=label?.textContent?.trim()||'';
        if(input&&!input.disabled){
            var val='';
            if(lt.includes('企业名称'))val='广西智信数据科技有限公司';
            else if(lt.includes('保留单号'))val='GX20260413001';
            if(val){
                var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                setter.call(input,val);
                input.dispatchEvent(new Event('input',{bubbles:true}));
                input.dispatchEvent(new Event('change',{bubbles:true}));
            }
        }
    }
    return{form:JSON.stringify(inst.$data.form)};
})()""")
print(f"  fill: {fill}")

# 5. 安装XHR拦截器
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
            window.__apiLogs.push({method:xhr.__method,url:xhr.__url,status:xhr.status,response:xhr.responseText?.substring(0,200)||''});
        });
        return origSend.apply(this,arguments);
    };
})()""")

# 6. 先调用getData提交名称信息
print("\n=== 4. 调用getData ===")
get_data = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    try{
        inst.getData();
        return{called:'getData'};
    }catch(e){return{error:e.message}}
})()""")
print(f"  getData: {get_data}")
time.sleep(5)

# 7. 检查API日志
logs = ev("window.__apiLogs")
if logs:
    print("\n=== 5. API日志 ===")
    for l in logs:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1]
        print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:100]}")

# 8. 检查页面
page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
print(f"\n=== 6. 页面 ===")
print(f"  hash: {(page or {}).get('hash','?')} forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:150]}")

# 9. 如果还在select-prise，尝试startSheli
if (page or {}).get('hash','').startswith('#/index/select-prise'):
    print("\n=== 7. 调用startSheli ===")
    ev("window.__apiLogs=[]")
    sheli = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var inst=null;
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
        }
        if(!inst)return{error:'no_instance'};
        try{
            // startSheli需要一个参数（企业信息对象）
            var entInfo={entType:'1100',name:'广西智信数据科技有限公司',numbers:'GX20260413001'};
            inst.startSheli(entInfo);
            return{called:'startSheli'};
        }catch(e){return{error:e.message}}
    })()""")
    print(f"  startSheli: {sheli}")
    time.sleep(5)
    
    logs2 = ev("window.__apiLogs")
    if logs2:
        for l in logs2:
            url_short = (l.get('url','') or '').split('?')[0].split('/')[-1]
            print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:100]}")
    
    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,300)})")
    print(f"  after: hash={(page2 or {}).get('hash')} forms={(page2 or {}).get('formCount',0)} inputs={(page2 or {}).get('inputCount',0)}")
    print(f"  text: {(page2 or {}).get('text','')[:200]}")

# 10. 也尝试getHandleBusiness
if ev("document.querySelectorAll('.el-form-item').length") in (0, None, 2):
    print("\n=== 8. 调用getHandleBusiness ===")
    ev("window.__apiLogs=[]")
    business = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var inst=null;
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
        }
        if(!inst)return{error:'no_instance'};
        try{
            inst.getHandleBusiness({entType:'1100'});
            return{called:'getHandleBusiness'};
        }catch(e){return{error:e.message}}
    })()""")
    print(f"  getHandleBusiness: {business}")
    time.sleep(5)
    
    page3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after: hash={(page3 or {}).get('hash')} forms={(page3 or {}).get('formCount',0)} inputs={(page3 or {}).get('inputCount',0)}")
    print(f"  text: {(page3 or {}).get('text','')[:150]}")

# 11. 如果到了设立登记表单页面，探查和填写
final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
fc = (final or {}).get('formCount',0)
ic = (final or {}).get('inputCount',0)
log("55.名称提交后状态", {"hash":(final or {}).get("hash"),"formCount":fc,"inputCount":ic})

if fc > 2 or ic > 2:
    print("\n=== 9. 设立登记表单探查 ===")
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
        return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,20)};
    })()""")
    if form:
        log("56.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("56a.字段详情", {"fields":form.get("fields",[])[:60]})
        for f in form.get("fields",[])[:40]:
            print(f"  [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')}")

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
        log("57.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
        print(f"\n  填写: ok={len(ok)} fail={len(fail)}")

        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
        if auth: log("58.认证检测",auth); print(f"  认证: {auth}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step26.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step26 完成")
