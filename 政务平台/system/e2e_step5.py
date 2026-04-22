#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step5: 点击首页设立登记卡片 → 探查表单 → 逐字段填写 → 记录"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=15)

_mid = 0
def ev(js, mid=None):
    global _mid
    if mid is None: mid = _mid + 1; _mid = mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")

def screenshot(name):
    ws.send(json.dumps({"id":9000+hash(name)%1000,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 9000+hash(name)%1000:
            d = r.get("result",{}).get("data","")
            if d:
                p = os.path.join(os.path.dirname(__file__),"..","data",f"e2e_{name}.png")
                with open(p,"wb") as f: f.write(base64.b64decode(d))
                print(f"  📸 {p}")
            break

# 1. 确认在首页
cur = ev("location.hash")
print(f"当前hash: {cur}")

# 2. 搜索首页所有可点击元素
print("\n=== 2. 搜索设立登记入口 ===")
entries = ev("""(function(){
    var r={cards:[],links:[],divs:[]};
    // 搜索所有div/span/a
    var all=document.querySelectorAll('div,span,a,p,h1,h2,h3,h4,h5,h6,li');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<30){
            r.cards.push({tag:all[i].tagName,cls:all[i].className?.substring(0,40)||'',text:t,clickable:all[i].onclick||all[i].parentElement?.onclick||null});
        }
    }
    // 搜索a标签
    var links=document.querySelectorAll('a');
    for(var i=0;i<links.length;i++){
        var t=links[i].textContent?.trim()||'';
        var href=links[i].getAttribute('href')||'';
        if(t.includes('设立')||t.includes('登记')||href.includes('establish')){
            r.links.push({text:t.substring(0,30),href:href.substring(0,60)});
        }
    }
    // 搜索带router-link的
    var rls=document.querySelectorAll('[data-v-],[class*="card"],[class*="service"],[class*="item"]');
    for(var i=0;i<rls.length;i++){
        var t=rls[i].textContent?.trim()||'';
        if((t.includes('设立')||t.includes('登记'))&&t.length<50){
            r.divs.push({tag:rls[i].tagName,cls:rls[i].className?.substring(0,40)||'',text:t.substring(0,40)});
        }
    }
    return r;
})()""")
print(f"  cards: {entries.get('cards',[])}")
print(f"  links: {entries.get('links',[])}")
print(f"  divs: {entries.get('divs',[])}")

# 3. 点击设立登记
print("\n=== 3. 点击设立登记 ===")
click_result = ev("""(function(){
    var all=document.querySelectorAll('div,span,a,p,li,h3,h4');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='设立登记'||t.includes('设立登记')){
            // 找到最近的可点击父元素
            var el=all[i];
            // 先尝试点击自己
            el.click();
            return{clicked:t,tag:el.tagName,cls:el.className?.substring(0,40)||''};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  result: {click_result}")
time.sleep(5)

# 检查导航结果
after_click = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        text:(document.body.innerText||'').substring(0,300)
    };
})()""")
print(f"  hash: {after_click.get('hash')}")
print(f"  formCount: {after_click.get('formCount')}")
print(f"  text: {(after_click.get('text','') or '')[:200]}")

screenshot("after_click_establish")

# 如果还在首页，尝试Vue Router导航
if after_click.get('formCount',0) == 0 and after_click.get('hash') == '#/index/page':
    print("\n=== 3b. 尝试Vue Router ===")
    nav = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app&&app.__vue__;
        if(!vm||!vm.$router)return{error:'no_router'};
        try{
            vm.$router.push('/index/enterprise/establish');
            return{pushed:true};
        }catch(e){return{error:e.message}}
    })()""")
    print(f"  router push: {nav}")
    time.sleep(5)
    after_router = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  after router: {after_router}")
    screenshot("after_router")

# 如果还是首页，尝试点击企业开办专区
if ev("document.querySelectorAll('.el-form-item').length") == 0:
    print("\n=== 3c. 点击企业开办专区 ===")
    zone_click = ev("""(function(){
        var all=document.querySelectorAll('div,span,a,h3,h4,p');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.includes('企业开办专区')||t.includes('企业开办')){
                all[i].click();
                return{clicked:t.substring(0,30)};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  zone click: {zone_click}")
    time.sleep(5)
    after_zone = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after zone: hash={after_zone.get('hash')} forms={after_zone.get('formCount')}")
    print(f"  text: {(after_zone.get('text','') or '')[:150]}")
    screenshot("after_zone")

    # 如果到了企业开办专区，再找设立登记
    if after_zone.get('formCount',0) == 0:
        print("\n=== 3d. 在专区页面找设立登记 ===")
        establish2 = ev("""(function(){
            var all=document.querySelectorAll('div,span,a,h3,h4,p,button');
            for(var i=0;i<all.length;i++){
                var t=all[i].textContent?.trim()||'';
                if((t.includes('设立')||t==='设立登记')&&t.length<20){
                    all[i].click();
                    return{clicked:t};
                }
            }
            // 也找"情景导办"
            for(var i=0;i<all.length;i++){
                var t=all[i].textContent?.trim()||'';
                if(t.includes('情景导办')||t.includes('导办')){
                    all[i].click();
                    return{clicked:t};
                }
            }
            return{error:'not_found'};
        })()""")
        print(f"  establish2 click: {establish2}")
        time.sleep(5)
        after_est2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  after: {after_est2}")
        screenshot("after_establish2")

# 4. 最终页面状态
final = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        isLogin:(document.body.innerText||'').includes('扫码登录'),
        text:(document.body.innerText||'').substring(0,400)
    };
})()""")
log("11.最终导航状态", {
    "hash": final.get("hash"),
    "formCount": final.get("formCount"),
    "isLogin": final.get("isLogin"),
    "textPreview": (final.get("text","") or "")[:200],
})

# 5. 如果有表单，探查并尝试填写
if final.get("formCount",0) > 0:
    form_info = ev("""(function(){
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
            if(input){info.ph=input.placeholder||'';info.val=(input.value||'').substring(0,40);info.disabled=input.disabled}
            r.push(info);
        }
        return r;
    })()""")
    log("12.表单字段详情", {"fields": form_info[:50]})

    # 逐字段填写
    MATERIALS = {
        "公司名称":"广西智信数据科技有限公司","名称":"广西智信数据科技有限公司",
        "注册资本":"100","经营范围":"软件开发、信息技术咨询服务",
        "住所":"南宁市青秀区民族大道166号","法定代表人":"陈明辉",
        "身份证":"450103199001151234","联系电话":"13877151234",
        "邮箱":"chenmh@example.com","监事":"李芳","财务负责人":"张丽华",
    }
    results = []
    for kw, val in MATERIALS.items():
        r = ev(f"""(function(){{
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
    ok = [r for r in results if r and r.get("ok")]
    fail = [r for r in results if r and not r.get("ok")]
    log("13.填写测试", {"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
        issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
    screenshot("after_fill")

    # 检查认证
    auth = ev("""(function(){
        var t=document.body.innerText||'';
        return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证')};
    })()""")
    log("14.认证检测", auth)
else:
    # 没有表单，记录页面内容供分析
    full_text = ev("(document.body.innerText||'').substring(0,1000)")
    log("12.无表单-页面内容", {"text": (full_text or "")[:500]})
    screenshot("no_form_page")

ws.close()
print("\n✅ Step5 完成")
