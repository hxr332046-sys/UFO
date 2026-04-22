#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发现正确的API端点和参数格式"""
import json, time, requests, websocket

def ev(js, timeout=20):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type") == "page" and "core.html" in p.get("url", "")]
        if not page:
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")]
        if not page: return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 找operationBusinessDataInfo的API路径
# ============================================================
print("Step 1: find API path")
api_info = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    
    // 找a对象（API service）
    var a=fc.$data?.a||fc.a;
    if(!a){
        // 找注入的service
        var keys=Object.keys(fc).filter(function(k){return k.includes('service')||k.includes('Service')||k.includes('api')||k.includes('Api')});
        return {noA:true,keys:keys.slice(0,10)};
    }
    
    // 查看a的方法
    var methods=Object.keys(a).filter(function(k){return typeof a[k]==='function'});
    var obdi=a.operationBusinessDataInfo;
    if(!obdi)return{noMethod:true,methods:methods.slice(0,10)};
    
    return {
        obdiSrc:obdi.toString().substring(0,500),
        methods:methods.slice(0,15)
    };
})()""", timeout=15)
print(f"  {json.dumps(api_info, ensure_ascii=False)[:400] if isinstance(api_info,dict) else api_info}")

# ============================================================
# Step 2: 拦截所有网络请求，让SPA保存一次
# ============================================================
print("\nStep 2: intercept all network + SPA save")
ev("""(function(){
    window.__all_requests=[];
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){
        this.__method=m;
        this.__url=u;
        return origOpen.apply(this,arguments);
    };
    XMLHttpRequest.prototype.send=function(body){
        window.__all_requests.push({
            method:this.__method||'GET',
            url:(this.__url||'').substring(0,100),
            bodyLen:(body||'').length,
            bodyPreview:(body||'').substring(0,80)
        });
        return origSend.apply(this,arguments);
    };
})()""")

# 点击保存
click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('保存并下一步')||t.includes('下一步'))&&!all[i].disabled&&all[i].offsetParent!==null){
            all[i].click();return{clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  click: {click}")
time.sleep(12)

# 查看所有请求
all_reqs = ev("window.__all_requests")
print(f"  requests: {json.dumps(all_reqs, ensure_ascii=False)[:600] if isinstance(all_reqs,list) else all_reqs}")

# ============================================================
# Step 3: 找到正确的API URL
# ============================================================
print("\nStep 3: find correct API URL")
if isinstance(all_reqs, list):
    for r in all_reqs:
        url = r.get('url', '')
        if 'operationBusiness' in url or 'BasicInfo' in url or 'flow' in url or 'save' in url:
            print(f"  >>> {r.get('method')} {url}")
            print(f"      bodyLen={r.get('bodyLen')} preview={r.get('bodyPreview','')[:60]}")

# ============================================================
# Step 4: 用正确的URL + 修复后的body直接fetch
# ============================================================
print("\nStep 4: direct fetch with correct URL")
# 先获取token
tokens = ev("""(function(){
    return {
        topToken:localStorage.getItem('top-token')||'',
        auth:localStorage.getItem('Authorization')||'',
        baseURL:window.location.origin
    };
})()""")
print(f"  tokens: {json.dumps(tokens, ensure_ascii=False)[:200] if isinstance(tokens,dict) else tokens}")

# 找到API URL后直接fetch
if isinstance(all_reqs, list):
    target_req = None
    for r in all_reqs:
        if 'operationBusiness' in r.get('url', ''):
            target_req = r
            break
    
    if target_req:
        target_url = target_req.get('url', '')
        print(f"  target URL: {target_url}")
        
        # 获取bdi构造body
        fetch_result = ev(f"""(function(){{
            var vm=document.getElementById('app').__vue__;
            function findComp(vm,name,d){{if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var fc=findComp(vm,'flow-control',0);
            var bdi=fc?.$data?.businessDataInfo||{{}};
            var token=localStorage.getItem('top-token')||'';
            var auth=localStorage.getItem('Authorization')||'';
            
            // 从bdi构造body，修复所有字段
            var body=JSON.parse(JSON.stringify(bdi));
            
            // 修复busiAreaData
            if(typeof body.busiAreaData==='string'){{
                try{{body.busiAreaData=JSON.parse(decodeURIComponent(body.busiAreaData))}}catch(e){{try{{body.busiAreaData=JSON.parse(body.busiAreaData)}}catch(e2){{}}}}
            }}
            if(body.busiAreaData&&typeof body.busiAreaData==='object'&&!Array.isArray(body.busiAreaData)&&body.busiAreaData.param){{
                body.busiAreaData=body.busiAreaData.param;
            }}
            
            // 修复genBusiArea
            if(typeof body.genBusiArea==='string'&&body.genBusiArea.indexOf('%')===0){{
                try{{var g=decodeURIComponent(body.genBusiArea);if(g.charAt(0)==='"'&&g.charAt(g.length-1)==='"')g=g.substring(1,g.length-1);body.genBusiArea=g}}catch(e){{}}
            }}
            
            // 修复linkData
            if(body.linkData&&typeof body.linkData.busiCompUrlPaths==='string'){{
                try{{body.linkData.busiCompUrlPaths=JSON.parse(decodeURIComponent(body.linkData.busiCompUrlPaths))}}catch(e){{}}
            }}
            
            // 修复flowData
            if(body.flowData&&body.flowData.vipChannel==='null')body.flowData.vipChannel=null;
            
            return fetch('{target_url}',{{
                method:'POST',
                headers:{{'Content-Type':'application/json','Authorization':auth,'top-token':token}},
                body:JSON.stringify(body)
            }}).then(function(r){{return r.json()}}).then(function(d){{
                return {{code:d.code,msg:d.msg?.substring(0,80),dataKeys:d.data?Object.keys(d.data).slice(0,5):[]}};
            }}).catch(function(e){{return 'err:'+e.message}});
        }})()""", timeout=20)
        print(f"  fetch result: {fetch_result}")
    else:
        print("  no operationBusiness request found")
        # 尝试所有URL
        for r in all_reqs:
            url = r.get('url', '')
            if url and not url.includes('js') and not url.includes('css'):
                print(f"  trying: {url}")
                result = ev(f"""(function(){{
                    var token=localStorage.getItem('top-token')||'';
                    var auth=localStorage.getItem('Authorization')||'';
                    return fetch('{url}',{{
                        method:'POST',
                        headers:{{'Content-Type':'application/json','Authorization':auth,'top-token':token}},
                        body:JSON.stringify({{test:true}})
                    }}).then(function(r){{return r.status}}).catch(function(e){{return 'err:'+e.message}});
                }})()""", timeout=10)
                print(f"    status: {result}")

print("\nDONE")
