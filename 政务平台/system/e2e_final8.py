#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final8: 通过Vue数据模型直接设置cascader/select值 → 遍历步骤 → 认证检测"""
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
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    for _ in range(20):
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r.get("result",{}).get("result",{}).get("value")
        except:
            return None
    return None

def screenshot(name):
    try:
        ws.send(json.dumps({"id":9900+hash(name)%100,"method":"Page.captureScreenshot","params":{"format":"png"}}))
        for _ in range(10):
            try:
                ws.settimeout(10);r=json.loads(ws.recv())
                if r.get("id",0)>=9900:
                    d=r.get("result",{}).get("data","")
                    if d:
                        p=os.path.join(os.path.dirname(__file__),"..","data",f"e2e_{name}.png")
                        with open(p,"wb") as f:f.write(base64.b64decode(d))
                        print(f"  📸 {p}")
                    break
            except:break
    except:pass

# ===== STEP 1: 恢复token =====
print("STEP 1: 恢复token")
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")

diag = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  hash={diag.get('hash')} forms={diag.get('formCount',0)}")

# ===== STEP 2: 找到表单Vue组件并分析数据模型 =====
print("\nSTEP 2: 分析表单Vue组件数据模型")
comp = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        var m=matched[i];
        if(m.instances?.default){
            var inst2=m.instances.default;
            // 找有表单数据的组件
            if(inst2.$data?.form||inst2.$data?.baseForm||inst2.$data?.entForm){
                inst=inst2;break;
            }
        }
    }
    if(!inst){
        // 递归查找子组件
        function findFormComp(vm,depth){
            if(depth>5)return null;
            if(vm.$data?.form||vm.$data?.baseForm||vm.$data?.entForm)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){
                var r=findFormComp(children[i],depth+1);
                if(r)return r;
            }
            return null;
        }
        inst=findFormComp(vm,0);
    }
    if(!inst)return{error:'no_form_component'};
    
    // 获取$data的keys
    var dataKeys=Object.keys(inst.$data||{});
    var formKeys=[];
    if(inst.$data?.form)formKeys=Object.keys(inst.$data.form);
    
    // 获取cascader相关的字段
    var cascaderFields=[];
    var cas=document.querySelectorAll('.el-cascader');
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var prop=fi?.getAttribute('prop')||'';
        // 找cascader绑定的prop
        var vueComp=cas[i].__vue__;
        var valueKey='';
        if(vueComp){
            var vModel=vueComp.$attrs?.['v-model']||vueComp.$vnode?.data?.model?.expression||'';
            valueKey=vModel;
        }
        cascaderFields.push({label:label,prop:prop,valueKey:valueKey});
    }
    
    return{
        compName:inst.$options?.name||'unknown',
        dataKeys:dataKeys.slice(0,20),
        formKeys:formKeys.slice(0,30),
        cascaderFields:cascaderFields,
        hasForm:!!inst.$data?.form,
        formSample:JSON.stringify(inst.$data?.form||{}).substring(0,300)
    };
})()""")
print(f"  compName: {comp.get('compName','')}")
print(f"  dataKeys: {comp.get('dataKeys',[])}")
print(f"  formKeys: {comp.get('formKeys',[])}")
print(f"  cascaderFields: {comp.get('cascaderFields',[])}")
print(f"  formSample: {comp.get('formSample','')[:200]}")

# ===== STEP 3: 直接通过Vue数据模型设置cascader值 =====
print("\nSTEP 3: 通过Vue数据模型设置cascader值")
set_result = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    
    // 递归找表单组件
    function findFormComp(vm,depth){
        if(depth>8)return null;
        if(vm.$data?.form||vm.$data?.baseForm||vm.$data?.entForm)return vm;
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){
            var r=findFormComp(children[i],depth+1);
            if(r)return r;
        }
        return null;
    }
    var inst=findFormComp(vm,0);
    if(!inst)return{error:'no_form_component'};
    
    var form=inst.$data?.form||inst.$data?.baseForm||inst.$data?.entForm;
    if(!form)return{error:'no_form_data'};
    
    var results=[];
    
    // 查找cascader绑定的prop
    var cas=document.querySelectorAll('.el-cascader');
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        
        // 从el-form-item获取prop
        var prop='';
        // 遍历form的keys找地址相关字段
        for(var k in form){
            var v=form[k];
            if(label.includes('住所')||label.includes('地址')){
                if(k.includes('address')||k.includes('addr')||k.includes('domicile')||k.includes('location')||k.includes('area')||k.includes('region')||k.includes('place')){
                    // 这是地址字段，设置级联值
                    // 先获取cascader的options来找到正确的值
                    var cascaderComp=cas[i].__vue__;
                    var options=cascaderComp?.options||[];
                    
                    // 找广西
                    var guangxiCode=null;
                    for(var j=0;j<options.length;j++){
                        if(options[j].label?.includes('广西')){
                            guangxiCode=options[j].value;
                            // 找南宁
                            var nanningCode=null;
                            var children=options[j].children||[];
                            for(var m=0;m<children.length;m++){
                                if(children[m].label?.includes('南宁')){
                                    nanningCode=children[m].value;
                                    // 找青秀区
                                    var qingxiuCode=null;
                                    var district=children[m].children||[];
                                    for(var n=0;n<district.length;n++){
                                        if(district[n].label?.includes('青秀')){
                                            qingxiuCode=district[n].value;
                                            break;
                                        }
                                    }
                                    if(!qingxiuCode&&district.length>0)qingxiuCode=district[0].value;
                                    
                                    if(qingxiuCode){
                                        form[k]=[guangxiCode,nanningCode,qingxiuCode];
                                        results.push({field:k,label:label,value:[guangxiCode,nanningCode,qingxiuCode],set:'direct'});
                                    }
                                    break;
                                }
                            }
                            // 如果没找到南宁，用第一个子项
                            if(!nanningCode&&children.length>0){
                                nanningCode=children[0].value;
                                form[k]=[guangxiCode,nanningCode];
                                results.push({field:k,label:label,value:[guangxiCode,nanningCode],set:'partial'});
                            }
                            break;
                        }
                    }
                    break; // 找到匹配字段就停止
                }
            }
        }
    }
    
    inst.$forceUpdate();
    return{results:results,formKeys:Object.keys(form).filter(function(k){return k.includes('addr')||k.includes('address')||k.includes('domicile')||k.includes('area')||k.includes('region')||k.includes('place')})};
})()""")
print(f"  set_result: {set_result}")

# ===== STEP 4: 如果直接设置失败，尝试通过el-cascader组件方法 =====
if not set_result or not set_result.get('results'):
    print("\nSTEP 3b: 通过el-cascader组件方法设置")
    set2 = ev("""(function(){
        var cas=document.querySelectorAll('.el-cascader');
        var results=[];
        for(var i=0;i<cas.length;i++){
            var fi=cas[i].closest('.el-form-item');
            var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
            var required=fi?.className?.includes('is-required')||false;
            if(!required)continue;
            
            var cascaderComp=cas[i].__vue__;
            if(!cascaderComp)continue;
            
            // 获取options
            var options=cascaderComp.options||cascaderComp.mergedOptions||[];
            if(options.length===0){
                // 尝试从props获取
                var props=cascaderComp.$props||{};
                options=props.options||[];
            }
            
            // 找广西
            for(var j=0;j<options.length;j++){
                if(options[j].label?.includes('广西')){
                    var guangxi=options[j];
                    var children1=guangxi.children||[];
                    if(children1.length>0){
                        // 找南宁
                        var nanning=null;
                        for(var m=0;m<children1.length;m++){
                            if(children1[m].label?.includes('南宁')){nanning=children1[m];break}
                        }
                        if(!nanning)nanning=children1[0];
                        
                        var children2=nanning.children||[];
                        var district=children2.length>0?children2[0]:null;
                        // 找青秀区
                        for(var n=0;n<children2.length;n++){
                            if(children2[n].label?.includes('青秀')){district=children2[n];break}
                        }
                        
                        var value=[guangxi.value];
                        if(nanning)value.push(nanning.value);
                        if(district)value.push(district.value);
                        
                        // 直接设置cascader的presentValue
                        try{
                            cascaderComp.handleValueChange(value);
                            cascaderComp.$emit('input',value);
                            cascaderComp.$emit('change',value);
                            results.push({label:label,value:value,method:'handleValueChange'});
                        }catch(e){
                            try{
                                cascaderComp.presentValue=value;
                                cascaderComp.$forceUpdate();
                                results.push({label:label,value:value,method:'presentValue',error:e.message});
                            }catch(e2){
                                results.push({label:label,error:e2.message});
                            }
                        }
                    }
                    break;
                }
            }
        }
        return results;
    })()""")
    print(f"  set2: {set2}")

# ===== STEP 5: 处理select下拉框 =====
print("\nSTEP 4: 处理select下拉框")
selects = ev("""(function(){
    var sels=document.querySelectorAll('.el-select');
    var r=[];
    for(var i=0;i<sels.length;i++){
        var fi=sels[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=sels[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        var required=fi?.className?.includes('is-required')||false;
        var selComp=sels[i].__vue__;
        var options=selComp?.options||selComp?.mergedOptions||[];
        var optionLabels=options.slice(0,3).map(function(o){return o.label||o.currentLabel||''});
        if(!val&&required)r.push({i:i,label:label,options:optionLabels,optionCount:options.length});
    }
    return r;
})()""")
print(f"  required selects: {selects}")

# 对每个required select选择第一个选项
for sel in (selects or []):
    idx = sel.get('i',0)
    print(f"  处理 select #{idx}: {sel.get('label','')} (options: {sel.get('options',[])})")
    # 通过Vue组件方法选择
    ev(f"""(function(){{
        var sels=document.querySelectorAll('.el-select');
        var selComp=sels[{idx}]?.__vue__;
        if(!selComp)return;
        var options=selComp.options||selComp.mergedOptions||[];
        if(options.length>0){{
            var opt=options[0];
            var val=opt.value||opt.currentValue||opt.currentKey||'';
            selComp.handleOptionSelect(opt);
            selComp.$emit('input',val);
            selComp.$emit('change',val);
        }}
    }})()""")
    time.sleep(1)

# ===== STEP 6: 填写text input =====
print("\nSTEP 5: 填写text input")
MATERIALS = {
    "企业名称":"广西智信数据科技有限公司","注册资本":"100",
    "详细地址":"民族大道166号","生产经营地详细地址":"民族大道166号",
    "联系电话":"13877151234","邮政编码":"530028","从业人数":"5",
}

for kw,val in MATERIALS.items():
    r=ev(f"""(function(){{
        var kw='{kw}',val='{val}';
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){{
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes(kw)){{
                var input=fi[i].querySelector('.el-input__inner,.el-textarea__inner');
                if(input&&!input.disabled){{
                    var setter=Object.getOwnPropertyDescriptor(window[input.tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                    setter.call(input,val);input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));
                    return{{ok:true,label:label.textContent.trim()}};
                }}
            }}
        }}
        return{{ok:false}};
    }})()""")
    if r and r.get('ok'): print(f"  ✅ {kw}")
    else: print(f"  ❌ {kw}")

screenshot("step5_all_filled")

# ===== STEP 7: 点击保存并下一步 =====
print("\nSTEP 6: 保存并下一步")
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){
            btns[i].click();return;
        }
    }
})()""")
time.sleep(5)

# 检查
errs = ev("""(function(){
    var msgs=document.querySelectorAll('.el-form-item__error,.el-message');
    var r=[];
    for(var i=0;i<msgs.length;i++){
        var t=msgs[i].textContent?.trim()||'';
        if(t&&t.length<80&&t.length>2)r.push(t);
    }
    return r.slice(0,10);
})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")

if errs:
    print(f"  ⚠️ 验证错误: {errs}")
    log("120.验证错误", {"errors":errs})
    
    # 尝试通过API获取地址编码
    print("  尝试API获取地址编码...")
    addr = ev("""(function(){
        var t=localStorage.getItem('top-token')||'';
        var xhr=new XMLHttpRequest();
        // 获取省市区编码
        xhr.open('GET','/icpsp-api/v4/pc/common/tools/getAreaList?parentCode=450000',false);
        xhr.setRequestHeader('top-token',t);
        try{xhr.send()}catch(e){return{error:e.message}}
        if(xhr.status===200){
            var resp=JSON.parse(xhr.responseText);
            return{status:xhr.status,data:resp.data?.busiData?.slice(0,5)?.map(function(d){return{code:d.code||d.areaCode||d.id,name:d.name||d.areaName}})||[]};
        }
        return{status:xhr.status};
    })()""")
    print(f"  地址API: {addr}")
    
    # 如果有地址数据，直接设置表单
    if addr and addr.get('data'):
        ev("""(function(){
            var app=document.getElementById('app');
            var vm=app?.__vue__;
            function findFormComp(vm,depth){
                if(depth>8)return null;
                if(vm.$data?.form||vm.$data?.baseForm||vm.$data?.entForm)return vm;
                var children=vm.$children||[];
                for(var i=0;i<children.length;i++){var r=findFormComp(children[i],depth+1);if(r)return r}
                return null;
            }
            var inst=findFormComp(vm,0);
            if(!inst)return;
            var form=inst.$data?.form||inst.$data?.baseForm||inst.$data?.entForm;
            if(!form)return;
            
            // 设置地址字段 - 450000=广西 450100=南宁 450103=青秀区
            for(var k in form){
                var label='';
                // 找对应的label
                var fi=document.querySelectorAll('.el-form-item');
                for(var i=0;i<fi.length;i++){
                    var fiLabel=fi[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                    var prop=fi[i].getAttribute('prop')||'';
                    if(prop===k)label=fiLabel;
                }
                
                if(label.includes('住所')||label.includes('地址')){
                    if(Array.isArray(form[k])){
                        form[k]=['450000','450100','450103'];
                    }else if(typeof form[k]==='string'){
                        form[k]='450103';
                    }else if(typeof form[k]==='object'&&form[k]!==null){
                        // 可能是对象格式
                        form[k].province='450000';
                        form[k].city='450100';
                        form[k].district='450103';
                    }
                }
            }
            inst.$forceUpdate();
        })()""")
        time.sleep(2)
        
        # 再次点击保存并下一步
        ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){
                    btns[i].click();return;
                }
            }
        })()""")
        time.sleep(5)
        
        errs2 = ev("""(function(){
            var msgs=document.querySelectorAll('.el-form-item__error,.el-message');
            var r=[];
            for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}
            return r.slice(0,5);
        })()""")
        page2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  第二次: errors={errs2} hash={page2.get('hash')} forms={page2.get('formCount',0)}")
        
        if errs2:
            print(f"  ⚠️ 仍有验证错误")

else:
    print(f"  ✅ 无验证错误！hash={page.get('hash')} forms={page.get('formCount',0)}")

# ===== STEP 8: 遍历步骤直到提交页 =====
print("\nSTEP 7: 遍历步骤直到提交页（不点提交）")
for step in range(12):
    current = ev("""(function(){
        var steps=document.querySelectorAll('.el-step');
        var active=null;
        for(var i=0;i<steps.length;i++){
            if(steps[i].className?.includes('is-active')){
                active={i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||''};break;
            }
        }
        var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20});
        var hasSubmit=btns.some(function(t){return t.includes('提交')&&!t.includes('暂存')});
        return{step:active,hasSubmit:hasSubmit,
        buttons:btns.filter(function(t){return t.includes('下一步')||t.includes('提交')||t.includes('保存')||t.includes('暂存')||t.includes('预览')}).slice(0,5),
        formCount:document.querySelectorAll('.el-form-item').length,
        hash:location.hash};
    })()""")
    
    step_info = current.get('step') or {}
    print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)} hash={current.get('hash','')[:30]}")
    print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
    
    auth=ev("""(function(){
        var t=document.body.innerText||'';var html=document.body.innerHTML||'';
        return{faceAuth:t.includes('人脸')||html.includes('faceAuth'),smsAuth:t.includes('验证码')||t.includes('短信'),
        realName:t.includes('实名认证')||t.includes('实名'),signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),
        digitalCert:t.includes('数字证书')||t.includes('CA锁'),caAuth:t.includes('CA认证')||html.includes('caAuth'),
        ukeyAuth:t.includes('UKey')||t.includes('U盾')};
    })()""")
    if any(auth.values() if auth else []):
        print(f"  ⚠️ 认证要求: {auth}")
        add_auth_finding({"step":step,"title":step_info.get('title',''),"auth":auth})
    
    if current.get('hasSubmit'):
        print(f"\n  🔴 检测到提交按钮！停止（不点击提交）")
        log("121.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
        screenshot("step7_submit_page")
        break
    
    clicked = False
    for btn_text in ['保存并下一步','保存至下一步','下一步']:
        click_result = ev(f"""(function(){{
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){{
                if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{
                    btns[i].click();return{{clicked:true}};
                }}
            }}
            return{{clicked:false}};
        }})()""")
        if click_result and click_result.get('clicked'):
            print(f"  ✅ 点击: {btn_text}")
            clicked = True
            break
    
    if not clicked:
        print(f"  ⚠️ 无可点击按钮，停止")
        break
    
    time.sleep(5)
    
    # 检查是否前进到新步骤
    new_hash = ev("location.hash")
    new_forms = ev("document.querySelectorAll('.el-form-item').length")
    
    # 检查错误
    errs = ev("""(function(){
        var msgs=document.querySelectorAll('.el-form-item__error,.el-message');
        var r=[];
        for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}
        return r.slice(0,5);
    })()""")
    if errs:
        print(f"  ⚠️ 错误: {errs}")
        # 如果hash没变，验证阻止了前进
        if new_hash == current.get('hash'):
            print(f"  验证阻止前进，停止遍历")
            log("121b.验证阻止", {"errors":errs,"hash":new_hash})
            break

screenshot("step7_final")

# ===== 最终报告 =====
print("\n" + "=" * 60)
print("E2E 测试总结")
print("=" * 60)
rpt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "e2e_report.json")
if os.path.exists(rpt_path):
    with open(rpt_path, "r", encoding="utf-8") as f:
        rpt = json.load(f)
    print(f"  总步骤数: {len(rpt.get('steps',[]))}")
    print(f"  认证发现: {len(rpt.get('auth_findings',[]))}")
    print(f"  问题数: {len(rpt.get('issues',[]))}")
    for af in rpt.get('auth_findings',[]):
        print(f"  🔐 {af}")
    log("122.E2E测试完成", {"totalSteps":len(rpt.get('steps',[])),"authFindings":len(rpt.get('auth_findings',[])),"issues":len(rpt.get('issues',[]))})
else:
    print("  无报告文件")

ws.close()
print("\n✅ e2e_final8.py 完成")
