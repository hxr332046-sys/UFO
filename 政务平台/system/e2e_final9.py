#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final9: 深入分析cascader/select组件 → 正确设置值 → 通过验证"""
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

# 恢复token
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

# ===== STEP 1: 深入分析cascader组件 =====
print("STEP 1: 深入分析cascader组件")
cascader_info = ev("""(function(){
    var cas=document.querySelectorAll('.el-cascader');
    var r=[];
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=cas[i].__vue__;
        
        // 获取组件属性
        var info={
            idx:i,
            label:label,
            compName:comp?.$options?.name||'',
            value:comp?.value||comp?.presentValue||comp?.currentValue||null,
            props:comp?.$props?Object.keys(comp.$props):[],
            options:comp?.options?.length||0,
            config:comp?.config||null,
        };
        
        // 获取options的前3项
        if(comp?.options&&comp.options.length>0){
            info.optionsSample=comp.options.slice(0,3).map(function(o){
                return{label:o.label,value:o.value,childrenCount:o.children?.length||0};
            });
        }
        
        // 获取v-model绑定的表达式
        var vnode=comp?.$vnode;
        var model=vnode?.data?.model;
        if(model){
            info.modelExpression=model.expression||'';
            info.modelValue=model.value||null;
        }
        
        // 获取el-form-item的prop
        var formItem=fi;
        while(formItem&&!formItem.__vue__){
            formItem=formItem.parentElement;
        }
        var formItemComp=fi?.__vue__;
        if(formItemComp){
            info.formItemProp=formItemComp.prop||formItemComp.$attrs?.prop||'';
        }
        
        r.push(info);
    }
    return r;
})()""")
for c in (cascader_info or []):
    print(f"\n  cascader #{c.get('idx')}: {c.get('label','')}")
    print(f"    compName: {c.get('compName','')}")
    print(f"    value: {c.get('value')}")
    print(f"    modelExpression: {c.get('modelExpression','')}")
    print(f"    formItemProp: {c.get('formItemProp','')}")
    print(f"    options: {c.get('options',0)} sample: {c.get('optionsSample',[])}")

# ===== STEP 2: 分析select组件 =====
print("\n\nSTEP 2: 分析select组件")
select_info = ev("""(function(){
    var sels=document.querySelectorAll('.el-select');
    var r=[];
    for(var i=0;i<sels.length;i++){
        var fi=sels[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=sels[i].__vue__;
        var input=sels[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        
        var info={
            idx:i,label:label,value:val,
            compName:comp?.$options?.name||'',
            multiple:comp?.multiple||false,
            optionsCount:comp?.options?.length||comp?.cachedOptions?.length||0,
        };
        
        // 获取选项样本
        var opts=comp?.options||comp?.cachedOptions||[];
        if(opts.length>0){
            info.optionsSample=opts.slice(0,3).map(function(o){
                return{label:o.currentLabel||o.label||'',value:o.currentValue||o.value||''};
            });
        }
        
        // model expression
        var vnode=comp?.$vnode;
        var model=vnode?.data?.model;
        if(model){
            info.modelExpression=model.expression||'';
        }
        
        // form-item prop
        var formItemComp=fi?.__vue__;
        if(formItemComp){
            info.formItemProp=formItemComp.prop||formItemComp.$attrs?.prop||'';
        }
        
        r.push(info);
    }
    return r;
})()""")
for s in (select_info or []):
    print(f"  select #{s.get('idx')}: {s.get('label','')} val={s.get('value','')} prop={s.get('formItemProp','')}")
    print(f"    options({s.get('optionsCount',0)}): {s.get('optionsSample',[])}")
    print(f"    model: {s.get('modelExpression','')}")

# ===== STEP 3: 分析经营范围字段 =====
print("\nSTEP 3: 分析经营范围字段")
scope_info = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var html=fi[i].innerHTML;
            var comp=fi[i].__vue__;
            var prop=comp?.prop||'';
            // 检查是否有特殊控件
            var hasBtn=fi[i].querySelector('button,.el-button');
            var hasTag=fi[i].querySelector('.el-tag');
            var hasTable=fi[i].querySelector('table,.el-table');
            return{
                idx:i,label:label.textContent.trim(),prop:prop,
                hasButton:!!hasBtn,buttonText:hasBtn?.textContent?.trim()||'',
                hasTag:!!hasTag,hasTable:!!hasTable,
                htmlSnippet:html.substring(0,300),
                compMethods:comp?Object.keys(comp.$options?.methods||{}).slice(0,10):[]
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  经营范围: {scope_info}")

# ===== STEP 4: 找到表单数据模型并设置cascader值 =====
print("\nSTEP 4: 通过表单数据模型设置cascader值")
set_result = ev("""(function(){
    // 递归找包含表单数据的组件
    function findFormComp(vm,depth){
        if(depth>10)return null;
        var data=vm.$data||{};
        // 检查是否有表单相关数据
        for(var k in data){
            if(data[k]&&typeof data[k]==='object'&&!Array.isArray(data[k])){
                var keys=Object.keys(data[k]);
                if(keys.length>5)return{comp:vm,formKey:k,form:data[k]};
            }
        }
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){
            var r=findFormComp(children[i],depth+1);
            if(r)return r;
        }
        return null;
    }
    
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var result=findFormComp(vm,0);
    if(!result)return{error:'no_form_found'};
    
    var form=result.form;
    var formKey=result.formKey;
    
    // 列出所有包含address/area/domicile/location的字段
    var addrFields=[];
    for(var k in form){
        var v=form[k];
        var kl=k.toLowerCase();
        if(kl.includes('address')||kl.includes('addr')||kl.includes('domicile')||kl.includes('area')||kl.includes('region')||kl.includes('location')||kl.includes('place')||kl.includes('province')||kl.includes('city')||kl.includes('district')){
            addrFields.push({key:k,value:v,type:Array.isArray(v)?'array':typeof v});
        }
    }
    
    // 列出所有包含industry/type/scope的字段
    var industryFields=[];
    for(var k in form){
        var v=form[k];
        var kl=k.toLowerCase();
        if(kl.includes('industry')||kl.includes('type')||kl.includes('scope')||kl.includes('business')||kl.includes('trade')){
            industryFields.push({key:k,value:v,type:Array.isArray(v)?'array':typeof v});
        }
    }
    
    return{
        formKey:formKey,
        addrFields:addrFields,
        industryFields:industryFields,
        formKeysCount:Object.keys(form).length,
        formKeysSample:Object.keys(form).slice(0,30)
    };
})()""")
print(f"  formKey: {set_result.get('formKey','')}")
print(f"  addrFields: {set_result.get('addrFields',[])}")
print(f"  industryFields: {set_result.get('industryFields',[])}")
print(f"  formKeys({set_result.get('formKeysCount',0)}): {set_result.get('formKeysSample',[])}")

# ===== STEP 5: 获取cascader的options并找到正确的值 =====
print("\nSTEP 5: 获取cascader options")
cascader_options = ev("""(function(){
    var cas=document.querySelectorAll('.el-cascader');
    var r=[];
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=cas[i].__vue__;
        if(!comp)continue;
        
        var options=comp.options||[];
        // 找广西
        var guangxi=null;
        for(var j=0;j<options.length;j++){
            if(options[j].label?.includes('广西')){
                guangxi={value:options[j].value,label:options[j].label,childrenCount:options[j].children?.length||0};
                // 找南宁
                var children1=options[j].children||[];
                for(var m=0;m<children1.length;m++){
                    if(children1[m].label?.includes('南宁')){
                        guangxi.nanning={value:children1[m].value,label:children1[m].label,childrenCount:children1[m].children?.length||0};
                        // 找青秀区
                        var children2=children1[m].children||[];
                        for(var n=0;n<children2.length;n++){
                            if(children2[n].label?.includes('青秀')){
                                guangxi.qingxiu={value:children2[n].value,label:children2[n].label};
                                break;
                            }
                        }
                        if(!guangxi.qingxiu&&children2.length>0){
                            guangxi.qingxiu={value:children2[0].value,label:children2[0].label};
                        }
                        break;
                    }
                }
                break;
            }
        }
        r.push({idx:i,label:label,guangxi:guangxi});
    }
    return r;
})()""")
for co in (cascader_options or []):
    print(f"  cascader #{co.get('idx')}: {co.get('label','')}")
    gx = co.get('guangxi') or {}
    print(f"    广西: value={gx.get('value')} label={gx.get('label')}")
    nn = gx.get('nanning') or {}
    print(f"    南宁: value={nn.get('value')} label={nn.get('label')}")
    qx = gx.get('qingxiu') or {}
    print(f"    青秀: value={qx.get('value')} label={qx.get('label')}")

# ===== STEP 6: 正确设置cascader值 =====
print("\nSTEP 6: 设置cascader值")
if cascader_options:
    set_cas = ev("""(function(){
        var cas=document.querySelectorAll('.el-cascader');
        var results=[];
        for(var i=0;i<cas.length;i++){
            var fi=cas[i].closest('.el-form-item');
            var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
            var comp=cas[i].__vue__;
            if(!comp)continue;
            
            var options=comp.options||[];
            // 找广西→南宁→青秀
            for(var j=0;j<options.length;j++){
                if(options[j].label?.includes('广西')){
                    var gxVal=options[j].value;
                    var ch1=options[j].children||[];
                    for(var m=0;m<ch1.length;m++){
                        if(ch1[m].label?.includes('南宁')){
                            var nnVal=ch1[m].value;
                            var ch2=ch1[m].children||[];
                            var qxVal=null;
                            for(var n=0;n<ch2.length;n++){
                                if(ch2[n].label?.includes('青秀')){qxVal=ch2[n].value;break}
                            }
                            if(!qxVal&&ch2.length>0)qxVal=ch2[0].value;
                            
                            if(qxVal){
                                var value=[gxVal,nnVal,qxVal];
                                // 方法1: 直接设值并触发事件
                                comp.$emit('input',value);
                                comp.$emit('change',value);
                                results.push({label:label,value:value,method:'emit'});
                            }
                            break;
                        }
                    }
                    break;
                }
            }
        }
        return results;
    })()""")
    print(f"  set_cas: {set_cas}")
    time.sleep(2)

# ===== STEP 7: 设置select值 =====
print("\nSTEP 7: 设置select值")
set_sel = ev("""(function(){
    var sels=document.querySelectorAll('.el-select');
    var results=[];
    for(var i=0;i<sels.length;i++){
        var fi=sels[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=sels[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        var required=fi?.className?.includes('is-required')||false;
        if(val||!required)continue;
        
        var comp=sels[i].__vue__;
        if(!comp)continue;
        var opts=comp.options||comp.cachedOptions||[];
        if(opts.length===0)continue;
        
        // 选择第一个选项
        var opt=opts[0];
        var optVal=opt.value||opt.currentValue||opt.currentKey||'';
        var optLabel=opt.label||opt.currentLabel||'';
        
        // 通过emit设置值
        comp.$emit('input',optVal);
        comp.$emit('change',optVal);
        results.push({label:label,value:optVal,optionLabel:optLabel});
    }
    return results;
})()""")
print(f"  set_sel: {set_sel}")
time.sleep(2)

# ===== STEP 8: 处理经营范围 =====
print("\nSTEP 8: 处理经营范围")
scope_result = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            // 找"添加规范经营用语"按钮
            var btn=fi[i].querySelector('button,.el-button');
            if(btn){
                btn.click();
                return{clicked:'add_scope_btn',btnText:btn.textContent?.trim()};
            }
            // 找textarea
            var textarea=fi[i].querySelector('.el-textarea__inner');
            if(textarea){
                var setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
                setter.call(textarea,'软件开发;信息技术咨询服务;数据处理服务');
                textarea.dispatchEvent(new Event('input',{bubbles:true}));
                textarea.dispatchEvent(new Event('change',{bubbles:true}));
                return{filled:'textarea'};
            }
            return{error:'no_btn_or_textarea',html:fi[i].innerHTML.substring(0,200)};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  scope: {scope_result}")
time.sleep(2)

screenshot("step8_all_filled")

# ===== STEP 9: 保存并下一步 =====
print("\nSTEP 9: 保存并下一步")
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){
            btns[i].click();return;
        }
    }
})()""")
time.sleep(5)

errs = ev("""(function(){
    var msgs=document.querySelectorAll('.el-form-item__error,.el-message');
    var r=[];
    for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}
    return r.slice(0,10);
})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if errs:
    log("130.验证错误", {"errors":errs})
    # 如果还有错误，详细分析
    print("\n  详细分析残留错误...")
    for e in errs:
        print(f"    {e}")
else:
    print("  ✅ 验证通过！")

# ===== STEP 10: 遍历步骤直到提交页 =====
print("\nSTEP 10: 遍历步骤直到提交页（不点提交）")
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
        log("131.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
        screenshot("step10_submit_page")
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
    
    new_hash = ev("location.hash")
    new_forms = ev("document.querySelectorAll('.el-form-item').length")
    
    errs = ev("""(function(){
        var msgs=document.querySelectorAll('.el-form-item__error,.el-message');
        var r=[];
        for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}
        return r.slice(0,5);
    })()""")
    if errs:
        print(f"  ⚠️ 错误: {errs}")
        if new_hash == current.get('hash'):
            print(f"  验证阻止前进，停止")
            log("131b.验证阻止", {"errors":errs,"hash":new_hash})
            break

screenshot("step10_final")

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
    log("132.E2E测试完成", {"totalSteps":len(rpt.get('steps',[])),"authFindings":len(rpt.get('auth_findings',[])),"issues":len(rpt.get('issues',[]))})
else:
    print("  无报告文件")

ws.close()
print("\n✅ e2e_final9.py 完成")
