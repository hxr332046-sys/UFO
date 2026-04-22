#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 找其他来源名称提交按钮 → 监控API获取nameId → startSheli"""
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

# 确保在select-prise
page = ev("({hash:location.hash})")
if not page or 'select-prise' not in page.get('hash',''):
    print("导航到select-prise...")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(3)
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/select-prise')})()""")
    time.sleep(3)

# Step 1: 设置isOther=true并填写表单
print("Step 1: 设置isOther并填写")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return;
    sp.$set(sp.$data,'isOther',true);
    sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');
    sp.$set(sp.$data.form,'numbers','GX2024001');
    sp.$forceUpdate();
})()""")
time.sleep(1)

# DOM填写
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
    for(var i=0;i<inputs.length;i++){
        var ph=inputs[i].placeholder||'';
        if(ph.includes('企业名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
        if(ph.includes('保留单号')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")
time.sleep(1)

# Step 2: 找所有按钮（包括isOther=true时出现的）
print("\nStep 2: 找所有按钮")
btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,[class*="btn"]');
    var r=[];
    for(var i=0;i<btns.length;i++){
        r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,25)||'',class:(btns[i].className||'').substring(0,40),visible:btns[i].offsetParent!==null,disabled:btns[i].disabled||btns[i].className?.includes('disabled')});
    }
    return r;
})()""")
for b in (btns or []):
    if b.get('visible'):
        print(f"  [{b.get('idx')}] {b.get('text','')} class={b.get('class','')} disabled={b.get('disabled')}")

# Step 3: 安装XHR拦截器
print("\nStep 3: 安装XHR拦截器")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(){
        var self=this;
        this.addEventListener('load',function(){
            window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||''});
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 找到并点击提交按钮
print("\nStep 4: 点击提交按钮")
# 找"确定"/"下一步"/"选择已有名称"按钮
# 注意："选择已有名称"可能是提交按钮
for btn_text in ['确定','确认','下一步','选择已有名称','提交','保存']:
    clicked = ev(f"""(function(){{
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){{
            if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null&&!btns[i].disabled){{
                btns[i].click();return{{clicked:true,text:'{btn_text}'}};
            }}
        }}
        return{{clicked:false}};
    }})()""")
    if clicked and clicked.get('clicked'):
        print(f"  点击: {btn_text}")
        time.sleep(3)
        break

# Step 5: 检查API调用
print("\nStep 5: 检查API调用")
api_logs = ev("window.__api_logs||[]")
for log_item in (api_logs or []):
    url = log_item.get('url','')
    if 'usermanager' not in url:  # 排除getUserInfo
        print(f"  {log_item.get('method','')} {url} status={log_item.get('status')} resp={log_item.get('response','')[:100]}")

# Step 6: 检查nameId
print("\nStep 6: 检查nameId")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    return{
        nameId:sp.$data?.nameId||'',
        form:JSON.stringify(sp.$data?.form)||'',
        dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,300)||'',
        isOther:sp.$data?.isOther||false,
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        errMsg:document.querySelector('.el-message__content,[class*="error"]')?.textContent?.trim()||''
    };
})()""")
print(f"  nameId={comp.get('nameId','') if comp else ''} isOther={comp.get('isOther') if comp else ''}")
print(f"  errMsg={comp.get('errMsg','') if comp else ''}")
print(f"  hash={comp.get('hash','') if comp else ''} forms={comp.get('formCount',0) if comp else 0}")

# Step 7: 如果没有nameId，分析getDataInfo方法
if comp and not comp.get('nameId'):
    print("\nStep 7: 分析getDataInfo")
    src = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return{error:'no_comp'};
        var methods=sp.$options?.methods||{};
        return{
            getDataInfo:methods.getDataInfo?.toString()?.substring(0,600)||'',
            getData:methods.getData?.toString()?.substring(0,400)||'',
            searchBtn:methods.searchBtn?.toString()?.substring(0,400)||''
        };
    })()""")
    print(f"  getDataInfo: {src.get('getDataInfo','')[:300] if src else ''}")
    print(f"  getData: {src.get('getData','')[:200] if src else ''}")
    print(f"  searchBtn: {src.get('searchBtn','')[:200] if src else ''}")
    
    # 调用getDataInfo
    print("\n  调用getDataInfo...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.getDataInfo==='function'){
            sp.getDataInfo();
        }
    })()""")
    time.sleep(3)
    
    api_logs2 = ev("window.__api_logs||[]")
    for log_item in (api_logs2 or []):
        url = log_item.get('url','')
        if 'usermanager' not in url and url not in [l.get('url','') for l in (api_logs or [])]:
            print(f"  NEW: {log_item.get('method','')} {url} status={log_item.get('status')} resp={log_item.get('response','')[:100]}")
    
    comp2 = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return{error:'no_comp'};
        return{nameId:sp.$data?.nameId||'',dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,300)||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
    })()""")
    print(f"  comp2: nameId={comp2.get('nameId','') if comp2 else ''} dataInfo={comp2.get('dataInfo','') if comp2 else ''}")

# Step 8: 如果有nameId，调用startSheli
nameId = ''
if comp and comp.get('nameId'): nameId = comp['nameId']
elif comp2 and comp2.get('nameId'): nameId = comp2['nameId']

if nameId:
    print(f"\nStep 8: 调用startSheli (nameId={nameId})")
    ev(f"""(function(){{
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nameId}'}});
    }})()""")
    time.sleep(5)
    
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
else:
    # Step 8b: 尝试直接通过API获取nameId
    print("\nStep 8b: 尝试API获取nameId")
    # 搜索名称相关API
    api_search = ev("""(function(){
        var t=localStorage.getItem('top-token')||'';
        var apis=[
            {url:'/icpsp-api/v4/pc/flow/namenotice/getOtherNameInfo',method:'GET',body:null},
            {url:'/icpsp-api/v4/pc/flow/namenotice/getNameList?entType=1100',method:'GET',body:null},
            {url:'/icpsp-api/v4/pc/flow/namenotice/saveOtherName',method:'POST',body:JSON.stringify({name:'广西智信数据科技有限公司',numbers:'GX2024001',entType:'1100'})},
            {url:'/icpsp-api/v4/pc/flow/name/getOtherNameInfo',method:'GET',body:null},
            {url:'/icpsp-api/v4/pc/flow/name/getNameList?entType=1100',method:'GET',body:null},
            {url:'/icpsp-api/v4/pc/flow/base/getBusinessData?entType=1100',method:'GET',body:null}
        ];
        var results=[];
        for(var i=0;i<apis.length;i++){
            var xhr=new XMLHttpRequest();
            xhr.open(apis[i].method,apis[i].url,false);
            xhr.setRequestHeader('Content-Type','application/json');
            xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
            try{
                xhr.send(apis[i].body);
                var resp=null;
                try{resp=JSON.parse(xhr.responseText)}catch(e){}
                results.push({url:apis[i].url,status:xhr.status,code:resp?.code||'',data:JSON.stringify(resp?.data)?.substring(0,150)||'',msg:resp?.msg||''});
            }catch(e){results.push({url:apis[i].url,error:e.message})}
        }
        return results;
    })()""")
    for r in (api_search or []):
        print(f"  {r.get('url','').split('/').pop()}: status={r.get('status')} code={r.get('code','')} data={r.get('data','')[:60]} msg={r.get('msg','')[:30]}")
    
    # 如果找到nameId
    for r in (api_search or []):
        if r.get('code') == '00000' and r.get('data',''):
            try:
                data = json.loads(r['data'])
                nid = data.get('nameId','') or data.get('busiData',{}).get('nameId','') if isinstance(data, dict) else ''
                if nid:
                    print(f"  找到nameId: {nid}")
                    nameId = nid
                    # 设置到组件
                    ev(f"""(function(){{
                        var app=document.getElementById('app');var vm=app?.__vue__;
                        function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                        var sp=findComp(vm,'select-prise',0);
                        if(sp){{sp.$set(sp.$data,'nameId','{nid}');if(typeof sp.startSheli==='function')sp.startSheli({{nameId:'{nid}'}})}}
                    }})()""")
                    time.sleep(5)
                    break
            except: pass

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 如果表单加载了，保存状态信息
if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    # 保存关键信息供后续脚本使用
    ev(f"""localStorage.setItem('e2e_nameId','{nameId}')""")
    log("400.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0),"nameId":nameId})
else:
    # 检查动态路由
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")
    log("400.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})

ws.close()
print("✅ 完成")
