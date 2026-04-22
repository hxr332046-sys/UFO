#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 通过namenotice步骤 → 到达flow/base/basic-info表单"""
import json, time, os, requests, websocket
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# 恢复Vuex
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

# Step 1: 先调用bindName API获取nameId
print("Step 1: 调用bindName API")
bind_result = ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var xhr=new XMLHttpRequest();
    xhr.open('POST','/icpsp-api/v4/pc/register/index/bindName',false);
    xhr.setRequestHeader('Content-Type','application/json');
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{
        xhr.send(JSON.stringify({nId:'test_auto_001'}));
        if(xhr.status===200){
            var resp=JSON.parse(xhr.responseText);
            return{status:xhr.status,code:resp.code,data:JSON.stringify(resp.data)?.substring(0,200)||'',msg:resp.msg||''};
        }
        return{status:xhr.status,response:xhr.responseText?.substring(0,200)||''};
    }catch(e){return{error:e.message}}
})()""")
print(f"  bind_result: {bind_result}")

# Step 2: 如果bindName失败，尝试其他API路径
if not bind_result or bind_result.get('status') != 200 or bind_result.get('code') != '00000':
    print("\nStep 2: 尝试其他bindName路径")
    for path in [
        '/icpsp-api/v4/pc/register/index/bindName',
        '/icpsp-api/v4/pc/flow/index/bindName',
        '/icpsp-api/v4/pc/register/guide/bindName',
        '/icpsp-api/v4/pc/register/name/bindName',
        '/icpsp-api/v4/pc/flow/name/bindName',
    ]:
        r = ev(f"""(function(){{
            var t=localStorage.getItem('top-token')||'';
            var xhr=new XMLHttpRequest();
            xhr.open('POST','{path}',false);
            xhr.setRequestHeader('Content-Type','application/json');
            xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
            try{{
                xhr.send(JSON.stringify({{nId:'test_auto_001'}}));
                if(xhr.status===200){{
                    var resp=JSON.parse(xhr.responseText);
                    return{{status:xhr.status,code:resp.code,data:JSON.stringify(resp.data)?.substring(0,100)||'',msg:resp.msg||''}};
                }}
                return{{status:xhr.status}};
            }}catch(e){{return{{error:e.message}}}}
        }})()""")
        status = r.get('status',0) if r else 0
        code = r.get('code','') if r else ''
        print(f"  {path.split('/').pop()}: status={status} code={code}")
        if status == 200 and code == '00000':
            print(f"  ✅ 成功! data={r.get('data','')[:60]}")
            break

# Step 3: 确保动态路由已注册
print("\nStep 3: 确保动态路由已注册")
# 如果还没注册，重新调用getHandleBusiness
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

if not routes.get('flow'):
    print("  重新注册路由...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0)||findComp(vm,'without-name',0);
        if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness({entType:'1100',nameId:'test_auto_001'});
    })()""")
    time.sleep(3)
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  routes2: total={routes.get('total',0)} flow={routes.get('flow',[])}")

# Step 4: 导航到namenotice/declaration-instructions
print("\nStep 4: 导航到namenotice页面")
flow_routes = routes.get('flow',[])
for route in flow_routes:
    print(f"  尝试: {route}")
    ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
    time.sleep(3)
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body?.innerText||'').substring(0,80)})")
    print(f"    hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0} text={fc.get('text','')[:40] if fc else ''}")
    if fc and fc.get('formCount',0) > 0:
        print("    ✅ 有表单！")
        break
    if fc and fc.get('hash','') != '#/index/select-prise' and fc.get('hash','') != '#/index/page':
        print("    页面已变化")
        # 不break，继续尝试其他路由

# Step 5: 如果到达了namenotice页面，分析并继续
print("\nStep 5: 分析当前页面")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body?.innerText||'').substring(0,150)})")
print(f"  hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")
print(f"  text={page.get('text','')[:80] if page else ''}")

# 如果在namenotice页面，找下一步按钮
if page and 'namenotice' in page.get('hash',''):
    print("\n  在namenotice页面，找下一步按钮")
    btns = ev("""(function(){var btns=document.querySelectorAll('button,.el-button');var r=[];for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||''})}return r})()""")
    print(f"  按钮: {btns}")
    
    # 安装XHR拦截器
    ev("""(function(){
        window.__api_logs=[];
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
        var origSend=XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send=function(body){
            var self=this;self.__body=body;
            this.addEventListener('load',function(){
                if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                    window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,200)||'',body:self.__body?.substring(0,100)||''});
                }
            });
            return origSend.apply(this,arguments);
        };
    })()""")
    
    # 逐步点击下一步
    for step in range(8):
        current = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"\n  步骤{step}: hash={current.get('hash','') if current else '?'} forms={current.get('formCount',0) if current else 0}")
        
        if current and 'flow/base' in current.get('hash',''):
            print("  ✅ 到达flow/base！")
            break
        
        # 点击下一步/确定/同意
        clicked = False
        for btn_text in ['下一步','确定','确认','同意','我已阅读','继续','保存并下一步']:
            cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null&&!btns[i].disabled){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
            if cr and cr.get('clicked'):
                print(f"  点击: {btn_text}")
                clicked = True
                time.sleep(3)
                break
        
        if not clicked:
            # 可能需要填写表单
            if current and current.get('formCount',0) > 0:
                print("  需要填写表单...")
                # 填写所有可见input
                ev("""(function(){
                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
                    for(var i=0;i<inputs.length;i++){
                        if(!inputs[i].value&&inputs[i].offsetParent!==null&&!inputs[i].disabled){
                            s.call(inputs[i],'测试数据');inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
                        }
                    }
                })()""")
                time.sleep(1)
                # 重试点击
                for btn_text in ['下一步','确定','确认','保存']:
                    cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
                    if cr and cr.get('clicked'):
                        print(f"  点击: {btn_text}")
                        time.sleep(3)
                        break
            else:
                print("  无按钮可点击，停止")
                break
        
        # 检查API调用
        api_logs = ev("window.__api_logs||[]")
        if api_logs and len(api_logs) > 0:
            for l in api_logs[-3:]:
                print(f"  API: {l.get('method','')} {l.get('url','').split('?')[0].split('/').pop()} status={l.get('status')}")

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 检查flow路由是否已注册
routes_final = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow/base')});
    return{total:all.length,flow:flow};
})()""")
print(f"  flow/base routes: {routes_final.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("470.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
elif routes_final.get('flow'):
    print("  flow/base路由已注册，尝试导航...")
    for route in routes_final.get('flow',[]):
        ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
        time.sleep(5)
        fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  hash={fc2.get('hash','') if fc2 else '?'} forms={fc2.get('formCount',0) if fc2 else 0}")
        if fc2 and fc2.get('formCount',0) > 10:
            print("✅ 表单已加载！")
            log("470b.表单加载成功", {"hash":fc2.get('hash'),"formCount":fc2.get('formCount',0)})
            break
else:
    log("470.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})

ws.close()
print("✅ 完成")
