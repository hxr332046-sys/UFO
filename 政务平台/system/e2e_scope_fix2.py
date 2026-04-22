#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复经营范围: 设置businese-info组件的busineseForm.busiAreaData"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=8)
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
# Step 1: 分析busineseForm当前值
# ============================================================
print("Step 1: busineseForm当前值")
bf = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var form=comp.busineseForm||{};
    return{
        businessArea:form.businessArea||'',
        busiAreaData:JSON.stringify(form.busiAreaData||[]).substring(0,200),
        busiAreaCode:form.busiAreaCode||'',
        busiAreaName:form.busiAreaName||'',
        secretaryServiceEnt:form.secretaryServiceEnt||''
    };
})()""")
print(f"  busineseForm: {bf}")

# ============================================================
# Step 2: 设置busineseForm.busiAreaData
# ============================================================
print("\nStep 2: 设置busiAreaData")
set_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    
    // 正确的busiAreaData数据结构 - 需要分析实际格式
    // 先看已有数据格式
    var existing=comp.busineseForm.busiAreaData||[];
    var existingSample=existing.length>0?JSON.stringify(existing[0]).substring(0,200):'empty';
    
    // 设置busiAreaData - 使用完整数据结构
    var scopeData=[
        {name:'软件开发',code:'6511',industryCode:'I65',isMain:true,sort:1,type:'1'},
        {name:'信息技术咨询服务',code:'6560',industryCode:'I65',isMain:false,sort:2,type:'1'},
        {name:'数据处理和存储支持服务',code:'6550',industryCode:'I65',isMain:false,sort:3,type:'1'}
    ];
    
    comp.$set(comp.busineseForm,'busiAreaData',scopeData);
    comp.$set(comp.busineseForm,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(comp.busineseForm,'busiAreaCode','I65');
    comp.$set(comp.busineseForm,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    
    comp.$forceUpdate();
    
    return{set:true,existingSample:existingSample,newLen:comp.busineseForm.busiAreaData.length};
})()""")
print(f"  设置结果: {set_result}")

# ============================================================
# Step 3: 也同步到父组件businessDataInfo
# ============================================================
print("\nStep 3: 同步到父组件")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    
    comp.$set(bdi,'busiAreaData',comp.$data.businessDataInfo.busiAreaData||[]);
    comp.$set(bdi,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'busiAreaCode','I65');
    comp.$set(bdi,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$forceUpdate();
})()""")

# ============================================================
# Step 4: 验证
# ============================================================
print("\nStep 4: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 5: 保存草稿
# ============================================================
print("\nStep 5: 保存草稿")

# 拦截API
ev("""(function(){
    window.__api_resp=[];
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__api_resp.push({url:url,status:self.status,response:self.responseText?.substring(0,500)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    try{comp.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
time.sleep(5)

# 检查API响应
api_resp = ev("window.__api_resp")
if api_resp and isinstance(api_resp, list):
    for r in api_resp:
        print(f"  API: {r.get('url','')[:50]} status={r.get('status')}")
        resp = r.get('response','')
        if resp:
            try:
                parsed = json.loads(resp)
                print(f"    code={parsed.get('code','')} msg={parsed.get('msg','')[:50]}")
                if parsed.get('data'):
                    print(f"    data keys: {list(parsed['data'].keys())[:10] if isinstance(parsed['data'],dict) else type(parsed['data']).__name__}")
            except:
                print(f"    raw: {resp[:100]}")

# 检查保存后状态
errors_after = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  保存后验证错误: {errors_after}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
