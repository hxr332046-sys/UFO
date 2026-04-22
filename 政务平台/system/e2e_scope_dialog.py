#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找到经营范围对话框的正确触发方式 + busiAreaData格式"""
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
# Step 1: 分析businese-info的$refs和子组件
# ============================================================
print("Step 1: businese-info $refs和子组件")
refs_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    
    var refs=Object.keys(comp.$refs||{});
    var children=[];
    for(var i=0;i<(comp.$children||[]).length;i++){
        var c=comp.$children[i];
        children.push({name:c.$options?.name||'',dataKeys:Object.keys(c.$data||{}).slice(0,10),methods:Object.keys(c.$options?.methods||{}).slice(0,10)});
    }
    
    return{refs:refs,children:children};
})()""")
print(f"  refs: {refs_info.get('refs',[]) if isinstance(refs_info,dict) else refs_info}")
if isinstance(refs_info,dict) and refs_info.get('children'):
    for c in refs_info['children']:
        print(f"  child: {c.get('name','')} keys={c.get('dataKeys',[])} methods={c.get('methods',[])}")

# ============================================================
# Step 2: 找"添加规范经营用语"按钮的Vue组件和事件
# ============================================================
print("\nStep 2: 添加按钮分析")
btn_info = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){
            var comp=btns[i].__vue__;
            if(!comp)return{text:t,htmlBtn:true};
            return{
                text:t,
                compName:comp.$options?.name||'',
                compMethods:Object.keys(comp.$options?.methods||{}),
                click:comp.$listeners?.click?'has_click':'no_click',
                parentName:comp.$parent?.$options?.name||'',
                events:Object.keys(comp.$listeners||{})
            };
        }
    }
})()""")
print(f"  按钮: {btn_info}")

# ============================================================
# Step 3: 找scope-dialog或类似组件
# ============================================================
print("\nStep 3: 搜索scope相关组件")
scope_comps = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findAll(vm,d,path){
        if(d>15)return[];
        var result=[];
        var name=vm.$options?.name||'';
        if(name.toLowerCase().includes('scope')||name.toLowerCase().includes('dialog')||
           name.toLowerCase().includes('business')||name.toLowerCase().includes('area')||
           name==='tne-dialog'||name==='tni-dialog'){
            var dataKeys=Object.keys(vm.$data||{}).slice(0,8);
            var methodNames=Object.keys(vm.$options?.methods||{});
            var refKeys=Object.keys(vm.$refs||{});
            result.push({name:name,path:path,dataKeys:dataKeys,methods:methodNames.slice(0,8),refs:refKeys,visible:vm.$el?.offsetParent!==null});
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            result=result.concat(findAll(vm.$children[i],d+1,path+'/'+i));
        }
        return result;
    }
    return findAll(vm,0,'root');
})()""")
print(f"  scope相关组件: {len(scope_comps) if isinstance(scope_comps,list) else 0}")
if isinstance(scope_comps,list):
    for c in scope_comps[:10]:
        print(f"    {c.get('name','')} path={c.get('path','')} visible={c.get('visible')} refs={c.get('refs',[])} methods={c.get('methods',[])}")

# ============================================================
# Step 4: 找tne-dialog组件并分析其内容
# ============================================================
print("\nStep 4: tne-dialog组件分析")
tne_dlg = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tne-dialog',0);
    if(!comp)return{error:'no_tne_dialog'};
    
    var dataKeys=Object.keys(comp.$data||{});
    var props=Object.keys(comp.$props||{});
    var methods=Object.keys(comp.$options?.methods||{});
    var children=[];
    for(var i=0;i<(comp.$children||[]).length;i++){
        var c=comp.$children[i];
        children.push({name:c.$options?.name||'',dataKeys:Object.keys(c.$data||{}).slice(0,8)});
    }
    var refs=Object.keys(comp.$refs||{});
    
    return{dataKeys:dataKeys,props:props,methods:methods,children:children,refs:refs};
})()""")
print(f"  tne-dialog: {tne_dlg}")

# ============================================================
# Step 5: 查看businese-info的模板中对话框相关部分
# ============================================================
print("\nStep 5: businese-info模板分析(对话框部分)")
template_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    
    // 获取render函数或template
    var render=comp.$options?.render?.toString()?.substring(0,500)||'';
    var staticRenderFns=comp.$options?.staticRenderFns?.length||0;
    
    // 获取$scopedSlots
    var slots=Object.keys(comp.$scopedSlots||{});
    
    // 获取component options中的components
    var components=Object.keys(comp.$options?.components||{});
    
    return{render:render,staticRenderFns:staticRenderFns,slots:slots,components:components};
})()""")
print(f"  components: {template_info.get('components',[]) if isinstance(template_info,dict) else template_info}")
print(f"  slots: {template_info.get('slots',[]) if isinstance(template_info,dict) else ''}")

# ============================================================
# Step 6: 尝试通过businese-info的$refs找到对话框
# ============================================================
print("\nStep 6: 通过$refs找对话框")
if isinstance(refs_info, dict) and refs_info.get('refs'):
    for refName in refs_info['refs']:
        ref_info = ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){{
                if(d>15)return null;
                if(vm.$options?.name===name)return vm;
                for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
                return null;
            }}
            var comp=findComp(vm,'businese-info',0);
            if(!comp)return'no_comp';
            var ref=comp.$refs['{refName}'];
            if(!ref)return'no_ref';
            if(Array.isArray(ref))ref=ref[0];
            var isVue=!!ref.__vue__;
            var name=isVue?ref.__vue__?.$options?.name||'':'';
            var tag=ref.tagName||'';
            return{{refName:'{refName}',isVue:isVue,name:name,tag:tag,elCount:ref.querySelectorAll?.('*')?.length||0}};
        }})()""")
        print(f"  $refs.{refName}: {ref_info}")

# ============================================================
# Step 7: 模拟confirm回调，注入正确格式的busiAreaData
# ============================================================
print("\nStep 7: 模拟confirm回调注入busiAreaData")

# 从handleDelBusinessRange可以看到item有stateCo属性
# 从confirm可以看到e有busiAreaData, genBusiArea, busiAreaCode, busiAreaName
# 尝试构造正确的数据格式

confirm_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    
    // 构造confirm回调数据 - 参考真实格式
    var confirmData={
        busiAreaData:[
            {name:'软件开发',code:'6511',industryCode:'I6511',stateCo:3,sort:1,isMain:true},
            {name:'信息技术咨询服务',code:'6560',industryCode:'I6560',stateCo:1,sort:2,isMain:false},
            {name:'数据处理和存储支持服务',code:'6550',industryCode:'I6550',stateCo:1,sort:3,isMain:false}
        ],
        genBusiArea:'软件开发;信息技术咨询服务;数据处理和存储支持服务',
        busiAreaCode:'I65',
        busiAreaName:'软件开发;信息技术咨询服务;数据处理和存储支持服务'
    };
    
    // 调用confirm方法
    comp.confirm(confirmData);
    
    return{
        busiAreaDataLen:comp.busineseForm.busiAreaData?.length||0,
        genBusiArea:comp.busineseForm.genBusiArea?.substring(0,30)||'',
        busiAreaCode:comp.busineseForm.busiAreaCode||'',
        busiAreaName:comp.busineseForm.busiAreaName?.substring(0,30)||''
    };
})()""")
print(f"  confirm结果: {confirm_result}")

# ============================================================
# Step 8: 保存并验证
# ============================================================
print("\nStep 8: 保存验证")

# 拦截API
ev("""(function(){
    window.__save_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_resp={url:url,status:self.status,resp:self.responseText?.substring(0,500)||''};
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

resp = ev("window.__save_resp")
if resp:
    print(f"  API: {resp.get('url','')[:50]} status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            print(f"  code={p.get('code','')} msg={p.get('msg','')[:50]}")
        except:
            print(f"  raw: {r[:100]}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
