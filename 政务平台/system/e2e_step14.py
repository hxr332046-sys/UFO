#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step14: 企业开办专区 → 找设立登记入口 → 进入表单 → 填写 → 记录认证"""
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

# 1. 确认在企业开办专区
print("=== 1. 当前页面 ===")
state = ev("""(function(){
    return{
        hash:location.hash,
        text:(document.body.innerText||'').substring(0,400),
        formCount:document.querySelectorAll('.el-form-item').length,
        buttonCount:document.querySelectorAll('button,.el-button').length
    };
})()""")
print(f"  hash: {state.get('hash')}")
print(f"  text: {(state.get('text','') or '')[:300]}")

# 2. 找所有可点击元素
print("\n=== 2. 找设立登记/办理入口 ===")
entries = ev("""(function(){
    var r=[];
    var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('设立')||t.includes('办理')||t.includes('登记')||t.includes('开办')||t.includes('下一步')||t.includes('开始'))&&t.length<30&&all[i].offsetParent!==null&&all[i].children.length<4){
            r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,40)||'',text:t,hasVue:!!all[i].__vue__});
        }
    }
    return r;
})()""")
for e in (entries or []):
    print(f"  [{e.get('tag')}] {e.get('text')} (vue={e.get('hasVue')})")

# 3. 点击"办理营业执照"或"设立登记"按钮
print("\n=== 3. 点击办理入口 ===")
click = ev("""(function(){
    var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li');
    // 优先找"办理营业执照"按钮
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('办理营业执照')&&all[i].offsetParent!==null&&all[i].children.length<4){
            all[i].click();
            return{clicked:t,tag:all[i].tagName};
        }
    }
    // 其次"设立登记"
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&all[i].offsetParent!==null&&all[i].children.length<4){
            all[i].click();
            return{clicked:t,tag:all[i].tagName};
        }
    }
    // 最后"开始"或"办理"
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t==='开始办理'||t==='立即办理'||t==='开始')&&all[i].offsetParent!==null){
            all[i].click();
            return{clicked:t,tag:all[i].tagName};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click: {click}")
time.sleep(5)

page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"  page: hash={page.get('hash')} forms={page.get('formCount')}")
print(f"  text: {(page.get('text','') or '')[:300]}")

# 4. 如果到了新页面但没表单，继续找入口
if page.get('formCount',0) == 0 and page.get('hash') != '#/index/enterprise/enterprise-zone':
    print("\n=== 4. 新页面找设立登记 ===")
    entries2 = ev("""(function(){
        var r=[];
        var all=document.querySelectorAll('div,span,a,h3,h4,p,button,li');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if((t.includes('设立')||t.includes('办理')||t.includes('登记')||t.includes('开办')||t.includes('选择')||t.includes('下一步'))&&t.length<25&&all[i].offsetParent!==null&&all[i].children.length<3){
                r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,30)||'',text:t});
            }
        }
        return r;
    })()""")
    for e in (entries2 or []):
        print(f"  [{e.get('tag')}] {e.get('text')}")
    
    for e in (entries2 or []):
        if '设立' in e.get('text','') or '办理' in e.get('text',''):
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

# 5. 如果还在专区页面，找卡片/按钮
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 5. 专区页面找卡片 ===")
    cards = ev("""(function(){
        var r=[];
        var all=document.querySelectorAll('[class*="card"],[class*="service"],[class*="item"],[class*="btn"]');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.length>0&&t.length<50&&all[i].offsetParent!==null){
                r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,40)||'',text:t.substring(0,30)});
            }
        }
        return r.slice(0,20);
    })()""")
    for c in (cards or []):
        print(f"  [{c.get('tag')}.{c.get('cls','')[:20]}] {c.get('text')}")
    
    # 点击"办理营业执照"按钮
    for c in (cards or []):
        if '办理' in c.get('text','') or '设立' in c.get('text',''):
            print(f"\n  点击: {c.get('text')}")
            ev(f"""(function(){{
                var all=document.querySelectorAll('[class*="card"],[class*="service"],[class*="item"],[class*="btn"]');
                for(var i=0;i<all.length;i++){{
                    var t=all[i].textContent?.trim()||'';
                    if(t.includes('{c.get("text","")}')&&all[i].offsetParent!==null){{
                        all[i].click();return;
                    }}
                }}
            }})()""")
            time.sleep(5)
            break

# 6. 检查结果
page_final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    text:(document.body.innerText||'').substring(0,500)};
})()""")
print(f"\n=== 6. 当前状态 ===")
print(f"  hash: {page_final.get('hash')}")
print(f"  forms: {page_final.get('formCount')}")
print(f"  text: {(page_final.get('text','') or '')[:300]}")

# 7. 如果有表单，探查并填写
if page_final.get('formCount',0) > 0:
    print("\n=== 7. 表单探查 ===")
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
        return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,15)};
    })()""")
    log("29.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
    log("29a.字段详情", {"fields":form.get("fields",[])[:60]})
    
    for f in (form.get("fields",[])[:30]):
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
    log("30.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
        issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
    print(f"\n  填写结果: ok={len(ok)} fail={len(fail)}")
    for r in fail:
        print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

    # 认证检测
    auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证')}})()""")
    log("31.认证检测",auth)
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
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step14.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step14 完成")
