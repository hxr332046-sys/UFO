#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用正确的searchList格式设置busiAreaData"""
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
# Step 1: 获取searchList中所有软件/信息技术相关项的完整数据
# ============================================================
print("Step 1: 获取searchList完整数据")
search_data = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    var sl=comp.searchList||comp.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){
        var name=sl[i].name||'';
        if(name.includes('软件开发')||name.includes('信息技术咨询')||name.includes('数据处理')){
            items.push(JSON.parse(JSON.stringify(sl[i])));
        }
    }
    return{total:sl.length,matched:items};
})()""", timeout=12)
print(f"  searchList total={search_data.get('total',0) if isinstance(search_data,dict) else 0}")
if isinstance(search_data, dict):
    for item in search_data.get('matched', []):
        print(f"  匹配项: {json.dumps(item, ensure_ascii=False)[:150]}")

# ============================================================
# Step 2: 用正确的格式调用confirm
# ============================================================
print("\nStep 2: 用正确格式调用confirm")

# 先获取完整的searchList项数据（包含所有字段）
full_items = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    var sl=comp.searchList||comp.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){
        var name=sl[i].name||'';
        if(name==='软件开发'||name.includes('信息技术咨询')||name.includes('数据处理和存储')){
            items.push(JSON.parse(JSON.stringify(sl[i])));
        }
    }
    return items;
})()""", timeout=12)

if not isinstance(full_items, list) or len(full_items) == 0:
    print("  ❌ 未找到匹配项，尝试搜索")
    # 触发搜索
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        var si=comp.$refs?.searchInput;
        if(si){
            var input=si.$el?.querySelector('input')||si;
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(input,'软件开发');
            input.dispatchEvent(new Event('input',{bubbles:true}));
        }
    })()""")
    time.sleep(3)
    full_items = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        var sl=comp.searchList||comp.$data?.searchList||[];
        var items=[];
        for(var i=0;i<sl.length;i++){
            var name=sl[i].name||'';
            if(name==='软件开发'||name.includes('信息技术咨询')||name.includes('数据处理和存储')){
                items.push(JSON.parse(JSON.stringify(sl[i])));
            }
        }
        return items;
    })()""", timeout=12)

print(f"  找到{len(full_items) if isinstance(full_items,list) else 0}项")
if isinstance(full_items, list):
    for item in full_items:
        print(f"    {json.dumps(item, ensure_ascii=False)[:120]}")

# 用找到的数据调用confirm
if isinstance(full_items, list) and len(full_items) > 0:
    # 设置第一项为主营
    confirm_items = []
    for i, item in enumerate(full_items):
        item_copy = dict(item)
        if i == 0:
            item_copy['isMainIndustry'] = '1'
            item_copy['stateCo'] = '3'  # 主营
        confirm_items.append(item_copy)
    
    # 构造confirm数据
    names = ';'.join([it.get('name','') for it in confirm_items])
    confirm_data = {
        'busiAreaData': confirm_items,
        'genBusiArea': names,
        'busiAreaCode': 'I65',
        'busiAreaName': names
    }
    
    # 注入到页面
    ev(f"""(function(){{
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){{
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }}
        var comp=findComp(vm,'businese-info',0);
        if(!comp)return;
        var data={json.dumps(confirm_data, ensure_ascii=False)};
        comp.confirm(data);
    }})()""")
    
    print(f"  confirm已调用: {len(confirm_items)}项, genBusiArea={names[:40]}")

# ============================================================
# Step 3: 验证busineseForm
# ============================================================
print("\nStep 3: 验证busineseForm")
bf = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    var form=comp.busineseForm||{};
    var data=form.busiAreaData||[];
    return{
        len:data.length,
        sample:data.length>0?JSON.stringify(data[0]).substring(0,200):'empty',
        genBusiArea:form.genBusiArea?.substring(0,40)||'',
        busiAreaCode:form.busiAreaCode||'',
        busiAreaName:form.busiAreaName?.substring(0,40)||''
    };
})()""")
print(f"  busineseForm: {bf}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 4: 保存草稿
# ============================================================
print("\nStep 4: 保存草稿")

ev("""(function(){
    window.__save_resp3=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_resp3={status:self.status,resp:self.responseText?.substring(0,500)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    try{comp.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
time.sleep(5)

resp = ev("window.__save_resp3")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            print(f"  code={p.get('code','')} msg={p.get('msg','')[:60]}")
            if p.get('code') == '0' or p.get('code') == 0:
                print("  ✅ 保存成功！")
        except:
            print(f"  raw: {r[:150]}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
