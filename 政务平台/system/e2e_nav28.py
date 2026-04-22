#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完全重载 → 逐步UI导航 → 尝试无需名称路径(toNotName) → 获取flow路由"""
import json, time, requests, websocket

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    return websocket.create_connection(ws_url, timeout=30)

ws = get_ws()
_mid = 0
def ev(js):
    global _mid, ws; _mid += 1; mid = _mid
    try:
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    except:
        ws = get_ws()
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 完全重载页面
print("Step 1: 完全重载页面")
ev("window.location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'")
time.sleep(8)
ws = get_ws()

# 等Vue就绪
for _ in range(10):
    ready = ev("(function(){return !!document.getElementById('app')?.__vue__})()")
    if ready: break
    time.sleep(2)
print(f"  Vue就绪: {ready}")

# Step 2: 恢复Vuex
print("\nStep 2: 恢复Vuex")
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")
time.sleep(2)

# Step 3: 安装XHR拦截器
print("\nStep 3: 安装XHR拦截器")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,500)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 导航到企业开办专区
print("\nStep 4: 导航到企业开办专区")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

# Step 5: 点击开始办理
print("\nStep 5: 点击开始办理")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

# 检查API
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")

# Step 6: 分析without-name页面
print("\nStep 6: 分析without-name页面")
wn = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(!wn)return{error:'no_comp',hash:location.hash};
    var methods=wn.$options?.methods||{};
    var srcs={};
    for(var m in methods){srcs[m]=methods[m].toString().substring(0,500)}
    return{
        compName:wn.$options?.name||'',
        methods:Object.keys(methods),
        srcs:srcs,
        fromType:wn.$data?.fromType||'',
        entType:wn.$route?.query?.entType||'',
        hash:location.hash
    };
})()""")
print(f"  compName: {wn.get('compName','') if wn else ''}")
print(f"  fromType: {wn.get('fromType','') if wn else ''}")
print(f"  entType: {wn.get('entType','') if wn else ''}")
for m, src in (wn.get('srcs',{}) or {}).items():
    print(f"  {m}: {src[:300]}")

# Step 7: 尝试toNotName
print("\nStep 7: 调用toNotName")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(wn&&typeof wn.toNotName==='function')wn.toNotName();
})()""")
time.sleep(5)

page2 = ev("""(function(){return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body?.innerText||'').substring(0,150)}})()""")
print(f"  hash={page2.get('hash','') if page2 else '?'} forms={page2.get('formCount',0) if page2 else 0}")
print(f"  text={page2.get('text','')[:80] if page2 else ''}")

# 检查API
api_logs2 = ev("window.__api_logs||[]")
new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
for l in new_apis:
    url = l.get('url','')
    print(f"  NEW API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    if l.get('status') == 200:
        try:
            resp = json.loads(l.get('response','{}'))
            print(f"    code={resp.get('code','')} data={json.dumps(resp.get('data',''),ensure_ascii=False)[:100]}")
        except: pass

# Step 8: 如果到了新页面，分析并继续
if page2 and page2.get('hash','') != page.get('hash',''):
    print("\nStep 8: 分析新页面")
    comp = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findActive(vm,d){if(d>12)return null;
            if(vm.$options?.name&&vm.$el?.offsetParent!==null&&vm.$options?.name!=='layout'&&vm.$options?.name!=='index'&&vm.$options?.name!=='all-services'){
                return{compName:vm.$options?.name,methods:Object.keys(vm.$options?.methods||{}).slice(0,15),dataKeys:Object.keys(vm.$data||{}).slice(0,15)};
            }
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findActive(vm.$children[i],d+1);if(r)return r}return null}
        return findActive(vm,0);
    })()""")
    print(f"  comp: {comp}")
    
    # 如果有表单，分析
    if page2.get('formCount',0) > 0:
        print("  ✅ 有表单！")
    
    # 逐步点击下一步
    for step in range(10):
        current = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"\n  步骤{step}: hash={current.get('hash','') if current else '?'} forms={current.get('formCount',0) if current else 0}")
        
        if current and current.get('formCount',0) > 20:
            print("  ✅ 大量表单！")
            break
        
        # 检查flow路由
        routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return flow})()""")
        if routes:
            print(f"  flow routes: {routes}")
            for route in routes:
                if 'basic-info' in route:
                    ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                    time.sleep(5)
                    break
            break
        
        # 勾选checkbox
        ev("""(function(){var cbs=document.querySelectorAll('.el-checkbox__input:not(.is-checked)');for(var i=0;i<cbs.length;i++){cbs[i].click()}})()""")
        time.sleep(1)
        
        # 点击按钮
        clicked = False
        for btn_text in ['下一步','确定','确认','同意','我已阅读','继续','保存并下一步','我同意','开始']:
            cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null&&!btns[i].disabled){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
            if cr and cr.get('clicked'):
                print(f"  点击: {btn_text}")
                clicked = True
                time.sleep(3)
                break
        
        if not clicked:
            print("  无按钮可点击")
            break
        
        # 检查API
        api_logs3 = ev("window.__api_logs||[]")
        new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs2 or [])] and 'getUserInfo' not in l.get('url','') and 'getCacheCreateTime' not in l.get('url','')]
        for l in new_apis3[-3:]:
            url = l.get('url','')
            print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        api_logs2 = api_logs3

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
print(f"  flow routes: {routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
elif routes.get('flow'):
    for route in routes.get('flow',[]):
        if 'basic-info' in route:
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(5)
            fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            if fc2 and fc2.get('formCount',0) > 10:
                print(f"✅ 表单已加载！hash={fc2.get('hash','')} forms={fc2.get('formCount',0)}")
            break

ws.close()
print("✅ 完成")
