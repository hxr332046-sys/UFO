#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step16: 点击设立登记 → 进入表单 → 探查 → 填写 → 记录认证"""
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

# 1. 确认当前页面
print("=== 1. 当前页面 ===")
state = ev("""(function(){
    return{hash:location.hash,text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  hash: {state.get('hash')}")
print(f"  text: {(state.get('text','') or '')[:200]}")

# 2. 点击"设立登记"
print("\n=== 2. 点击设立登记 ===")
click = ev("""(function(){
    var all=document.querySelectorAll('div,span,a,h3,h4,p,li');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='设立登记'&&all[i].offsetParent!==null){
            all[i].click();
            return{clicked:t,tag:all[i].tagName,cls:all[i].className?.substring(0,40)||''};
        }
    }
    // 也找包含"设立登记"的卡片标题
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.startsWith('设立登记')&&t.length<30&&all[i].offsetParent!==null&&all[i].children.length<3){
            all[i].click();
            return{clicked:t,tag:all[i].tagName};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click: {click}")
time.sleep(5)

# 3. 检查导航结果
page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"  page: hash={page.get('hash')} forms={page.get('formCount')} inputs={page.get('inputCount')}")
print(f"  text: {(page.get('text','') or '')[:300]}")

# 4. 等待加载
if page.get('formCount',0) == 0 and page.get('inputCount',0) == 0:
    print("\n=== 4. 等待加载 ===")
    for attempt in range(8):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,text:(document.body.innerText||'').substring(0,200)})")
        print(f"  attempt {attempt+1}: hash={check.get('hash')} forms={check.get('formCount')} inputs={check.get('inputCount')}")
        if check.get('formCount',0) > 0 or check.get('inputCount',0) > 0:
            break
        # 如果hash变了，说明导航了
        if check.get('hash') != page.get('hash'):
            print(f"  hash changed to: {check.get('hash')}")
            page = check
            break

# 5. 如果到了新页面，继续探查
page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,500)};
})()""")
print(f"\n=== 5. 当前状态 ===")
print(f"  hash: {page.get('hash')}")
print(f"  forms: {page.get('formCount')}")
print(f"  inputs: {page.get('inputCount')}")
print(f"  text: {(page.get('text','') or '')[:300]}")

# 6. 如果有表单，详细探查
if page.get('formCount',0) > 0 or page.get('inputCount',0) > 0:
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
    log("35.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
    log("35a.字段详情", {"fields":form.get("fields",[])[:60]})
    for f in (form.get("fields",[])[:40]):
        print(f"  [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')}")

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
    log("36.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
        issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
    print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
    for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

    # 认证检测
    auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
    log("37.认证检测",auth)
    print(f"  认证: {auth}")

    # 截图
    try:
        ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
        while True:
            try:
                ws.settimeout(10);r=json.loads(ws.recv())
                if r.get("id")==8888:
                    d=r.get("result",{}).get("data","")
                    if d:
                        p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step16_form.png")
                        with open(p,"wb") as f:f.write(base64.b64decode(d))
                        print(f"\n📸 {p}")
                    break
            except:break
    except:pass

elif page.get('hash','') != '#/index/page':
    # 新页面但没表单，可能是中间确认页
    print("\n=== 6. 中间页面探查 ===")
    entries = ev("""(function(){
        var r=[];
        var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if((t.includes('设立')||t.includes('办理')||t.includes('登记')||t.includes('选择')||t.includes('下一步')||t.includes('确认')||t.includes('同意'))&&t.length<25&&all[i].offsetParent!==null&&all[i].children.length<3){
                r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,30)||'',text:t});
            }
        }
        return r;
    })()""")
    for e in (entries or []):
        print(f"  [{e.get('tag')}] {e.get('text')}")
    
    # 点击设立登记相关
    for e in (entries or []):
        if '设立' in e.get('text','') or '办理' in e.get('text','') or '同意' in e.get('text','') or '确认' in e.get('text',''):
            ev(f"""(function(){{
                var all=document.querySelectorAll('{e.get("tag","div")}');
                for(var i=0;i<all.length;i++){{
                    if(all[i].textContent?.trim()?.includes('{e.get("text","")}')&&all[i].offsetParent!==null){{
                        all[i].click();return;
                    }}
                }}
            }})()""")
            time.sleep(5)
            break

    # 再检查
    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after: hash={page2.get('hash')} forms={page2.get('formCount')} inputs={page2.get('inputCount')}")
    print(f"  text: {(page2.get('text','') or '')[:150]}")

ws.close()
print("\n✅ Step16 完成")
