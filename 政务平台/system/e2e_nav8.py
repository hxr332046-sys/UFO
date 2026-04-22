#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 分析toOther源码 → 正确触发其他来源名称表单 → 提交 → 表单"""
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

# Step 1: 分析toOther源码
print("Step 1: 分析toOther源码")
src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    var methods=sp.$options?.methods||{};
    return{
        toOther:methods.toOther?.toString()?.substring(0,500)||'',
        startSheli:methods.startSheli?.toString()?.substring(0,500)||'',
        getHandleBusiness:methods.getHandleBusiness?.toString()?.substring(0,500)||'',
        validateName:methods.validateName?.toString()?.substring(0,300)||'',
        getData:methods.getData?.toString()?.substring(0,300)||'',
        getDataInfo:methods.getDataInfo?.toString()?.substring(0,300)||''
    };
})()""")
print(f"  toOther: {src.get('toOther','')[:200] if src else 'None'}")
print(f"  startSheli: {src.get('startSheli','')[:200] if src else 'None'}")
print(f"  getHandleBusiness: {src.get('getHandleBusiness','')[:200] if src else 'None'}")

# Step 2: 分析select-prise的template结构
print("\nStep 2: 分析select-prise的DOM结构")
dom = ev("""(function(){
    // 找select-prise的根元素
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    
    var el=sp.$el;
    // 找所有子组件
    var children=sp.$children||[];
    var childInfo=children.map(function(c){return{name:c.$options?.name||'',tag:c.$el?.tagName||'',class:(c.$el?.className||'').substring(0,30),visible:c.$el?.offsetParent!==null}});
    
    // 找isOther相关DOM
    var otherSection=el.querySelector('[class*="other"],[class*="Other"]');
    var otherHtml=otherSection?.outerHTML?.substring(0,200)||'';
    
    // 找v-if/v-show条件渲染的部分
    var hiddenEls=el.querySelectorAll('[style*="display: none"],[style*="display:none"]');
    var hiddenInfo=[];
    for(var i=0;i<hiddenEls.length;i++){
        hiddenInfo.push({idx:i,tag:hiddenEls[i].tagName,class:(hiddenEls[i].className||'').substring(0,30),text:hiddenEls[i].textContent?.trim()?.substring(0,30)||''});
    }
    
    return{
        childCount:children.length,
        childInfo:childInfo,
        otherHtml:otherHtml,
        hiddenCount:hiddenEls.length,
        hiddenInfo:hiddenInfo.slice(0,5),
        isOther:sp.$data?.isOther||false
    };
})()""")
print(f"  children: {dom.get('childInfo',[]) if dom else []}")
print(f"  isOther: {dom.get('isOther') if dom else '?'}")
print(f"  hidden: {dom.get('hiddenInfo',[]) if dom else []}")
print(f"  otherHtml: {dom.get('otherHtml','') if dom else ''}")

# Step 3: 手动设置isOther=true并forceUpdate
print("\nStep 3: 设置isOther=true")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return;
    sp.$set(sp.$data,'isOther',true);
    sp.$forceUpdate();
})()""")
time.sleep(2)

# Step 4: 检查表单是否出现
print("\nStep 4: 检查表单")
form = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var items=[];
    for(var i=0;i<fi.length;i++){
        var lb=fi[i].querySelector('.el-form-item__label');
        var input=fi[i].querySelector('.el-input__inner,input,textarea,select');
        items.push({idx:i,label:lb?.textContent?.trim()||'',ph:input?.placeholder||'',type:input?.type||input?.tagName||'',val:input?.value||'',visible:fi[i].offsetParent!==null});
    }
    var btns=document.querySelectorAll('button,.el-button');
    var btnTexts=[];
    for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)btnTexts.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,15)||''})}
    return{formCount:fi.length,items:items,btnTexts:btnTexts,hash:location.hash};
})()""")
print(f"  forms: {form.get('formCount',0) if form else 0}")
for item in (form.get('items',[]) if form else []):
    print(f"    [{item.get('idx')}] {item.get('label','')} ph={item.get('ph','')} vis={item.get('visible')}")
print(f"  按钮: {form.get('btnTexts',[]) if form else []}")

# Step 5: 填写表单
print("\nStep 5: 填写表单")
if form and form.get('formCount',0) > 0:
    for item in form.get('items',[]):
        label = item.get('label','')
        ph = item.get('ph','')
        idx = item.get('idx',0)
        val = None
        if '名称' in label or '名称' in ph: val = '广西智信数据科技有限公司'
        elif '单号' in label or '保留' in label or '通知' in label or '单号' in ph: val = 'GX2024001'
        elif '类型' in label: val = '有限责任公司'
        elif '住所' in label or '地址' in label: val = '南宁市青秀区民族大道166号'
        elif '资本' in label: val = '100'
        elif '电话' in label: val = '0771-5888888'
        
        if val and not item.get('val',''):
            print(f"  填写 [{idx}] {label or ph}: {val}")
            ev(f"""(function(){{
                var fi=document.querySelectorAll('.el-form-item');
                var input=fi[{idx}]?.querySelector('.el-input__inner,input,textarea');
                if(input){{
                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    s.call(input,'{val}');input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));
                }}
            }})()""")
    time.sleep(1)
    
    # 点击确定/提交
    for btn in (form.get('btnTexts',[]) if form else []):
        t = btn.get('text','')
        if any(kw in t for kw in ['确定','确认','提交','保存','下一步']):
            idx = btn.get('idx',0)
            print(f"  点击: {t}")
            ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
            time.sleep(3)
            break

# Step 6: 检查提交结果
print("\nStep 6: 检查提交结果")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
    return{
        isOther:sp.$data?.isOther||false,
        nameId:sp.$data?.nameId||sp.$data?.form?.nameId||sp.$data?.dataInfo?.nameId||'',
        priseName:sp.$data?.priseName||sp.$data?.form?.priseName||'',
        form:JSON.stringify(sp.$data?.form)?.substring(0,200)||'',
        dataInfo:JSON.stringify(sp.$data?.dataInfo)?.substring(0,200)||'',
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length
    };
})()""")
print(f"  comp: isOther={comp.get('isOther') if comp else '?'} nameId={comp.get('nameId','') if comp else ''}")
print(f"  form: {comp.get('form','') if comp else ''}")
print(f"  dataInfo: {comp.get('dataInfo','') if comp else ''}")

# Step 7: 如果有nameId，调用startSheli
if comp and comp.get('nameId'):
    print(f"\nStep 7: 调用startSheli")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.startSheli==='function')sp.startSheli();
    })()""")
    time.sleep(5)
elif comp and comp.get('isOther'):
    # 如果仍在其他来源名称表单，尝试validateName
    print("\nStep 7: 调用validateName")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.validateName==='function'){
            try{sp.validateName()}catch(e){return{error:e.message}}
        }
    })()""")
    time.sleep(3)

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 如果表单还没加载，检查动态路由
if fc and fc.get('formCount',0) < 10:
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
        var all=findRoutes(routes,'');
        var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')||r.includes('declaration')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")
    
    # 尝试导航
    if routes.get('flow') and len(routes.get('flow',[])) > 0:
        for route in routes.get('flow',[]):
            print(f"  尝试: {route}")
            ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
            time.sleep(3)
            fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            if fc2 and fc2.get('formCount',0) > 5:
                print(f"  ✅ 找到表单: {route} forms={fc2.get('formCount',0)}")
                fc = fc2
                break

log("380.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 完成")
