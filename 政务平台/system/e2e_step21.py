#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step21: 拦截initData API → 分析响应 → 触发表单渲染"""
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

# 2. 安装XHR拦截器
print("=== 1. 安装XHR拦截器 ===")
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
        var origLoad=this.onload;
        xhr.addEventListener('loadend',function(){
            window.__apiLogs.push({
                method:xhr.__method,
                url:xhr.__url,
                status:xhr.status,
                response:xhr.responseText?.substring(0,200)||'',
                time:new Date().toISOString()
            });
        });
        return origSend.apply(this,arguments);
    };
    return'ok';
})()""")

# 3. 导航到without-name
print("\n=== 2. 导航 ===")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/without-name?entType=1100');
})()""")
time.sleep(5)

# 4. 获取API日志
print("\n=== 3. API日志（导航后）===")
logs1 = ev("window.__apiLogs.slice(-20)")
if logs1:
    for l in logs1:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1] if l.get('url') else '?'
        print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:80]}")

# 5. 调用initData并捕获API
print("\n=== 4. 调用initData ===")
ev("""(function(){
    window.__apiLogs=[];
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(inst&&inst.initData)inst.initData();
})()""")
time.sleep(5)

logs2 = ev("window.__apiLogs")
print(f"\n=== 5. initData API日志 ===")
if logs2:
    for l in logs2:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1] if l.get('url') else '?'
        print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:120]}")
else:
    print("  无API调用")

# 6. 检查initData后的data
print("\n=== 6. initData后的组件data ===")
after = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    return{
        priseName:inst.$data.priseName,
        priseNo:inst.$data.priseNo,
        busiDataList:JSON.stringify(inst.$data.busiDataList)?.substring(0,200)||'[]',
        formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        elHtml:inst.$el?.innerHTML?.substring(0,500)||''
    };
})()""")
print(f"  priseName: {(after or {}).get('priseName','')}")
print(f"  priseNo: {(after or {}).get('priseNo','')}")
print(f"  busiDataList: {(after or {}).get('busiDataList','')[:100]}")
print(f"  forms: {(after or {}).get('formCount',0)} inputs: {(after or {}).get('inputCount',0)}")
print(f"  elHtml: {(after or {}).get('elHtml','')[:200]}")

# 7. 尝试toSelectName和toNotName
print("\n=== 7. 尝试toSelectName ===")
ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(inst&&inst.toSelectName){
        window.__apiLogs=[];
        inst.toSelectName();
        return'called';
    }
    return'no_method';
})()""")
time.sleep(5)

logs3 = ev("window.__apiLogs")
if logs3:
    print("  toSelectName API:")
    for l in logs3:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1] if l.get('url') else '?'
        print(f"    {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:100]}")

page3 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,text:(document.body.innerText||'').substring(0,200)})")
print(f"  after toSelectName: hash={(page3 or {}).get('hash')} forms={(page3 or {}).get('formCount',0)} inputs={(page3 or {}).get('inputCount',0)}")
print(f"  text: {(page3 or {}).get('text','')[:100]}")

# 8. 如果toSelectName没效果，试toNotName
if (page3 or {}).get('formCount',0) == 0:
    print("\n=== 8. 尝试toNotName ===")
    ev("""(function(){
        window.__apiLogs=[];
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var inst=null;
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
        }
        if(inst&&inst.toNotName)inst.toNotName();
    })()""")
    time.sleep(5)
    
    page4 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after toNotName: hash={(page4 or {}).get('hash')} forms={(page4 or {}).get('formCount',0)} inputs={(page4 or {}).get('inputCount',0)}")
    print(f"  text: {(page4 or {}).get('text','')[:100]}")
    
    logs4 = ev("window.__apiLogs")
    if logs4:
        for l in logs4:
            url_short = (l.get('url','') or '').split('?')[0].split('/')[-1] if l.get('url') else '?'
            print(f"    {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:100]}")

# 9. 如果还是空，直接看initData方法的源码
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 9. initData源码 ===")
    src = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var inst=null;
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
        }
        if(!inst)return'no_instance';
        var methods={};
        for(var k in inst.$options?.methods||{}){
            methods[k]=inst.$options.methods[k].toString().substring(0,300);
        }
        // 也获取created/mounted钩子
        var hooks={};
        if(inst.$options?.created)hooks.created=inst.$options.created.toString().substring(0,300);
        if(inst.$options?.mounted)hooks.mounted=inst.$options.mounted.toString().substring(0,300);
        return{methods:methods,hooks:hooks};
    })()""")
    print(f"  source: {json.dumps(src or {}, ensure_ascii=False)[:800]}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step21.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step21 完成")
