#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step18: 恢复Vuex token → 导航企业开办专区 → 开始办理 → 等待表单 → 填写"""
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

# 1. 恢复Vuex登录态（关键！）
print("=== 1. 恢复Vuex登录态 ===")
restore = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(!store)return'no_store';
    var t=localStorage.getItem('top-token')||'';
    store.commit('login/SET_TOKEN',t);
    return{token:String(store.state.login.token).substring(0,10)+'...',len:String(store.state.login.token).length};
})()""")
print(f"  restore: {restore}")

# 2. 导航到企业开办专区
print("\n=== 2. 导航到企业开办专区 ===")
nav = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(!vm?.$router)return'no_router';
    try{vm.$router.push('/index/enterprise/enterprise-zone');return'ok'}catch(e){return e.message}
})()""")
print(f"  nav: {nav}")
time.sleep(5)

page = ev("({hash:location.hash, text:(document.body.innerText||'').substring(0,150)})")
print(f"  hash: {page.get('hash') if page else 'N/A'}")
print(f"  text: {(page or {}).get('text','')[:100]}")

# 3. 点击"开始办理"按钮
print("\n=== 3. 点击开始办理 ===")
click = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('开始办理')&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:t};
        }
    }
    return'not_found';
})()""")
print(f"  click: {click}")
time.sleep(8)

# 4. 检查页面
page2 = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        text:(document.body.innerText||'').substring(0,400)
    };
})()""")
print(f"  hash: {(page2 or {}).get('hash','?')}")
print(f"  forms: {(page2 or {}).get('formCount',0)}")
print(f"  inputs: {(page2 or {}).get('inputCount',0)}")
print(f"  text: {(page2 or {}).get('text','')[:200]}")

# 5. 等待表单加载（最多30秒）
form_count = (page2 or {}).get('formCount',0)
input_count = (page2 or {}).get('inputCount',0)
if form_count == 0 and input_count == 0:
    print("\n=== 5. 等待表单加载 ===")
    for attempt in range(10):
        time.sleep(3)
        check = ev("({formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,hash:location.hash})")
        fc = (check or {}).get('formCount',0)
        ic = (check or {}).get('inputCount',0)
        h = (check or {}).get('hash','?')
        print(f"  {attempt+1}: hash={h} forms={fc} inputs={ic}")
        if fc > 0 or ic > 0:
            form_count = fc
            input_count = ic
            break

# 6. 如果有表单，探查
if form_count > 0 or input_count > 0:
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
        for(var i=0;i<steps.length;i++){stepList.push(steps[i].querySelector('.el-step__title')?.textContent?.trim()||'')}
        return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,20)};
    })()""")
    if form:
        log("39.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("39a.字段详情", {"fields":form.get("fields",[])[:60]})
        for f in form.get("fields",[])[:40]:
            print(f"  [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')}")

        # 7. 逐字段填写
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
        log("40.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
        print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
        for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

        # 8. 认证检测
        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
        if auth:
            log("41.认证检测",auth)
            print(f"  认证: {auth}")

        # 9. 截图
        try:
            ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
            for _ in range(10):
                try:
                    ws.settimeout(10);r=json.loads(ws.recv())
                    if r.get("id")==8888:
                        d=r.get("result",{}).get("data","")
                        if d:
                            p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step18_form.png")
                            with open(p,"wb") as f:f.write(base64.b64decode(d))
                            print(f"\n📸 {p}")
                        break
                except:break
        except:pass
else:
    # 没有表单 - 深入分析原因
    print("\n=== 6. 无表单，分析原因 ===")
    # 检查API错误
    api_check = ev("""(function(){
        var topToken=localStorage.getItem('top-token')||'';
        var xhr=new XMLHttpRequest();
        xhr.open('POST','/icpsp-api/v4/pc/register/apply',false);
        xhr.setRequestHeader('Content-Type','application/json');
        xhr.setRequestHeader('top-token',topToken);
        xhr.setRequestHeader('Authorization',topToken);
        try{xhr.send(JSON.stringify({entType:'1100'}))}catch(e){return{error:e.message}}
        return{status:xhr.status,body:xhr.responseText?.substring(0,200)};
    })()""")
    print(f"  apply API: {api_check}")
    
    # 检查console错误（通过Performance/Log API）
    # 检查网络请求
    net_check = ev("""(function(){
        var entries=performance.getEntriesByType('resource');
        var recent=entries.filter(function(e){return e.startTime>performance.now()-30000});
        return{total:recent.length,failed:recent.filter(function(e){return e.transferSize===0&&e.responseStatus>400}).map(function(e){return e.name?.substring(e.name.lastIndexOf('/')+1)+'('+e.responseStatus+')'}).slice(0,10)};
    })()""")
    print(f"  network: {net_check}")

    # 截图
    try:
        ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
        for _ in range(10):
            try:
                ws.settimeout(10);r=json.loads(ws.recv())
                if r.get("id")==8888:
                    d=r.get("result",{}).get("data","")
                    if d:
                        p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step18_noform.png")
                        with open(p,"wb") as f:f.write(base64.b64decode(d))
                        print(f"\n📸 {p}")
                    break
            except:break
    except:pass

ws.close()
print("\n✅ Step18 完成")
