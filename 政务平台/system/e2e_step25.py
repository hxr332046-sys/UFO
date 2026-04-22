#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step25: 选择已有名称模式 → 填写 → 找真正提交按钮 → 进入设立登记"""
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

# 2. 导航到名称选择页
print("=== 1. 导航 ===")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/select-prise?entType=1100');
})()""")
time.sleep(5)

# 3. 点击"其他来源名称" → 确认 → 进入选择已有名称模式
print("\n=== 2. 进入选择已有名称模式 ===")
# 点击其他来源名称按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        if(btns[i].textContent?.trim()?.includes('其他来源名称')&&btns[i].offsetParent!==null){
            btns[i].click();return;
        }
    }
})()""")
time.sleep(2)
# 点击确定
ev("""(function(){
    var dgs=document.querySelectorAll('.el-dialog__wrapper,.el-dialog');
    for(var i=0;i<dgs.length;i++){
        var visible=dgs[i].className?.includes('open')||dgs[i].style?.display!=='none';
        if(visible){
            var btns=dgs[i].querySelectorAll('button,.el-button');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('确 定')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(3)

# 4. 确认在"选择已有名称"模式
page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
print(f"  forms: {(page or {}).get('formCount',0)} text: {(page or {}).get('text','')[:100]}")

# 5. 填写企业名称和保留单号
print("\n=== 3. 填写 ===")
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
            if(val){
                var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
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

# 6. 找所有按钮（包括隐藏的）
print("\n=== 4. 所有按钮 ===")
all_btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,a,[class*="btn"],[class*="button"]');
    var r=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        var vis=btns[i].offsetParent!==null;
        var rect=btns[i].getBoundingClientRect();
        r.push({i:i,text:t.substring(0,15),visible:vis,inViewport:rect.top>=0&&rect.top<window.innerHeight,type:btns[i].tagName,cls:btns[i].className?.substring(0,25)||''});
    }
    return r.filter(function(b){return b.text&&b.text.length>0}).slice(0,30);
})()""")
for b in (all_btns or []):
    marker = "✅" if b.get('inViewport') else "📍" if b.get('visible') else "❌"
    print(f"  {marker} [{b.get('type')}] {b.get('text')} ({b.get('cls','')[:15]})")

# 7. 找select-prise组件的方法
print("\n=== 5. select-prise组件方法 ===")
comp = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    var methods=[];
    for(var k in inst.$options?.methods||{}){
        var fn=inst.$options.methods[k].toString();
        methods.push({name:k,preview:fn.substring(0,120)});
    }
    var data={};
    for(var k in inst.$data||{}){
        var v=inst.$data[k];
        data[k]=typeof v==='object'?JSON.stringify(v)?.substring(0,60):String(v).substring(0,20);
    }
    return{methods:methods,data:data};
})()""")
for m in (comp.get('methods',[]) if comp else []):
    print(f"  {m.get('name')}: {m.get('preview','')[:80]}")
print(f"  data: {json.dumps((comp or {}).get('data',{}), ensure_ascii=False)[:200]}")

# 8. 安装XHR拦截器
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

# 9. 尝试调用组件的提交方法
print("\n=== 6. 调用提交方法 ===")
submit_result = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    
    // 尝试各种可能的提交方法
    var tryMethods=['submit','handleSubmit','onSubmit','nextStep','toNext','confirm','handleConfirm','saveName','selectName','addName','handleSelect','toNextStep','goNext'];
    var results=[];
    for(var i=0;i<tryMethods.length;i++){
        if(typeof inst[tryMethods[i]]==='function'){
            try{
                inst[tryMethods[i]]();
                results.push(tryMethods[i]+':called');
            }catch(e){
                results.push(tryMethods[i]+':'+e.message.substring(0,30));
            }
        }
    }
    return results;
})()""")
print(f"  submit methods: {submit_result}")
time.sleep(5)

# 10. 检查API日志和页面变化
logs = ev("window.__apiLogs.slice(-10)")
if logs:
    print("\n=== 7. API日志 ===")
    for l in logs:
        url_short = (l.get('url','') or '').split('?')[0].split('/')[-1]
        print(f"  {l.get('method','')} {url_short} → {l.get('status','')} {(l.get('response','') or '')[:80]}")

page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
print(f"\n=== 8. 页面状态 ===")
print(f"  hash: {(page2 or {}).get('hash','?')} forms: {(page2 or {}).get('formCount',0)} inputs: {(page2 or {}).get('inputCount',0)}")
print(f"  text: {(page2 or {}).get('text','')[:150]}")

# 11. 如果方法调用没效果，尝试通过Vue $refs找表单提交
if (page2 or {}).get('formCount',0) <= 2:
    print("\n=== 9. 通过$refs提交表单 ===")
    ref_submit = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var inst=null;
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='select-prise'){inst=matched[i].instances?.default;break}
        }
        if(!inst)return{error:'no_instance'};
        
        var refs=Object.keys(inst.$refs||{});
        var results={refs:refs};
        
        // 找el-form并validate+submit
        for(var k in inst.$refs){
            var ref=inst.$refs[k];
            if(ref&&ref.validate){
                results.hasForm=true;
                results.formRef=k;
                // 尝试validate
                ref.validate(function(valid){
                    results.valid=valid;
                });
            }
        }
        
        // 也尝试直接调用Vue组件的click handler
        // 找所有有@click的元素
        var allBtns=inst.$el?.querySelectorAll('button,.el-button')||[];
        for(var i=0;i<allBtns.length;i++){
            var t=allBtns[i].textContent?.trim()||'';
            if(t.includes('下一步')||t.includes('提交')||t.includes('确定')||t.includes('保存')||t.includes('办理')){
                allBtns[i].click();
                results.clickedBtn=t;
                break;
            }
        }
        
        return results;
    })()""")
    print(f"  ref_submit: {ref_submit}")
    time.sleep(5)
    
    page3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length})")
    print(f"  after: hash={(page3 or {}).get('hash')} forms={(page3 or {}).get('formCount',0)} inputs={(page3 or {}).get('inputCount',0)}")

# 12. 最终检查 - 如果到了设立登记表单页面
final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
log("54.名称选择后状态", {"hash":(final or {}).get("hash"),"formCount":(final or {}).get("formCount",0),"inputCount":(final or {}).get("inputCount",0),"text":(final.get("text","") or "")[:100]})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step25.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step25 完成")
