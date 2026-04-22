#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step22: 名称选择页→填写企业名称→下一步→设立登记表单→填写→记录认证"""
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
state = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"  hash: {(state or {}).get('hash','?')}")
print(f"  forms: {(state or {}).get('formCount',0)} inputs: {(state or {}).get('inputCount',0)}")
print(f"  text: {(state or {}).get('text','')[:250]}")

# 3. 分析select-prise组件
print("\n=== 2. select-prise组件分析 ===")
comp = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance',routeName:route?.name};
    
    var data={};
    for(var k in inst.$data||{}){
        var v=inst.$data[k];
        data[k]=typeof v==='object'?JSON.stringify(v)?.substring(0,80):String(v).substring(0,30);
    }
    var methods=[];
    for(var k in inst.$options?.methods||{})methods.push(k);
    
    return{data:data,methods:methods,elHtml:inst.$el?.innerHTML?.substring(0,600)||''};
})()""")
print(f"  data: {json.dumps((comp or {}).get('data',{}), ensure_ascii=False)[:300]}")
print(f"  methods: {(comp or {}).get('methods',[])}")
print(f"  elHtml: {(comp or {}).get('elHtml','')[:300]}")

# 4. 找所有input和按钮
print("\n=== 3. 所有input和按钮 ===")
inputs = ev("""(function(){
    var ins=document.querySelectorAll('input,textarea,select');
    var r=[];
    for(var i=0;i<ins.length;i++){
        r.push({i:i,type:ins[i].type||ins[i].tagName,name:ins[i].name||'',id:ins[i].id||'',
        ph:ins[i].placeholder||'',val:(ins[i].value||'').substring(0,20),
        visible:ins[i].offsetParent!==null,disabled:ins[i].disabled});
    }
    var btns=document.querySelectorAll('button,.el-button');
    var bl=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t&&t.length<20)bl.push({i:i,text:t,visible:btns[i].offsetParent!==null});
    }
    return{inputs:r,buttons:bl};
})()""")
print(f"  inputs: {(inputs or {}).get('inputs',[])}")
print(f"  buttons: {(inputs or {}).get('buttons',[])}")

# 5. 点击"其他来源名称"按钮录入企业名称
print("\n=== 4. 点击其他来源名称 ===")
click_result = ev("""(function(){
    var all=document.querySelectorAll('div,span,a,button,p');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('其他来源名称')&&all[i].offsetParent!==null&&all[i].children.length<3){
            all[i].click();
            return{clicked:t,tag:all[i].tagName};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click: {click_result}")
time.sleep(3)

# 6. 检查是否出现输入框/弹窗
page2 = ev("""(function(){
    return{formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    dialogVisible:document.querySelectorAll('.el-dialog__wrapper').length>0,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
print(f"  forms: {(page2 or {}).get('formCount',0)} inputs: {(page2 or {}).get('inputCount',0)} dialog: {(page2 or {}).get('dialogVisible',False)}")
print(f"  text: {(page2 or {}).get('text','')[:200]}")

# 7. 填写企业名称
print("\n=== 5. 填写企业名称 ===")
fill = ev("""(function(){
    var inputs=document.querySelectorAll('input.el-input__inner,textarea.el-textarea__inner');
    var filled=[];
    for(var i=0;i<inputs.length;i++){
        if(inputs[i].offsetParent!==null&&!inputs[i].disabled){
            var ph=inputs[i].placeholder||'';
            var label='';
            var fi=inputs[i].closest('.el-form-item');
            if(fi){
                var lb=fi.querySelector('.el-form-item__label');
                label=lb?.textContent?.trim()||'';
            }
            // 填写名称相关字段
            var val='';
            if(ph.includes('名称')||label.includes('名称')||label.includes('企业名称')||label.includes('公司名称')){
                val='广西智信数据科技有限公司';
            }else if(ph.includes('字号')||label.includes('字号')){
                val='智信数据';
            }else if(ph.includes('行业')||label.includes('行业')){
                val='科技';
            }else if(ph.includes('组织形式')||label.includes('组织形式')){
                val='有限公司';
            }else if(ph!=''&&!ph.includes('请选择')){
                val='test';
            }
            if(val){
                var setter=Object.getOwnPropertyDescriptor(window[inputs[i].tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                setter.call(inputs[i],val);
                inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
                inputs[i].dispatchEvent(new Event('change',{bubbles:true}));
                filled.push({ph:ph,label:label,val:val});
            }
        }
    }
    return{filled:filled,totalInputs:inputs.length};
})()""")
print(f"  fill: {fill}")

# 8. 找下一步/确定/提交按钮
print("\n=== 6. 找下一步按钮 ===")
time.sleep(2)
btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    var r=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t&&(t.includes('下一步')||t.includes('确定')||t.includes('提交')||t.includes('保存')||t.includes('确认')||t.includes('录入'))&&btns[i].offsetParent!==null){
            r.push({i:i,text:t,cls:btns[i].className?.substring(0,30)||'',type:btns[i].getAttribute('type')||''});
        }
    }
    return r;
})()""")
print(f"  buttons: {btns}")

# 9. 点击下一步/确定
if btns:
    for b in btns:
        if '下一步' in b.get('text','') or '确定' in b.get('text','') or '录入' in b.get('text','') or '确认' in b.get('text',''):
            print(f"\n=== 7. 点击 {b.get('text')} ===")
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

# 10. 检查结果
page3 = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"  hash: {(page3 or {}).get('hash','?')}")
print(f"  forms: {(page3 or {}).get('formCount',0)} inputs: {(page3 or {}).get('inputCount',0)}")
print(f"  text: {(page3 or {}).get('text','')[:250]}")

# 11. 如果有表单，详细探查和填写
fc = (page3 or {}).get('formCount',0)
ic = (page3 or {}).get('inputCount',0)
if fc > 0 or ic > 0:
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
        return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,20)};
    })()""")
    if form:
        log("45.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("45a.字段详情", {"fields":form.get("fields",[])[:60]})
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
        log("46.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
        print(f"\n  填写: ok={len(ok)} fail={len(fail)}")

        # 认证检测
        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
        if auth: log("47.认证检测",auth); print(f"  认证: {auth}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step22.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step22 完成")
