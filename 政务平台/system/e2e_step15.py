#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step15: 名称预核准页面探查 → 找表单/步骤 → 填写 → 记录"""
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

# 1. 当前页面完整分析
print("=== 1. 当前页面完整分析 ===")
state = ev("""(function(){
    var text=document.body.innerText||'';
    var html=document.body.innerHTML||'';
    return{
        hash:location.hash,
        url:location.href,
        text:text.substring(0,600),
        formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        buttonCount:document.querySelectorAll('button,.el-button').length,
        stepCount:document.querySelectorAll('.el-step').length,
        iframeCount:document.querySelectorAll('iframe').length,
        loadingCount:document.querySelectorAll('.el-loading,.is-loading').length,
        bodyChildCount:document.body.children.length,
        mainContent:document.querySelector('#app')?.children?.length||0
    };
})()""")
print(f"  hash: {state.get('hash')}")
print(f"  formCount: {state.get('formCount')}")
print(f"  inputCount: {state.get('inputCount')}")
print(f"  buttonCount: {state.get('buttonCount')}")
print(f"  stepCount: {state.get('stepCount')}")
print(f"  iframeCount: {state.get('iframeCount')}")
print(f"  loadingCount: {state.get('loadingCount')}")
print(f"  text: {(state.get('text','') or '')[:300]}")

# 2. 等待加载完成
if state.get('loadingCount',0) > 0 or state.get('formCount',0) == 0:
    print("\n=== 2. 等待加载 ===")
    for attempt in range(5):
        time.sleep(3)
        check = ev("({formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,loading:document.querySelectorAll('.el-loading,.is-loading').length,text:(document.body.innerText||'').substring(0,200)})")
        print(f"  attempt {attempt+1}: forms={check.get('formCount')} inputs={check.get('inputCount')} loading={check.get('loading')}")
        if check.get('formCount',0) > 0 or check.get('inputCount',0) > 0:
            break

# 3. 深入DOM分析 - 找隐藏的表单/组件
print("\n=== 3. DOM深入分析 ===")
dom = ev("""(function(){
    var r={allElements:0,visibleElements:0,hiddenElements:0,components:[]};
    var all=document.querySelectorAll('*');
    r.allElements=all.length;
    for(var i=0;i<all.length;i++){
        if(all[i].offsetParent!==null)r.visibleElements++;
        else r.hiddenElements++;
    }
    // 找Vue组件
    var vms=[];
    var app=document.getElementById('app');
    if(app&&app.__vue__){
        var vm=app.__vue__;
        // 遍历当前路由的组件
        var route=vm.$route;
        var matched=route?.matched||[];
        for(var i=0;i<matched.length;i++){
            vms.push({path:matched[i].path,name:matched[i].name||'',compName:matched[i].components?.default?.name||''});
        }
    }
    r.routeComponents=vms;
    // 找所有input（包括hidden）
    var inputs=document.querySelectorAll('input,textarea,select');
    r.inputDetails=[];
    for(var i=0;i<inputs.length;i++){
        var inp=inputs[i];
        r.inputDetails.push({i:i,type:inp.type||inp.tagName,visible:inp.offsetParent!==null,name:inp.name||'',id:inp.id||'',placeholder:inp.placeholder||'',value:(inp.value||'').substring(0,20)});
    }
    return r;
})()""")
print(f"  total/visible/hidden: {dom.get('allElements')}/{dom.get('visibleElements')}/{dom.get('hiddenElements')}")
print(f"  routeComponents: {dom.get('routeComponents')}")
print(f"  inputs: {dom.get('inputDetails')}")

# 4. 检查是否有iframe包含表单
if state.get('iframeCount',0) > 0:
    print("\n=== 4. Iframe检查 ===")
    iframes = ev("""(function(){
        var ifs=document.querySelectorAll('iframe');
        var r=[];
        for(var i=0;i<ifs.length;i++){
            r.push({i:i,src:ifs[i].src||ifs[i].getAttribute('src')||'',visible:ifs[i].offsetParent!==null,width:ifs[i].offsetWidth,height:ifs[i].offsetHeight});
        }
        return r;
    })()""")
    print(f"  iframes: {iframes}")

# 5. 检查Vue路由组件的完整DOM
print("\n=== 5. Vue路由组件DOM ===")
route_dom = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    if(!vm)return{error:'no_vue'};
    var route=vm.$route;
    // 找router-view的内容
    var rv=document.querySelector('.router-view,[class*="router-view"]');
    if(!rv){
        // 尝试找main-content
        rv=document.querySelector('.main-content,[class*="main-content"],.content,[class*="content"]');
    }
    if(rv){
        return{
            found:'router-view',
            childCount:rv.children.length,
            html:rv.innerHTML?.substring(0,500)||'',
            text:rv.textContent?.substring(0,300)||''
        };
    }
    // 找#app下所有直接子元素
    var children=[];
    for(var i=0;i<app.children.length;i++){
        children.push({tag:app.children[i].tagName,cls:app.children[i].className?.substring(0,30)||'',text:app.children[i].textContent?.substring(0,50)||''});
    }
    return{found:'app_children',children:children};
})()""")
print(f"  route_dom: {json.dumps(route_dom, ensure_ascii=False)[:500]}")

# 6. 如果表单存在但隐藏，尝试使其可见
if state.get('formCount',0) == 0 and dom.get('inputCount',0) == 0:
    print("\n=== 6. 页面可能需要交互才能显示表单 ===")
    # 找所有可点击元素
    clickable = ev("""(function(){
        var r=[];
        var all=document.querySelectorAll('div,span,a,button,p,h3,h4');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.length>0&&t.length<30&&all[i].offsetParent!==null){
                var cursor=getComputedStyle(all[i]).cursor;
                if(cursor==='pointer'||all[i].tagName==='BUTTON'||all[i].onclick){
                    r.push({tag:all[i].tagName,cls:all[i].className?.substring(0,30)||'',text:t,cursor:cursor});
                }
            }
        }
        return r.slice(0,20);
    })()""")
    print(f"  clickable: {clickable}")
    
    # 点击"标准版"（可能需要选择版本）
    for c in (clickable or []):
        if '标准版' in c.get('text',''):
            print(f"\n  点击标准版: {c}")
            ev("""(function(){
                var all=document.querySelectorAll('div,span');
                for(var i=0;i<all.length;i++){
                    if(all[i].textContent?.trim()==='标准版'&&all[i].offsetParent!==null){
                        all[i].click();return;
                    }
                }
            })()""")
            time.sleep(5)
            break

    # 检查结果
    after = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after: {after}")

    # 如果还是没有表单，可能需要更长时间加载
    if after.get('formCount',0) == 0 and after.get('inputCount',0) == 0:
        print("\n=== 7. 长等待 ===")
        time.sleep(10)
        final_check = ev("({formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,300)})")
        print(f"  final: forms={final_check.get('formCount')} inputs={final_check.get('inputCount')}")
        print(f"  text: {(final_check.get('text','') or '')[:200]}")
        
        # 检查console错误
        errors = ev("""(function(){
            // 检查是否有错误提示
            var errs=document.querySelectorAll('.el-message,.el-notification,.el-alert,[class*="error"]');
            var r=[];
            for(var i=0;i<errs.length;i++){
                r.push({cls:errs[i].className?.substring(0,30),text:errs[i].textContent?.trim()?.substring(0,50)});
            }
            return r;
        })()""")
        print(f"  errors: {errors}")

# 8. 如果有表单，探查并填写
form_count = ev("document.querySelectorAll('.el-form-item').length")
if form_count and form_count > 0:
    print("\n=== 8. 表单探查 ===")
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
    log("32.名称预核准表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
    log("32a.字段详情", {"fields":form.get("fields",[])[:60]})
    for f in (form.get("fields",[])[:30]):
        print(f"  [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')}")

    # 填写
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
    log("33.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
        issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
    print(f"\n  填写: ok={len(ok)} fail={len(fail)}")

    # 认证检测
    auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书')}})()""")
    log("34.认证检测",auth)
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
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step15.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step15 完成")
