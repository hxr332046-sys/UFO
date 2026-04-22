#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复: 企业名称 + 经营范围正确数据结构"""
import json, time, requests, websocket

def ev(js, timeout=8):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=6)
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
# Step 1: 分析businessDataInfo完整结构
# ============================================================
print("Step 1: businessDataInfo完整字段")
bdi_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    var keys=Object.keys(bdi);
    var result={};
    for(var i=0;i<keys.length;i++){
        var k=keys[i];
        var v=bdi[k];
        if(v===null||v===undefined)result[k]='null';
        else if(Array.isArray(v))result[k]='Array['+v.length+']';
        else if(typeof v==='object')result[k]='obj:'+Object.keys(v).slice(0,3).join(',');
        else result[k]=String(v).substring(0,40);
    }
    return result;
})()""")
# 只打印含name/ent/scope/busi的
if isinstance(bdi_info, dict):
    for k,v in sorted(bdi_info.items()):
        if any(w in k.lower() for w in ['name','ent','scope','busi','area','indus','trade']):
            print(f"  {k}: {v}")

# ============================================================
# Step 2: 找企业名称字段
# ============================================================
print("\nStep 2: 企业名称字段")
name_fields = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    var fd=bdi.flowData||{};
    // 搜索所有含name的字段
    var nameKeys=[];
    for(var k in bdi){
        if(k.toLowerCase().includes('name')||k.toLowerCase().includes('entname')){
            nameKeys.push({key:k,val:String(bdi[k]).substring(0,40)});
        }
    }
    for(var k in fd){
        if(k.toLowerCase().includes('name')||k.toLowerCase().includes('entname')){
            nameKeys.push({key:'flowData.'+k,val:String(fd[k]).substring(0,40)});
        }
    }
    // 也检查DOM
    var items=document.querySelectorAll('.el-form-item');
    var domNames=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业名称')||label.includes('名称')){
            var input=items[i].querySelector('input');
            domNames.push({label:label,value:input?.value||'',prop:items[i].querySelector('.el-form-item__content')?.getAttribute('prop')||''});
        }
    }
    return{nameKeys:nameKeys,domNames:domNames};
})()""")
print(f"  name字段: {name_fields}")

# ============================================================
# Step 3: 分析经营范围数据结构（从已有成功案例或API响应）
# ============================================================
print("\nStep 3: 经营范围数据结构")

# 拦截下一次保存API，看请求体
ev("""(function(){
    window.__save_request=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')||url.includes('save')){
            window.__save_request={url:url,body:body?.substring(0,2000)||''};
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 设置企业名称
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
    var fd=bdi.flowData||{};
    
    // 设置企业名称 - 尝试所有可能的字段
    comp.$set(bdi,'entName','广西智信数据科技有限公司');
    comp.$set(bdi,'name','广西智信数据科技有限公司');
    comp.$set(bdi,'entNameCN','广西智信数据科技有限公司');
    comp.$set(bdi,'entNameEn','');
    comp.$set(bdi,'shortName','智信数据');
    if(fd){
        comp.$set(fd,'entName','广西智信数据科技有限公司');
        comp.$set(fd,'name','广西智信数据科技有限公司');
    }
    comp.$forceUpdate();
    
    // 同步DOM
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业名称')){
            var input=items[i].querySelector('input');
            if(input){
                s.call(input,'广西智信数据科技有限公司');
                input.dispatchEvent(new Event('input',{bubbles:true}));
            }
        }
    }
})()""")

# 修复经营范围 - 用更完整的数据结构
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
    
    // 经营范围数据结构 - 可能需要数组格式
    var scopeItems=[
        {name:'软件开发',code:'6511',industryCode:'I65',isMain:1,sort:1},
        {name:'信息技术咨询服务',code:'6560',industryCode:'I65',isMain:0,sort:2},
        {name:'数据处理和存储支持服务',code:'6550',industryCode:'I65',isMain:0,sort:3}
    ];
    
    comp.$set(bdi,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'busiAreaCode','I65');
    comp.$set(bdi,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'scopeList',scopeItems);
    comp.$set(bdi,'busiScopeList',scopeItems);
    comp.$set(bdi,'businessScopeList',scopeItems);
    comp.$set(bdi,'scopeData',scopeItems);
    comp.$set(bdi,'mainScope','软件开发');
    comp.$set(bdi,'mainBusiness','软件开发');
    comp.$set(bdi,'mainBusiName','软件开发');
    
    comp.$forceUpdate();
})()""")

# ============================================================
# Step 4: 再次保存
# ============================================================
print("\nStep 4: 保存")
save_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    try{
        comp.save(null,null,'working');
        return{called:'save'};
    }catch(e){
        return{error:e.message};
    }
})()""", timeout=15)
print(f"  保存: {save_result}")
time.sleep(5)

# 检查API请求体
api_req = ev("window.__save_request")
if api_req:
    print(f"  API: {api_req.get('url','')[:60]}")
    body = api_req.get('body','')
    if body:
        try:
            parsed = json.loads(body)
            # 找关键字段
            for k in ['entName','businessArea','busiAreaCode','itemIndustryTypeCode','distCode']:
                if k in parsed:
                    print(f"    {k}: {str(parsed[k])[:50]}")
            # 也检查嵌套
            if 'flowData' in parsed:
                fd = parsed['flowData']
                for k in ['entName','businessArea','busiAreaCode']:
                    if k in fd:
                        print(f"    flowData.{k}: {str(fd[k])[:50]}")
            # 保存完整body用于分析
            with open(r'g:\\UFO\\政务平台\\data\\save_request_body.json','w',encoding='utf-8') as f:
                json.dump(parsed,f,ensure_ascii=False,indent=2)
            print("    已保存请求体到 save_request_body.json")
        except:
            print(f"    body(raw): {body[:200]}")

# 检查结果
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

msg = ev("""(function(){var msgs=document.querySelectorAll('.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  消息: {msg}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
