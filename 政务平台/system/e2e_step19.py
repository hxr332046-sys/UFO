#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step19: 正确提取token → 恢复Vuex → 导航 → 表单"""
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

# 1. 分析localStorage中所有token相关值
print("=== 1. localStorage token分析 ===")
tokens = ev("""(function(){
    var r={};
    var keys=['top-token','Top-token','Authorization','_topnet_accessToken','_topnet_userInfo','token','accessToken'];
    for(var i=0;i<keys.length;i++){
        var v=localStorage.getItem(keys[i]);
        r[keys[i]]=v?v.substring(0,50):'NULL';
    }
    // 解析 _topnet_accessToken
    var at=localStorage.getItem('_topnet_accessToken')||'';
    if(at.startsWith('_topnet_')){
        try{
            var parsed=JSON.parse(at.substring(8));
            r._parsed_token=parsed._value||'no_value';
            r._parsed_expires=parsed._expires||'no_expires';
        }catch(e){r._parse_error=e.message}
    }
    // 解析 _topnet_userInfo
    var ui=localStorage.getItem('_topnet_userInfo')||'';
    if(ui.startsWith('_topnet_')){
        try{
            var parsed2=JSON.parse(ui.substring(8));
            r._parsed_userId=parsed2._value||'no_value';
        }catch(e){}
    }
    return r;
})()""")
for k,v in (tokens or {}).items():
    print(f"  {k}: {v}")

# 2. 用解析出的真实token恢复Vuex
print("\n=== 2. 用真实token恢复Vuex ===")
restore = ev("""(function(){
    // 从 _topnet_accessToken 解析真实token
    var at=localStorage.getItem('_topnet_accessToken')||'';
    var realToken='';
    if(at.startsWith('_topnet_')){
        try{
            var parsed=JSON.parse(at.substring(8));
            realToken=parsed._value||'';
        }catch(e){}
    }
    if(!realToken)return{error:'no_real_token'};
    
    // 设置到localStorage
    localStorage.setItem('top-token',realToken);
    localStorage.setItem('Authorization',realToken);
    
    // 设置到Vuex
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(!store)return{error:'no_store'};
    store.commit('login/SET_TOKEN',realToken);
    
    // 验证
    var vuexToken=store.state.login?.token||'';
    var lsToken=localStorage.getItem('top-token')||'';
    return{
        realToken:realToken.substring(0,10)+'...',
        vuexToken:vuexToken.substring(0,10)+'...',
        lsToken:lsToken.substring(0,10)+'...',
        match:vuexToken===realToken && lsToken===realToken
    };
})()""")
print(f"  restore: {restore}")

# 3. 导航到without-name页面
print("\n=== 3. 导航到名称预核准页面 ===")
nav = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(!vm?.$router)return'no_router';
    try{vm.$router.push('/index/without-name?entType=1100');return'ok'}catch(e){return e.message}
})()""")
print(f"  nav: {nav}")
time.sleep(8)

# 4. 检查页面
page = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        text:(document.body.innerText||'').substring(0,400)
    };
})()""")
print(f"  hash: {(page or {}).get('hash','?')}")
print(f"  forms: {(page or {}).get('formCount',0)}")
print(f"  inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:200]}")

# 5. 等待加载
fc = (page or {}).get('formCount',0)
ic = (page or {}).get('inputCount',0)
if fc == 0 and ic == 0:
    print("\n=== 5. 等待加载 ===")
    for attempt in range(10):
        time.sleep(3)
        check = ev("({formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,hash:location.hash})")
        fc = (check or {}).get('formCount',0)
        ic = (check or {}).get('inputCount',0)
        print(f"  {attempt+1}: forms={fc} inputs={ic}")
        if fc > 0 or ic > 0:
            break

# 6. 如果有表单，探查并填写
if fc > 0 or ic > 0:
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
        log("42.名称预核准表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("42a.字段详情", {"fields":form.get("fields",[])[:60]})
        for f in form.get("fields",[])[:40]:
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
        log("43.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
        print(f"\n  填写: ok={len(ok)} fail={len(fail)}")

        # 认证检测
        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
        if auth: log("44.认证检测",auth); print(f"  认证: {auth}")

else:
    # 没有表单 - 深入分析
    print("\n=== 6. 无表单，深入分析 ===")
    
    # 检查Vue组件是否加载
    comp = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var comps=[];
        for(var i=0;i<matched.length;i++){
            var m=matched[i];
            var inst=m.instances?.default;
            comps.push({path:m.path,name:m.name||'',hasInstance:!!inst,instData:inst?Object.keys(inst.$data||{}).slice(0,10):[]});
        }
        // 找router-view
        var rv=document.querySelector('.router-view,[class*="main-content"]');
        var rvHtml=rv?.innerHTML?.substring(0,300)||'no_router_view';
        return{comps:comps,routerViewHtml:rvHtml};
    })()""")
    print(f"  comps: {json.dumps(comp or {}, ensure_ascii=False)[:400]}")
    
    # 检查网络请求
    net = ev("""(function(){
        var entries=performance.getEntriesByType('resource');
        var recent=entries.filter(function(e){return e.startTime>performance.now()-60000});
        var apiCalls=recent.filter(function(e){return e.name.includes('icpsp-api')||e.name.includes('api')});
        return apiCalls.map(function(e){return{name:e.name?.substring(e.name.lastIndexOf('/')+1),status:e.responseStatus,duration:Math.round(e.duration)}).slice(0,15);
    })()""")
    print(f"  api calls: {net}")
    
    # 拦截XHR看API调用
    print("\n=== 7. 拦截XHR ===")
    ev("""(function(){
        window.__apiLogs=[];
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(method,url){
            this.__url=url;this.__method=method;
            return origOpen.apply(this,arguments);
        };
        var origSend=XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send=function(){
            var xhr=this;
            xhr.addEventListener('load',function(){
                window.__apiLogs.push({method:xhr.__method,url:xhr.__url,status:xhr.status,body:xhr.responseText?.substring(0,80)});
            });
            xhr.addEventListener('error',function(){
                window.__apiLogs.push({method:xhr.__method,url:xhr.__url,status:'error'});
            });
            return origSend.apply(this,arguments);
        };
        return'interceptor_installed';
    })()""")
    
    # 重新导航触发API调用
    ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(vm?.$router){
            vm.$router.push('/index/enterprise/enterprise-zone');
        }
    })()""")
    time.sleep(3)
    ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(vm?.$router)vm.$router.push('/index/without-name?entType=1100');
    })()""")
    time.sleep(8)
    
    api_logs = ev("window.__apiLogs||[]")
    print(f"  API logs: {json.dumps(api_logs or [], ensure_ascii=False)[:500]}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step19.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step19 完成")
