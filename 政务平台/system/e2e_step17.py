#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step17: 精确分析设立登记卡片的Vue点击处理 → 触发正确导航"""
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
    while True:
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None

# 1. 找到设立登记卡片的精确DOM和Vue实例
print("=== 1. 设立登记卡片Vue分析 ===")
card_analysis = ev("""(function(){
    var r={found:false};
    var all=document.querySelectorAll('div,span');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='设立登记'&&all[i].offsetParent!==null){
            r.found=true;
            r.tag=all[i].tagName;
            r.cls=all[i].className||'';
            r.parentTag=all[i].parentElement?.tagName||'';
            r.parentCls=all[i].parentElement?.className||'';
            r.grandParentCls=all[i].parentElement?.parentElement?.className||'';
            
            // 找Vue实例 - 向上遍历
            var el=all[i];
            for(var j=0;j<8&&el;j++){
                if(el.__vue__){
                    var vm=el.__vue__;
                    r.vueLevel=j;
                    r.vueTag=vm.$options?.name||'';
                    r.vueFile=vm.$options?.__file||'';
                    
                    // 获取所有方法
                    var methods=[];
                    var proto=Object.getPrototypeOf(vm);
                    for(var k in proto){
                        if(typeof proto[k]==='function'&&k.charAt(0)!=='_'&&!k.startsWith('$')){
                            methods.push(k+':'+proto[k].toString().substring(0,80));
                        }
                    }
                    r.methods=methods.slice(0,15);
                    
                    // 获取$data
                    var dataKeys=[];
                    for(var k in vm.$data||{}){
                        var v=vm.$data[k];
                        dataKeys.push(k+':'+(typeof v==='object'?JSON.stringify(v)?.substring(0,40):String(v).substring(0,20)));
                    }
                    r.dataKeys=dataKeys.slice(0,15);
                    
                    // 获取$listeners
                    r.listeners=Object.keys(vm.$listeners||{});
                    
                    // 获取$attrs
                    r.attrs=Object.keys(vm.$attrs||{});
                    
                    // 获取vnode信息
                    var vnode=vm._vnode||vm.$vnode;
                    if(vnode){
                        r.vnodeTag=vnode.tag||'';
                        r.vnodeData=JSON.stringify(vnode.data?.on||{}).substring(0,100);
                    }
                    
                    // 获取props
                    var props=[];
                    for(var k in vm.$props||{}){
                        props.push(k+':'+String(vm.$props[k]).substring(0,30));
                    }
                    r.props=props.slice(0,10);
                    
                    break;
                }
                el=el.parentElement;
            }
            break;
        }
    }
    return r;
})()""")
print(f"  found: {card_analysis.get('found')}")
print(f"  vueLevel: {card_analysis.get('vueLevel')}")
print(f"  vueTag: {card_analysis.get('vueTag')}")
print(f"  vueFile: {card_analysis.get('vueFile')}")
print(f"  methods: {card_analysis.get('methods',[])}")
print(f"  dataKeys: {card_analysis.get('dataKeys',[])}")
print(f"  listeners: {card_analysis.get('listeners')}")
print(f"  attrs: {card_analysis.get('attrs')}")
print(f"  vnodeData: {card_analysis.get('vnodeData')}")
print(f"  props: {card_analysis.get('props')}")

# 2. 找到卡片容器组件（可能是服务列表组件）
print("\n=== 2. 卡片容器组件 ===")
container = ev("""(function(){
    var r=[];
    var all=document.querySelectorAll('div,span');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='设立登记'&&all[i].offsetParent!==null){
            // 向上找有Vue实例的容器
            var el=all[i].parentElement;
            for(var j=0;j<10&&el;j++){
                if(el.__vue__){
                    var vm=el.__vue__;
                    var name=vm.$options?.name||'';
                    if(name&&name!=='ElMenuItem'&&name!=='swiper-slide'){
                        var methods=[];
                        var proto=Object.getPrototypeOf(vm);
                        for(var k in proto){
                            if(typeof proto[k]==='function'&&k.charAt(0)!=='_'&&!k.startsWith('$')){
                                methods.push(k);
                            }
                        }
                        r.push({level:j,name:name,methods:methods.slice(0,10),tag:el.tagName,cls:el.className?.substring(0,30)});
                    }
                }
                el=el.parentElement;
            }
            break;
        }
    }
    return r;
})()""")
for c in (container or []):
    print(f"  [{c.get('level')}] {c.get('name')} methods={c.get('methods')}")

# 3. 找到有handleClick/goTo等方法的组件并调用
print("\n=== 3. 调用导航方法 ===")
nav_result = ev("""(function(){
    var all=document.querySelectorAll('div,span');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='设立登记'&&all[i].offsetParent!==null){
            var el=all[i].parentElement;
            for(var j=0;j<10&&el;j++){
                if(el.__vue__){
                    var vm=el.__vue__;
                    // 检查所有方法
                    var proto=Object.getPrototypeOf(vm);
                    for(var k in proto){
                        if(typeof proto[k]==='function'&&k.charAt(0)!=='_'){
                            var fnStr=proto[k].toString();
                            // 找包含router或navigate的方法
                            if(fnStr.includes('router')||fnStr.includes('push')||fnStr.includes('navigate')||fnStr.includes('route')){
                                return{method:k,on:vm.$options?.name||'',fnPreview:fnStr.substring(0,200)};
                            }
                        }
                    }
                    // 检查$listeners中的click
                    if(vm.$listeners&&vm.$listeners.click){
                        return{hasClickListener:true,listenerStr:vm.$listeners.click.toString().substring(0,200)};
                    }
                }
                el=el.parentElement;
            }
            break;
        }
    }
    return{error:'no_nav_method_found'};
})()""")
print(f"  nav: {json.dumps(nav_result, ensure_ascii=False)[:400]}")

# 4. 如果找到了方法，调用它
if nav_result and nav_result.get('method'):
    method_name = nav_result['method']
    print(f"\n=== 4. 调用 {method_name} ===")
    call_result = ev(f"""(function(){{
        var all=document.querySelectorAll('div,span');
        for(var i=0;i<all.length;i++){{
            var t=all[i].textContent?.trim()||'';
            if(t==='设立登记'&&all[i].offsetParent!==null){{
                var el=all[i].parentElement;
                for(var j=0;j<10&&el;j++){{
                    if(el.__vue__){{
                        var vm=el.__vue__;
                        if(vm.{method_name}){{
                            // 尝试不同参数
                            try{{vm.{method_name}('设立登记');return{{called:true,method:'{method_name}',arg:'设立登记'}}}}catch(e){{}}
                            try{{vm.{method_name}({{text:'设立登记'}});return{{called:true,method:'{method_name}',arg:'object'}}}}catch(e){{}}
                            try{{vm.{method_name}();return{{called:true,method:'{method_name}',arg:'none'}}}}catch(e){{}}
                            try{{vm.{method_name}(0);return{{called:true,method:'{method_name}',arg:'0'}}}}catch(e){{}}
                            return{{error:'all_args_failed'}};
                        }}
                    }}
                    el=el.parentElement;
                }}
                break;
            }}
        }}
    }})()""")
    print(f"  call: {call_result}")
    time.sleep(5)
    page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, text:(document.body.innerText||'').substring(0,200)})")
    print(f"  after: hash={page.get('hash')} forms={page.get('formCount')}")

# 5. 如果没找到方法，尝试直接用Vue Router push到设立登记路由
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 5. 尝试所有可能的设立登记路由 ===")
    # 先检查路由注册
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        if(!router)return[];
        var testPaths=[
            '/index/without-name?entType=1100',
            '/index/establish?entType=1100',
            '/index/enterprise/establish',
            '/index/establish-register',
            '/index/company-establish',
            '/index/service/establish',
            '/index/registration/establish',
            '/index/enterprise/register',
            '/index/enterprise-zone/establish',
            '/index/enterprise-zone/register',
            '/index/name-check?entType=1100',
            '/index/without-name',
        ];
        return testPaths.map(function(p){
            var m=router.resolve(p);
            return{path:p,resolved:m.route.path,name:m.route.name||'',matched:m.route.matched?.length||0};
        });
    })()""")
    for r in (routes or []):
        if r.get('resolved') != '/404':
            print(f"  ✅ {r.get('path')} → {r.get('resolved')} (name={r.get('name')}, matched={r.get('matched')})")
        else:
            print(f"  ❌ {r.get('path')} → 404")

    # 导航到非404路由
    valid = [r for r in (routes or []) if r.get('resolved') != '/404' and r.get('matched',0) > 1]
    if valid:
        for v in valid:
            print(f"\n  尝试: {v.get('path')}")
            nav = ev(f"""(function(){{
                var vm=document.getElementById('app')?.__vue__;
                if(!vm?.$router)return{{error:'no_router'}};
                try{{vm.$router.push('{v.get("path")}');return{{ok:true}}}}catch(e){{return{{error:e.message}}}}
            }})()""")
            print(f"  nav: {nav}")
            time.sleep(5)
            page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length})")
            print(f"  result: {page}")
            if page.get('formCount',0) > 0 or page.get('inputCount',0) > 0:
                print("  ✅ 找到表单！")
                break

# 6. 如果还是没表单，尝试通过API获取业务数据
if ev("document.querySelectorAll('.el-form-item').length") in (0, None):
    print("\n=== 6. API探查 ===")
    api_results = ev("""(function(){
        var topToken=localStorage.getItem('top-token')||'';
        var apis=[
            '/icpsp-api/enterprise/v1/establish/apply',
            '/icpsp-api/v1/pc/register/apply',
            '/icpsp-api/v4/pc/service/list',
            '/icpsp-api/v4/pc/service/category',
            '/icpsp-api/v4/pc/menu/list',
            '/icpsp-api/v4/pc/enterprise/info',
            '/icpsp-api/v4/pc/user/info',
        ];
        var results=[];
        for(var i=0;i<apis.length;i++){
            var xhr=new XMLHttpRequest();
            xhr.open('GET',apis[i],false);
            xhr.setRequestHeader('top-token',topToken);
            xhr.setRequestHeader('Authorization',topToken);
            try{xhr.send()}catch(e){results.push({api:apis[i],error:e.message});continue}
            var body=xhr.responseText||'';
            results.push({api:apis[i],status:xhr.status,body:body.substring(0,100)});
        }
        return results;
    })()""")
    for a in (api_results or []):
        print(f"  {a.get('api','')}: {a.get('status','ERR')} {str(a.get('body',''))[:60]}")

# 最终状态
final = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,200)})")
log("38.设立登记导航", {"hash":final.get("hash"),"formCount":final.get("formCount"),"inputCount":final.get("inputCount"),"text":(final.get("text","") or "")[:100]})

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    while True:
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step17.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step17 完成")
