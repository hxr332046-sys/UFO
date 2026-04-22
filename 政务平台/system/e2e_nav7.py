#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - select-prise → toOther() → 填写名称表单 → startSheli() → 表单"""
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
print(f"当前: hash={page.get('hash','') if page else '?'}")

if not page or 'select-prise' not in page.get('hash',''):
    print("导航到select-prise...")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(3)
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/select-prise')})()""")
    time.sleep(3)

# Step 1: 调用toOther方法
print("\nStep 1: 调用toOther()")
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    try{
        sp.toOther();
        return{called:true};
    }catch(e){
        return{error:e.message};
    }
})()""")
print(f"  result: {result}")
time.sleep(3)

# Step 2: 分析页面变化
print("\nStep 2: 分析页面变化")
page2 = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        text:(document.body?.innerText||'').substring(0,200),
        dialogVisible:!!document.querySelector('.el-dialog[style*="display: none"]')===false||!!document.querySelector('.el-dialog__wrapper:not([style*="display: none"])')
    };
})()""")
print(f"  hash={page2.get('hash','') if page2 else '?'} forms={page2.get('formCount',0) if page2 else 0}")
print(f"  text={page2.get('text','')[:80] if page2 else 'None'}")

# Step 3: 分析对话框/表单
print("\nStep 3: 分析表单")
form_analysis = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var items=[];
    for(var i=0;i<fi.length;i++){
        var lb=fi[i].querySelector('.el-form-item__label');
        var input=fi[i].querySelector('.el-input__inner,input,textarea,select');
        items.push({
            idx:i,
            label:lb?.textContent?.trim()||'',
            inputType:input?.type||input?.tagName||'',
            placeholder:input?.placeholder||'',
            value:input?.value||''
        });
    }
    return{formCount:fi.length,items:items};
})()""")
print(f"  forms: {form_analysis.get('formCount',0) if form_analysis else 0}")
for item in (form_analysis.get('items',[]) if form_analysis else []):
    print(f"    [{item.get('idx')}] {item.get('label','')} type={item.get('inputType','')} ph={item.get('placeholder','')}")

# Step 4: 填写表单
print("\nStep 4: 填写表单")
if form_analysis and form_analysis.get('formCount',0) > 0:
    for item in form_analysis.get('items',[]):
        label = item.get('label','')
        ph = item.get('placeholder','')
        idx = item.get('idx',0)
        
        val = None
        if '名称' in label or '名称' in ph or '企业' in label or '字号' in label:
            val = '广西智信数据科技有限公司'
        elif '单号' in label or '保留' in label or '通知' in label or '文号' in label or '单号' in ph:
            val = 'GX2024001'
        elif '类型' in label or '行业' in label:
            val = '信息传输、软件和信息技术服务业'
        
        if val:
            print(f"  填写 [{idx}] {label or ph}: {val}")
            ev(f"""(function(){{
                var fi=document.querySelectorAll('.el-form-item');
                var input=fi[{idx}]?.querySelector('.el-input__inner,input,textarea');
                if(input){{
                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set||function(){{}};
                    if(input.tagName==='TEXTAREA'){{
                        input.value='{val}';input.dispatchEvent(new Event('input',{{bubbles:true}}));
                    }}else{{
                        s.call(input,'{val}');input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));
                    }}
                }}
            }})()""")
    time.sleep(1)

# Step 5: 找到提交按钮并点击
print("\nStep 5: 提交")
btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    var r=[];
    for(var i=0;i<btns.length;i++){
        if(btns[i].offsetParent!==null){
            r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||'',class:(btns[i].className||'').substring(0,30)});
        }
    }
    return r;
})()""")
print(f"  按钮: {btns}")

# 点击确定/提交/下一步
for btn in (btns or []):
    t = btn.get('text','')
    if any(kw in t for kw in ['确定','确认','提交','下一步','保存']):
        idx = btn.get('idx',0)
        print(f"  点击: {t}")
        ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
        time.sleep(3)
        break

# Step 6: 检查结果
print("\nStep 6: 检查结果")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp',hash:location.hash};
    return{
        priseName:sp.$data?.priseName||sp.$data?.form?.priseName||'',
        priseNo:sp.$data?.priseNo||sp.$data?.form?.priseNo||'',
        nameId:sp.$data?.nameId||sp.$data?.form?.nameId||sp.$data?.dataInfo?.nameId||'',
        isOther:sp.$data?.isOther||false,
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length
    };
})()""")
print(f"  comp: {comp}")

# Step 7: 如果有nameId，调用startSheli
if comp and comp.get('nameId'):
    print(f"\nStep 7: 调用startSheli (nameId={comp.get('nameId')})")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.startSheli==='function')sp.startSheli();
    })()""")
    time.sleep(5)
    
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
elif comp and comp.get('isOther'):
    # 可能在"其他来源名称"表单页面
    print("\nStep 7: 在其他来源名称表单页面")
    
    # 分析当前表单
    form2 = ev("""(function(){
        var fi=document.querySelectorAll('.el-form-item');
        var items=[];
        for(var i=0;i<fi.length;i++){
            var lb=fi[i].querySelector('.el-form-item__label');
            var input=fi[i].querySelector('.el-input__inner,input,textarea,select');
            items.push({idx:i,label:lb?.textContent?.trim()||'',ph:input?.placeholder||'',val:input?.value||'',type:input?.type||input?.tagName||''});
        }
        var btns=document.querySelectorAll('button,.el-button');
        var btnTexts=[];
        for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)btnTexts.push(btns[i].textContent?.trim()?.substring(0,15)||'')}
        return{formCount:fi.length,items:items,btnTexts:btnTexts};
    })()""")
    print(f"  forms: {form2.get('formCount',0) if form2 else 0}")
    for item in (form2.get('items',[]) if form2 else []):
        print(f"    [{item.get('idx')}] {item.get('label','')} ph={item.get('ph','')} val={item.get('val','')}")
    print(f"  按钮: {form2.get('btnTexts',[]) if form2 else []}")
    
    # 填写所有空字段
    if form2 and form2.get('formCount',0) > 0:
        for item in form2.get('items',[]):
            if not item.get('val','') and item.get('label',''):
                label = item.get('label','')
                ph = item.get('ph','')
                idx = item.get('idx',0)
                val = None
                if '名称' in label: val = '广西智信数据科技有限公司'
                elif '单号' in label or '保留' in label or '通知' in label: val = 'GX2024001'
                elif '类型' in label: val = '有限责任公司'
                elif '住所' in label or '地址' in label: val = '南宁市青秀区民族大道166号'
                elif '资本' in label or '投资' in label: val = '100'
                elif '电话' in label: val = '0771-5888888'
                
                if val:
                    print(f"  填写 [{idx}] {label}: {val}")
                    ev(f"""(function(){{var fi=document.querySelectorAll('.el-form-item');var input=fi[{idx}]?.querySelector('.el-input__inner,input,textarea');if(input){{var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(input,'{val}');input.dispatchEvent(new Event('input',{{bubbles:true}}))}}}})()""")
        time.sleep(1)
        
        # 点击提交
        for btn_text in ['确定','确认','提交','保存','下一步']:
            ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{btns[i].click();return}}}}}})()""")
            time.sleep(3)
            fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            if fc and fc.get('hash','') != comp.get('hash',''):
                print(f"  页面变化: hash={fc.get('hash','')} forms={fc.get('formCount',0)}")
                break

# Step 8: 如果仍然没有nameId，尝试getData/getDataInfo
print("\nStep 8: 尝试getDataInfo")
comp3 = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    
    // 调用getData获取列表
    if(typeof sp.getData==='function'){
        try{sp.getData()}catch(e){return{error:e.message,method:'getData'}}
    }
    
    // 检查priseList
    var priseList=sp.$data?.priseList||[];
    return{
        priseListLen:priseList.length,
        firstItem:priseList.length>0?JSON.stringify(priseList[0]).substring(0,100):'',
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length
    };
})()""")
print(f"  comp3: {comp3}")

# 如果有priseList，选择第一个
if comp3 and comp3.get('priseListLen',0) > 0:
    print("  有名称列表，选择第一个...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(!sp)return;
        var priseList=sp.$data?.priseList||[];
        if(priseList.length>0){
            sp.$set(sp.$data,'nameId',priseList[0].id||priseList[0].nameId||'');
            if(typeof sp.startSheli==='function')sp.startSheli();
        }
    })()""")
    time.sleep(5)
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  result: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
log("370.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 完成")
