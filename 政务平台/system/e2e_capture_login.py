#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""捕获登录后token + 分析token机制 + 探查刷新API"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=15)

def ev(js, mid=1):
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")

# 1. 捕获完整登录态
print("=== 1. 登录态捕获 ===")
login_state = ev("""(function(){
    var ls={};
    for(var i=0;i<localStorage.length;i++){
        var k=localStorage.key(i);
        ls[k]=localStorage.getItem(k);
    }
    var ss={};
    for(var i=0;i<sessionStorage.length;i++){
        var k=sessionStorage.key(i);
        ss[k]=sessionStorage.getItem(k);
    }
    var cookies=document.cookie;
    return{localStorage:ls,sessionStorage:ss,cookies:cookies};
})()""")
print("localStorage:")
for k,v in (login_state.get("localStorage") or {}).items():
    val = str(v)
    print(f"  {k}: {val[:60]}{'...' if len(val)>60 else ''}")
print(f"\nsessionStorage keys: {list((login_state.get('sessionStorage') or {}).keys())}")
print(f"cookies: {(login_state.get('cookies') or '')[:100]}")

# 2. 分析token结构
token = (login_state.get("localStorage") or {}).get("Authorization","")
top_token = (login_state.get("localStorage") or {}).get("top-token","")
print(f"\n=== 2. Token分析 ===")
print(f"  Authorization: {token[:30]}... (len={len(token)})")
print(f"  top-token: {top_token[:30]}... (len={len(top_token)})")

# 检查是否JWT
is_jwt = token.count('.') == 2 if token else False
print(f"  isJWT: {is_jwt}")
if is_jwt:
    # 解码JWT payload
    jwt_decode = ev("""(function(){
        try{
            var parts=localStorage.getItem('Authorization').split('.');
            var payload=JSON.parse(atob(parts[1].replace(/-/g,'+').replace(/_/g,'/')));
            return payload;
        }catch(e){return{error:e.message}}
    })()""")
    print(f"  JWT payload: {json.dumps(jwt_decode, ensure_ascii=False, indent=2)[:300]}")

# 3. 探查刷新token API
print(f"\n=== 3. 探查刷新API ===")
refresh_apis = ev("""(function(){
    var results=[];
    var apis=[
        {method:'POST',url:'/icpsp-api/v4/pc/login/refreshToken'},
        {method:'POST',url:'/icpsp-api/v4/pc/login/refresh'},
        {method:'GET',url:'/icpsp-api/v4/pc/user/info'},
        {method:'GET',url:'/icpsp-api/v4/pc/user/getUserInfo'},
        {method:'POST',url:'/icpsp-api/v4/pc/login/token'},
        {method:'GET',url:'/icpsp-api/v1/pc/user/info'},
        {method:'POST',url:'/icpsp-api/auth/token/refresh'},
    ];
    for(var i=0;i<apis.length;i++){
        var xhr=new XMLHttpRequest();
        xhr.open(apis[i].method,apis[i].url,false);
        xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||'');
        xhr.setRequestHeader('top-token',localStorage.getItem('top-token')||'');
        xhr.setRequestHeader('Content-Type','application/json');
        try{xhr.send('{}')}catch(e){results.push({url:apis[i].url,error:e.message});continue}
        results.push({url:apis[i].url,status:xhr.status,body:xhr.responseText.substring(0,150)});
    }
    return results;
})()""")
for api in (refresh_apis or []):
    print(f"  {api.get('url','')}: status={api.get('status','ERR')} body={str(api.get('body',''))[:80]}")

# 4. 检查Vuex store中的登录信息
print(f"\n=== 4. Vuex登录状态 ===")
vuex_info = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    if(!store)return{error:'no_store'};
    var state=store.state;
    var result={modules:Object.keys(state)};
    // user module
    if(state.user){
        result.userKeys=Object.keys(state.user);
        result.userToken=state.user.token?'exists('+String(state.user.token).length+'chars)':'none';
        result.userInfo=state.user.userInfo?JSON.stringify(state.user.userInfo).substring(0,200):'none';
    }
    // login module
    if(state.login){
        result.loginKeys=Object.keys(state.login);
        result.loginInfo=JSON.stringify(state.login).substring(0,200);
    }
    // common module
    if(state.common){
        result.commonKeys=Object.keys(state.common);
        if(state.common.token)result.commonToken='exists('+String(state.common.token).length+'chars)';
    }
    return result;
})()""")
print(json.dumps(vuex_info, ensure_ascii=False, indent=2)[:500])

# 5. 监控网络请求 - 拦截XHR看token刷新机制
print(f"\n=== 5. 拦截XHR分析token机制 ===")
xhr_intercept = ev("""(function(){
    var origOpen=XMLHttpRequest.prototype.open;
    var origSend=XMLHttpRequest.prototype.send;
    var logs=[];
    XMLHttpRequest.prototype.open=function(method,url){
        this._method=method;this._url=url;
        return origOpen.apply(this,arguments);
    };
    XMLHttpRequest.prototype.send=function(){
        var self=this;
        if(self._url&&!self._url.includes('log')&&!self._url.includes('monitor')){
            logs.push({method:self._method,url:self._url,time:new Date().toISOString()});
        }
        var origOnLoad=self.onload;
        self.onload=function(){
            if(self._url&&!self._url.includes('log')){
                logs.push({method:self._method,url:self._url,status:self.status,resp:self.responseText?.substring(0,80)});
            }
            if(origOnLoad)origOnLoad.apply(this,arguments);
        };
        return origSend.apply(this,arguments);
    };
    window.__xhrLogs=logs;
    return{intercepted:true};
})()""")
print(f"  XHR拦截已安装: {xhr_intercept}")

# 6. 导航到业务页面触发请求
print(f"\n=== 6. 导航触发网络请求 ===")
nav = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    if(vm&&vm.$router){
        vm.$router.push('/index/enterprise/establish');
        return 'navigating';
    }
    return 'no_router';
})()""")
time.sleep(5)

# 收集拦截到的请求
logs = ev("window.__xhrLogs||[]")
print(f"  拦截到 {len(logs or [])} 个请求:")
for log_entry in (logs or [])[:20]:
    print(f"    {log_entry.get('method','')} {log_entry.get('url','')} → status={log_entry.get('status','pending')}")

# 7. 检查页面是否成功导航
page_state = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        isLogin:!!(document.body.innerText||'').includes('扫码登录'),
        text:(document.body.innerText||'').substring(0,200)
    };
})()""")
print(f"\n=== 7. 页面状态 ===")
print(f"  hash: {page_state.get('hash')}")
print(f"  formCount: {page_state.get('formCount')}")
print(f"  isLogin: {page_state.get('isLogin')}")
print(f"  text: {(page_state.get('text','') or '')[:150]}")

# 保存捕获的登录态
save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "login_state.json")
with open(save_path, "w", encoding="utf-8") as f:
    json.dump(login_state, f, ensure_ascii=False, indent=2)
print(f"\n  登录态已保存到: {save_path}")

ws.close()
