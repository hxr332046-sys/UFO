#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step4: 捕获登录态 + 拦截网络请求 + 导航到设立登记 + 探查表单"""
import json, time, os, requests, websocket
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

CDP_PORT = 9225
pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
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

# 1. 完整捕获登录态
print("=== 1. 登录态捕获 ===")
state = ev("""(function(){
    var ls={};
    for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);ls[k]=localStorage.getItem(k)}
    return{ls:ls,cookie:document.cookie};
})()""")
ls = state.get("ls") or {}
print(f"  Authorization: {(ls.get('Authorization') or 'NONE')[:30]}")
print(f"  top-token: {(ls.get('top-token') or 'NONE')[:30]}")
print(f"  cookie: {(state.get('cookie') or '')[:80]}")
print(f"  ls keys: {list(ls.keys())}")

# 保存完整登录态
os.makedirs(os.path.join(os.path.dirname(__file__), "..", "data"), exist_ok=True)
with open(os.path.join(os.path.dirname(__file__), "..", "data", "login_state.json"), "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

# 2. 安装网络请求监控（CDP方式，比XHR拦截更可靠）
print("\n=== 2. 安装CDP网络监控 ===")
ws.send(json.dumps({"id":1000,"method":"Network.enable","params":{}}))
# 忽略1000的响应
time.sleep(0.5)

# 3. 导航到设立登记页面
print("\n=== 3. 导航到设立登记 ===")
ws.send(json.dumps({"id":1001,"method":"Page.navigate","params":{"url":"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/establish"}}))
time.sleep(8)

# 收集网络请求
network_logs = []
deadline = time.time() + 3
while time.time() < deadline:
    try:
        ws.settimeout(0.5)
        msg = ws.recv()
        data = json.loads(msg)
        method = data.get("method","")
        if method == "Network.requestWillBeSent":
            req = data.get("params",{}).get("request",{})
            url = req.get("url","")
            if "icpsp" in url and not any(x in url for x in [".js",".css",".png",".jpg",".woff",".ico",".svg"]):
                headers = req.get("headers",{})
                network_logs.append({
                    "method": req.get("method",""),
                    "url": url[:120],
                    "hasAuth": "Authorization" in headers or "top-token" in headers,
                    "authVal": (headers.get("Authorization","") or "")[:20],
                    "topToken": (headers.get("top-token","") or "")[:20],
                })
        elif method == "Network.responseReceived":
            resp = data.get("params",{}).get("response",{})
            url = resp.get("url","")
            if "icpsp" in url and not any(x in url for x in [".js",".css",".png",".jpg",".woff"]):
                for nl in network_logs:
                    if nl["url"] in url:
                        nl["status"] = resp.get("status")
                        break
    except:
        break

print(f"  捕获到 {len(network_logs)} 个API请求:")
for nl in network_logs[:20]:
    print(f"    {nl.get('method','')} {nl.get('url','')[:80]} → {nl.get('status','?')} auth={nl.get('hasAuth')}")

# 4. 检查页面状态
page = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        isLogin:(document.body.innerText||'').includes('扫码登录'),
        text:(document.body.innerText||'').substring(0,300)
    };
})()""")
print(f"\n=== 4. 页面状态 ===")
print(f"  hash: {page.get('hash')}")
print(f"  formCount: {page.get('formCount')}")
print(f"  isLogin: {page.get('isLogin')}")

if page.get("isLogin"):
    log("7.导航结果", {"hash": page.get("hash"), "isLogin": True, "formCount": 0},
        issues=["导航后仍显示登录页，token可能未正确注入到Vuex"])
    # 尝试手动恢复Vuex
    print("\n=== 4a. 尝试恢复Vuex登录态 ===")
    restore = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app&&app.__vue__;
        var store=vm&&vm.$store;
        if(!store)return{error:'no_store'};
        var token=localStorage.getItem('Authorization');
        var topToken=localStorage.getItem('top-token');
        // 尝试各种commit
        var commits=[];
        var mutations=['SET_TOKEN','setToken','LOGIN','SET_LOGIN_INFO','SET_USER_INFO'];
        for(var i=0;i<mutations.length;i++){
            try{store.commit(mutations[i],{token:token,topToken:topToken});commits.push(mutations[i]+':ok')}catch(e){commits.push(mutations[i]+':'+e.message.substring(0,30))}
        }
        // 直接修改state
        if(store.state.login){
            store.state.login.token=token;
            commits.push('direct_login.token:ok');
        }
        return{commits:commits,loginToken:store.state.login?.token?'set':'empty'};
    })()""")
    print(f"  restore: {json.dumps(restore, ensure_ascii=False)}")
    time.sleep(2)

    # 再次检查
    page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, isLogin:(document.body.innerText||'').includes('扫码登录')})")
    print(f"  after restore: hash={page2.get('hash')} forms={page2.get('formCount')} login={page2.get('isLogin')}")

    # 如果还是登录页，尝试刷新
    if page2.get("isLogin"):
        print("\n=== 4b. 刷新页面 ===")
        ev("location.reload()")
        time.sleep(8)
        page3 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, isLogin:(document.body.innerText||'').includes('扫码登录')})")
        print(f"  after reload: hash={page3.get('hash')} forms={page3.get('formCount')} login={page3.get('isLogin')}")
else:
    # 成功导航！探查表单
    log("7.导航成功", {"hash": page.get("hash"), "formCount": page.get("formCount"), "isLogin": False})

    # 5. 探查表单结构
    form_info = ev("""(function(){
        var r={steps:[],tabs:[],formItems:[],buttons:[],uploads:[]};
        var steps=document.querySelectorAll('.el-step');
        for(var i=0;i<steps.length;i++){r.steps.push({i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||'',active:steps[i].className.includes('is-active')})}
        var tabs=document.querySelectorAll('.el-tabs__item');
        for(var i=0;i<tabs.length;i++){r.tabs.push(tabs[i].textContent?.trim())}
        var fi=document.querySelectorAll('.el-form-item');
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
            r.formItems.push(info);
        }
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){var t=btns[i].textContent?.trim();if(t&&t.length<25)r.buttons.push({text:t,disabled:btns[i].disabled})}
        return r;
    })()""")

    log("8.设立登记表单结构", {
        "steps": form_info.get("steps",[]),
        "tabs": form_info.get("tabs",[]),
        "formCount": len(form_info.get("formItems",[])),
        "buttons": form_info.get("buttons",[])[:15],
    })

    items = form_info.get("formItems",[])
    fillable = [f for f in items if f.get("type") in ("input","textarea") and not f.get("disabled")]
    selects = [f for f in items if f.get("type") == "select"]
    uploads = [f for f in items if f.get("type") == "upload"]
    required = [f for f in items if f.get("required")]

    log("8a.字段分类", {"可填input": len(fillable), "select下拉": len(selects), "upload上传": len(uploads), "必填": len(required)})
    log("8b.全部字段", {"fields": items[:50]})

    # 6. 逐字段填写测试
    MATERIALS = {
        "公司名称": "广西智信数据科技有限公司",
        "名称": "广西智信数据科技有限公司",
        "注册资本": "100",
        "经营范围": "软件开发、信息技术咨询服务",
        "住所": "南宁市青秀区民族大道166号",
        "法定代表人": "陈明辉",
        "身份证": "450103199001151234",
        "联系电话": "13877151234",
        "邮箱": "chenmh@example.com",
        "监事": "李芳",
        "财务负责人": "张丽华",
    }

    fill_results = []
    for label_kw, value in MATERIALS.items():
        result = ev(f"""(function(){{
            var keyword='{label_kw}';var value='{value}';
            var fi=document.querySelectorAll('.el-form-item');
            for(var i=0;i<fi.length;i++){{
                var label=fi[i].querySelector('.el-form-item__label');
                if(label&&label.textContent.trim().includes(keyword)){{
                    var input=fi[i].querySelector('.el-input__inner,.el-textarea__inner');
                    if(input&&!input.disabled){{
                        var setter=Object.getOwnPropertyDescriptor(window[input.tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                        setter.call(input,value);
                        input.dispatchEvent(new Event('input',{{bubbles:true}}));
                        input.dispatchEvent(new Event('change',{{bubbles:true}}));
                        return{{ok:true,label:label.textContent.trim(),val:value}};
                    }}
                    return{{ok:false,label:label.textContent.trim(),reason:'no_input_or_disabled'}};
                }}
            }}
            return{{ok:false,label:keyword,reason:'not_found'}};
        }})()""")
        fill_results.append(result or {"ok":False, "label":label_kw, "reason":"cdp_error"})

    ok = [r for r in fill_results if r and r.get("ok")]
    fail = [r for r in fill_results if r and not r.get("ok")]
    log("9.表单填写测试", {"attempted":len(MATERIALS),"success":len(ok),"failed":len(fail),"ok_details":ok,"fail_details":fail},
        issues=[f"填写失败: {r.get('label','')}({r.get('reason','')})" for r in fail])

    # 7. 检查认证要求
    auth = ev("""(function(){
        var t=document.body.innerText||'';
        var r={faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证')};
        var dialogs=document.querySelectorAll('.el-dialog:not([style*="display: none"])');
        for(var i=0;i<dialogs.length;i++){var dt=dialogs[i].textContent||'';if(dt.includes('认证')||dt.includes('人脸'))r.activeDialog=dt.substring(0,100)}
        return r;
    })()""")
    log("10.认证检测", auth)
    if auth:
        for k,v in auth.items():
            if v and k != "activeDialog": add_auth_finding(f"页面检测到{k}: {v}")

    # 8. 截图保存
    ss_path = os.path.join(os.path.dirname(__file__), "..", "data", "establish_page.png")
    ev(f"""(function(){{
        var c=document.createElement('canvas');c.width=window.innerWidth;c.height=window.innerHeight;
        // CDP截图更可靠，这里先标记
        return 'canvas_not_available';
    }})()""")
    # 用CDP截图
    ws.send(json.dumps({"id":2000,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 2000:
            import base64
            img_data = r.get("result",{}).get("data","")
            if img_data:
                with open(ss_path, "wb") as f:
                    f.write(base64.b64decode(img_data))
                print(f"\n  截图已保存: {ss_path}")
            break

ws.close()
print("\n✅ Step4 完成")
