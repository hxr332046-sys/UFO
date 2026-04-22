#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step27: 尝试直接导航设立登记路由 + 名称核准流程 + API探查"""
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

# 2. 先回首页
print("=== 1. 回首页 ===")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/page');
})()""")
time.sleep(3)

# 3. 检查所有已注册的路由中与establish/register相关
print("\n=== 2. 检查所有相关路由 ===")
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    var router=vm?.$router;
    if(!router)return{error:'no_router'};
    // 遍历所有注册的路由
    var allRoutes=[];
    function collectRoutes(routes,prefix){
        for(var i=0;i<routes.length;i++){
            var r=routes[i];
            var path=prefix+r.path;
            if(r.name||r.path)allRoutes.push({path:path,name:r.name||'',hasComp:!!r.components?.default,meta:r.meta||{}});
            if(r.children)collectRoutes(r.children,path+'/');
        }
    }
    collectRoutes(router.options.routes,'');
    // 过滤与设立/登记/注册相关
    var related=allRoutes.filter(function(r){
        var p=r.path.toLowerCase();
        return p.includes('establish')||p.includes('register')||p.includes('sheli')||p.includes('namenotice')||p.includes('apply')||p.includes('fill')||p.includes('declare')||p.includes('declaration');
    });
    return{total:allRoutes.length,related:related.slice(0,30)};
})()""")
related = (routes or {}).get('related',[])
for r in related:
    print(f"  {r.get('path','')} name={r.get('name','')} hasComp={r.get('hasComp')} auth={r.get('meta',{}).get('isAuth','')}")

# 4. 尝试导航到namenotice相关路由
print("\n=== 3. 尝试导航namenotice路由 ===")
nav_tests = [
    '/namenotice/declaration-instructions?busiType=02&entType=1100',
    '/namenotice/declaration-instructions?busiType=07&entType=1100',
    '/index/enterprise/establish?entType=1100',
    '/index/enterprise/establish',
]
for path in nav_tests:
    resolved = ev(f"""(function(){{
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        if(!router)return{{error:'no_router'}};
        var m=router.resolve('{path}');
        return{{path:'{path}',resolved:m.route.path,name:m.route.name||'',matched:m.route.matched?.length||0}};
    }})()""")
    if resolved and resolved.get('resolved') != '/404':
        print(f"  ✅ {path} → {resolved.get('resolved')} (name={resolved.get('name')}, matched={resolved.get('matched')})")
        
        # 尝试导航
        print(f"  导航中...")
        nav = ev(f"""(function(){{
            var vm=document.getElementById('app')?.__vue__;
            try{{vm.$router.push('{path}');return{{ok:true}}}}catch(e){{return{{error:e.message}}}}
        }})()""")
        time.sleep(5)
        page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
        fc = (page or {}).get('formCount',0)
        ic = (page or {}).get('inputCount',0)
        print(f"  → hash={(page or {}).get('hash')} forms={fc} inputs={ic}")
        if fc > 0 or ic > 0:
            print(f"  ✅ 找到表单！")
            break
    else:
        print(f"  ❌ {path} → 404")

# 5. 如果还是没表单，尝试API获取业务数据
print("\n=== 4. API获取用户已有企业 ===")
api = ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var apis=[
        {url:'/icpsp-api/v4/pc/register/getHandleBusiness?busiType=07&entType=1100',method:'GET'},
        {url:'/icpsp-api/v4/pc/name/check/list?pageNum=1&pageSize=10',method:'GET'},
        {url:'/icpsp-api/v4/pc/enterprise/myEnterprise',method:'GET'},
        {url:'/icpsp-api/v4/pc/register/selectModuleFlows?busiType=07&entType=1100',method:'GET'},
        {url:'/icpsp-api/v4/pc/register/guideFlow?busiType=07&entType=1100',method:'GET'},
    ];
    var results=[];
    for(var i=0;i<apis.length;i++){
        var xhr=new XMLHttpRequest();
        xhr.open(apis[i].method,apis[i].url,false);
        xhr.setRequestHeader('top-token',t);
        xhr.setRequestHeader('Authorization',t);
        try{xhr.send()}catch(e){results.push({url:apis[i].url,error:e.message});continue}
        results.push({url:apis[i].url,status:xhr.status,body:xhr.responseText?.substring(0,200)||''});
    }
    return results;
})()""")
for a in (api or []):
    url_short = (a.get('url','') or '').split('?')[0].split('/')[-1]
    print(f"  {url_short}: {a.get('status','ERR')} {(a.get('body','') or '')[:100]}")

# 6. 尝试通过"全部服务"→"设立登记"进入
print("\n=== 5. 全部服务→设立登记 ===")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/page');
})()""")
time.sleep(3)

# 找设立登记卡片并分析其Vue方法
card = ev("""(function(){
    var all=document.querySelectorAll('div,span');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='设立登记'&&all[i].offsetParent!==null&&all[i].children.length<3){
            // 向上找有getHandleBusiness方法的组件
            var el=all[i];
            for(var j=0;j<10&&el;j++){
                if(el.__vue__){
                    var vm=el.__vue__;
                    if(vm.getHandleBusiness){
                        // 调用getHandleBusiness，busiType=07是设立登记
                        vm.getHandleBusiness({entType:'1100'});
                        return{called:'getHandleBusiness',on:vm.$options?.name||''};
                    }
                    if(vm.handleClick){
                        vm.handleClick({text:'设立登记'});
                        return{called:'handleClick',on:vm.$options?.name||''};
                    }
                }
                el=el.parentElement;
            }
            // 直接点击
            all[i].click();
            return{clicked:'native'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  card: {card}")
time.sleep(5)

page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,300)})")
print(f"  hash: {(page or {}).get('hash','?')} forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:200]}")

# 7. 如果到了namenotice页面，探查
if 'namenotice' in (page or {}).get('hash',''):
    print("\n=== 6. namenotice页面探查 ===")
    # 等待加载
    for attempt in range(8):
        time.sleep(3)
        check = ev("({formCount:document.querySelectorAll('.el-form-item').length,inputCount:document.querySelectorAll('input,textarea,select').length,text:(document.body.innerText||'').substring(0,200)})")
        fc = (check or {}).get('formCount',0)
        ic = (check or {}).get('inputCount',0)
        print(f"  {attempt+1}: forms={fc} inputs={ic}")
        if fc > 0 or ic > 0:
            break
    
    # 分析组件
    comp = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var comps=[];
        for(var i=0;i<matched.length;i++){
            var m=matched[i];
            var inst=m.instances?.default;
            if(inst){
                var methods=[];
                for(var k in inst.$options?.methods||{}){
                    methods.push(k+':'+inst.$options.methods[k].toString().substring(0,60));
                }
                comps.push({path:m.path,name:m.name||'',methods:methods.slice(0,10),data:JSON.stringify(inst.$data)?.substring(0,200)});
            }
        }
        return comps;
    })()""")
    for c in (comp or []):
        print(f"  {c.get('name','')}: methods={c.get('methods',[])}")
        print(f"  data: {c.get('data','')[:100]}")

# 8. 最终检查
final = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,300)};
})()""")
log("59.设立登记导航尝试", {"hash":(final or {}).get("hash"),"formCount":(final or {}).get("formCount",0),"inputCount":(final or {}).get("inputCount",0),"text":(final.get("text","") or "")[:100]})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step27.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step27 完成")
