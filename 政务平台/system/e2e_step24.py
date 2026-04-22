#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step24: 填写名称保留单号 → 提交 → 进入设立登记表单 → 填写 → 记录认证"""
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

# 2. 确认在名称选择页
print("=== 1. 当前页面 ===")
state = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
print(f"  hash: {(state or {}).get('hash','?')} forms: {(state or {}).get('formCount',0)}")

# 3. 填写名称保留单号
print("\n=== 2. 填写名称保留单号 ===")
fill = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var results=[];
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        var input=fi[i].querySelector('.el-input__inner,.el-textarea__inner');
        var lt=label?.textContent?.trim()||'';
        if(input&&input.offsetParent!==null&&!input.disabled){
            var val='';
            if(lt.includes('企业名称'))val='广西智信数据科技有限公司';
            else if(lt.includes('保留单号'))val='GX20260413001';
            else if(input.placeholder)val='test';
            if(val){
                var setter=Object.getOwnPropertyDescriptor(window[input.tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                setter.call(input,val);
                input.dispatchEvent(new Event('input',{bubbles:true}));
                input.dispatchEvent(new Event('change',{bubbles:true}));
                results.push({label:lt,val:val});
            }
        }
    }
    return results;
})()""")
print(f"  fill: {fill}")

# 4. 找下一步/提交按钮
print("\n=== 3. 找提交按钮 ===")
btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    var r=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t&&(t.includes('下一步')||t.includes('提交')||t.includes('确定')||t.includes('保存')||t.includes('开始')||t.includes('办理')||t.includes('关闭')||t.includes('选择'))&&btns[i].offsetParent!==null){
            r.push({i:i,text:t,type:btns[i].getAttribute('type')||'',cls:btns[i].className?.substring(0,30)||''});
        }
    }
    return r;
})()""")
print(f"  buttons: {btns}")

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
            window.__apiLogs.push({method:xhr.__method,url:xhr.__url,status:xhr.status,response:xhr.responseText?.substring(0,150)||''});
        });
        return origSend.apply(this,arguments);
    };
})()""")

# 6. 点击"选择已有名称"或下一步
print("\n=== 4. 点击操作按钮 ===")
# 先尝试"选择已有名称"（这可能是确认名称的按钮）
for b in (btns or []):
    if '选择' in b.get('text','') or '下一步' in b.get('text','') or '确定' in b.get('text',''):
        print(f"  点击: {b.get('text')}")
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

# 7. 检查API日志和页面
logs = ev("window.__apiLogs.slice(-10)")
if logs:
    print("\n=== 5. API日志 ===")
    for l in logs:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1]
        print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:80]}")

page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"\n=== 6. 页面状态 ===")
print(f"  hash: {(page or {}).get('hash','?')}")
print(f"  forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:250]}")

# 8. 如果有错误提示
errors = ev("""(function(){
    var msgs=document.querySelectorAll('.el-message,.el-message-box,.el-notification,.el-alert');
    var r=[];
    for(var i=0;i<msgs.length;i++){
        r.push({cls:msgs[i].className?.substring(0,30),text:msgs[i].textContent?.trim()?.substring(0,80)});
    }
    return r;
})()""")
if errors:
    print(f"  errors: {errors}")

# 9. 等待加载
fc = (page or {}).get('formCount',0)
ic = (page or {}).get('inputCount',0)
if fc == 0 and ic == 0:
    print("\n=== 7. 等待加载 ===")
    for attempt in range(8):
        time.sleep(3)
        check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length})")
        fc = (check or {}).get('formCount',0)
        ic = (check or {}).get('inputCount',0)
        h = (check or {}).get('hash','?')
        print(f"  {attempt+1}: hash={h} forms={fc} inputs={ic}")
        if fc > 0 or ic > 0:
            break

# 10. 如果有表单，详细探查
if fc > 0 or ic > 0:
    print("\n=== 8. 表单详细探查 ===")
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
        log("51.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("51a.字段详情", {"fields":form.get("fields",[])[:60]})
        for f in form.get("fields",[])[:40]:
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
        log("52.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
        print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
        for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
        if auth: log("53.认证检测",auth); print(f"  认证: {auth}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step24.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step24 完成")
