#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final21: 分析el-form model/rules → 找行业类型数据源 → 正确设值绕过验证"""
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

# ===== STEP 1: 分析行业类型和经营范围的el-form-item =====
print("STEP 1: 分析行业类型和经营范围form-item")
form_items = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(!label)continue;
        var lt=label.textContent?.trim()||'';
        if(lt.includes('行业类型')||lt.includes('经营范围')){
            var comp=fi[i].__vue__;
            var formComp=comp?.$parent;
            // 找el-form
            var elForm=null;
            var c=comp;
            for(var d=0;d<5&&c;d++){
                if(c.$options?.name==='ElForm'||c.$el?.tagName==='FORM'||c.$el?.className?.includes('el-form')){
                    elForm=c;break;
                }
                c=c.$parent;
            }
            
            var info={
                label:lt,
                prop:comp?.prop||'',
                formModel:elForm?.model?Object.keys(elForm.model).slice(0,20):[],
                formRules:elForm?.rules?Object.keys(elForm.rules):[],
            };
            
            // 获取prop对应的rule
            if(elForm?.rules&&comp?.prop){
                var rule=elForm.rules[comp.prop];
                if(rule){
                    info.ruleType=Array.isArray(rule)?rule.map(function(r){return r.type||r.required||r.validator?'custom':'simple'}):'unknown';
                    info.required=Array.isArray(rule)?rule.some(function(r){return r.required}):!!rule.required;
                }
            }
            
            // 获取prop对应的model值
            if(elForm?.model&&comp?.prop){
                var propPath=comp.prop;
                var val=elForm.model;
                var parts=propPath.split('.');
                for(var p=0;p<parts.length&&val;p++){
                    val=val[parts[p]];
                }
                info.modelValue=JSON.stringify(val)?.substring(0,80)||'null';
            }
            
            r.push(info);
        }
    }
    return r;
})()""")
for fi in (form_items or []):
    print(f"\n  {fi.get('label','')}:")
    print(f"    prop: {fi.get('prop','')}")
    print(f"    modelValue: {fi.get('modelValue','')}")
    print(f"    required: {fi.get('required')}")
    print(f"    ruleType: {fi.get('ruleType')}")
    print(f"    formModel keys: {fi.get('formModel',[])}")
    print(f"    formRules keys: {fi.get('formRules',[])}")

# ===== STEP 2: 找行业类型select的数据源 =====
print("\nSTEP 2: 行业类型select数据源")
industry_source = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');
            var comp=sel?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 检查remote/filterable
            var isRemote=comp.remote||false;
            var isFilterable=comp.filterable||false;
            var remoteMethod=comp.remoteMethod?.name||'anonymous';
            
            // 向上找有行业类型数据的组件
            var c=comp;
            for(var d=0;d<10&&c;d++){
                var data=c.$data||{};
                // 找包含行业选项的字段
                for(var k in data){
                    var v=data[k];
                    if(Array.isArray(v)&&v.length>0){
                        var first=v[0];
                        if(first&&typeof first==='object'){
                            var fk=Object.keys(first);
                            if(fk.some(function(k2){return k2.includes('industry')||k2.includes('Industry')||fk.includes('type')||fk.includes('Type')})){
                                return{depth:d,dataKey:k,count:v.length,firstItem:JSON.stringify(first).substring(0,100),compName:c.$options?.name||''};
                            }
                        }
                    }
                }
                c=c.$parent;
            }
            
            return{isRemote:isRemote,isFilterable:isFilterable,remoteMethod:remoteMethod,optCount:comp.options?.length||0};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  industry_source: {industry_source}")

# ===== STEP 3: 找行业类型的API - 通过Vue组件的created/mounted钩子 =====
print("\nSTEP 3: 找行业类型API来源")
industry_api = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');
            var comp=sel?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 检查select的v-model绑定
            var vnode=comp.$vnode;
            var model=vnode?.data?.model;
            var modelExpr=model?.expression||'';
            
            // 检查select的$attrs
            var attrs=comp.$attrs||{};
            var attrKeys=Object.keys(attrs);
            
            // 检查select的$listeners
            var listeners=comp.$listeners||{};
            var listenerKeys=Object.keys(listeners);
            
            // 向上找包含行业类型选项列表的组件
            var c=comp.$parent;
            for(var d=0;d<8&&c;d++){
                var methods=c.$options?.methods||{};
                var methodNames=Object.keys(methods);
                var industryMethods=methodNames.filter(function(m){
                    return m.toLowerCase().includes('industry')||m.toLowerCase().includes('type')||m.toLowerCase().includes('phmeconmy');
                });
                if(industryMethods.length>0){
                    // 检查方法的源码
                    var methodSrc=methods[industryMethods[0]]?.toString()?.substring(0,200)||'';
                    return{depth:d,compName:c.$options?.name||'',industryMethods:industryMethods,methodSrc:methodSrc};
                }
                c=c.$parent;
            }
            
            return{modelExpr:modelExpr,attrKeys:attrKeys.slice(0,10),listenerKeys:listenerKeys.slice(0,10)};
        }
    }
})()""")
print(f"  industry_api: {industry_api}")

# ===== STEP 4: 如果找到行业类型方法，调用它加载选项 =====
if industry_api and industry_api.get('industryMethods'):
    print("\nSTEP 4: 调用行业类型加载方法")
    for m in industry_api.get('industryMethods',[]):
        print(f"  尝试: {m}")
        result = ev(f"""(function(){{
            var fi=document.querySelectorAll('.el-form-item');
            for(var i=0;i<fi.length;i++){{
                var label=fi[i].querySelector('.el-form-item__label');
                if(label&&label.textContent.trim().includes('行业类型')){{
                    var sel=fi[i].querySelector('.el-select');
                    var comp=sel?.__vue__;
                    var c=comp?.$parent;
                    for(var d=0;d<8&&c;d++){{
                        if(typeof c.{m}==='function'){{
                            try{{
                                c.{m}();
                                return{{called:true,method:'{m}'}};
                            }}catch(e){{
                                return{{error:e.message,method:'{m}'}};
                            }}
                        }}
                        c=c.$parent;
                    }}
                }}
            }}
        }})()""")
        print(f"    result: {result}")
        time.sleep(3)
        
        # 检查选项是否加载
        opts = ev("""(function(){
            var fi=document.querySelectorAll('.el-form-item');
            for(var i=0;i<fi.length;i++){
                var label=fi[i].querySelector('.el-form-item__label');
                if(label&&label.textContent.trim().includes('行业类型')){
                    var sel=fi[i].querySelector('.el-select');
                    var comp=sel?.__vue__;
                    var opts=comp?.options||[];
                    return{optCount:opts.length,first3:opts.slice(0,3).map(function(o){return{l:(o.currentLabel||o.label||'').substring(0,20),v:o.currentValue||o.value||'',c:o.children?.length||0}})};
                }
            }
        })()""")
        print(f"    opts: {opts}")
        
        if opts and opts.get('optCount',0) > 4:
            # 选项已加载，选择[I]
            break

# ===== STEP 5: 点击行业类型select并等待选项加载 =====
print("\nSTEP 5: 点击行业类型select等待加载")
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input){input.click();input.focus();}
        }
    }
})()""")
time.sleep(5)  # 等待更长时间让选项加载

# 检查dropdown
dropdown = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            var r=[];
            for(var j=0;j<items.length;j++){
                r.push({idx:j,text:items[j].textContent?.trim()?.substring(0,50)||'',disabled:items[j].className?.includes('disabled'),group:items[j].className?.includes('group')});
            }
            return{visible:true,count:items.length,items:r};
        }
    }
    return{visible:false};
})()""")
print(f"  dropdown: {dropdown}")

# 如果有选项，选择
if dropdown and dropdown.get('visible') and dropdown.get('count',0) > 0:
    for item in dropdown.get('items',[]):
        if not item.get('disabled') and item.get('text','') and '[I]' in item.get('text',''):
            idx = item.get('idx',0)
            print(f"  选择: {item.get('text','')[:30]}")
            ev(f"""(function(){{
                var dropdown=document.querySelector('.el-select-dropdown');
                var items=dropdown?.querySelectorAll('.el-select-dropdown__item');
                if(items[{idx}])items[{idx}].click();
            }})()""")
            time.sleep(2)
            break

# ===== STEP 6: 经营范围 - 找到正确的form model字段 =====
print("\nSTEP 6: 经营范围form model")
scope_model = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var comp=fi[i].__vue__;
            var prop=comp?.prop||'';
            
            // 找el-form
            var c=comp;
            for(var d=0;d<5&&c;d++){
                if(c.$options?.name==='ElForm'||c.$el?.className?.includes('el-form')){
                    var model=c.model||{};
                    var rules=c.rules||{};
                    
                    // 获取prop对应的model值
                    var val=model;
                    var parts=prop.split('.');
                    for(var p=0;p<parts.length&&val;p++){
                        val=val[parts[p]];
                    }
                    
                    return{
                        prop:prop,
                        modelValue:JSON.stringify(val)?.substring(0,100)||'null',
                        modelType:typeof val,
                        isArray:Array.isArray(val),
                        hasRule:!!rules[prop],
                        ruleRequired:Array.isArray(rules[prop])?rules[prop].some(function(r){return r.required}):rules[prop]?.required,
                        modelKeys:Object.keys(model).slice(0,20)
                    };
                }
                c=c.$parent;
            }
        }
    }
})()""")
print(f"  scope_model: {scope_model}")

# ===== STEP 7: 设置经营范围到正确的model路径 =====
print("\nSTEP 7: 设置经营范围")
if scope_model and scope_model.get('prop'):
    prop = scope_model.get('prop','')
    print(f"  prop: {prop}")
    
    # 设置form model中的经营范围
    set_scope = ev(f"""(function(){{
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){{
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('经营范围')){{
                var comp=fi[i].__vue__;
                var c=comp;
                for(var d=0;d<5&&c;d++){{
                    if(c.$options?.name==='ElForm'||c.$el?.className?.includes('el-form')){{
                        var model=c.model;
                        var parts='{prop}'.split('.');
                        var target=model;
                        for(var p=0;p<parts.length-1&&target;p++){{
                            target=target[parts[p]];
                        }}
                        if(target){{
                            var lastKey=parts[parts.length-1];
                            c.$set(target,lastKey,'软件开发;信息技术咨询服务;数据处理和存储支持服务');
                            c.$forceUpdate();
                            return{{set:true,prop:'{prop}',value:target[lastKey]}};
                        }}
                    }}
                    c=c.$parent;
                }}
            }}
        }}
    }})()""")
    print(f"  set_scope: {set_scope}")
    time.sleep(2)

# ===== STEP 8: 验证 =====
print("\nSTEP 8: 验证")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if not errs:
    print("  ✅ 验证通过！")
    log("250.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤
    print("\nSTEP 9: 遍历步骤到提交页")
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
            formCount:document.querySelectorAll('.el-form-item').length,hash:location.hash};
        })()""")
        step_info = current.get('step') or {}
        print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)}")
        print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
        
        auth=ev("""(function(){
            var t=document.body.innerText||'';var html=document.body.innerHTML||'';
            return{faceAuth:t.includes('人脸')||html.includes('faceAuth'),smsAuth:t.includes('验证码')||t.includes('短信'),
            realName:t.includes('实名认证')||t.includes('实名'),signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),
            digitalCert:t.includes('数字证书')||t.includes('CA锁'),caAuth:t.includes('CA认证')||html.includes('caAuth'),ukeyAuth:t.includes('UKey')||t.includes('U盾')};
        })()""")
        if any(auth.values() if auth else []):
            print(f"  ⚠️ 认证: {auth}")
            add_auth_finding({"step":step,"title":step_info.get('title',''),"auth":auth})
        
        if current.get('hasSubmit'):
            print(f"\n  🔴 提交按钮！停止")
            log("251.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
            screenshot("submit_page")
            break
        
        clicked = False
        for btn_text in ['保存并下一步','保存至下一步','下一步']:
            cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
            if cr and cr.get('clicked'):
                print(f"  ✅ {btn_text}")
                clicked = True
                break
        if not clicked: break
        time.sleep(5)
        
        errs2 = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,5)})()""")
        if errs2:
            print(f"  ⚠️ 错误: {errs2}")
            new_hash = ev("location.hash")
            if new_hash == current.get('hash'):
                print("  验证阻止")
                break
else:
    print(f"  ⚠️ 验证错误: {errs}")
    log("250.验证失败", {"errors":errs})
    
    # 尝试直接调用handleStepsNext绕过前端验证
    print("\n  尝试调用handleStepsNext...")
    next_result = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        function findBDI(vm,depth){
            if(depth>12)return null;
            if(vm.$data?.businessDataInfo)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){var r=findBDI(children[i],depth+1);if(r)return r}
            return null;
        }
        var inst=findBDI(vm,0);
        if(!inst)return{error:'no_bdi'};
        
        // 找当前步骤组件
        var currentComp=inst.$data.currentComp;
        var children=inst.$children||[];
        var stepComp=null;
        for(var i=0;i<children.length;i++){
            if(children[i].$options?.name===currentComp||children[i].$el?.className?.includes(currentComp)){
                stepComp=children[i];break;
            }
        }
        if(!stepComp){
            // 递归找
            for(var i=0;i<children.length;i++){
                if(children[i].$children){
                    for(var j=0;j<children[i].$children.length;j++){
                        if(children[i].$children[j].$options?.name===currentComp){
                            stepComp=children[i].$children[j];break;
                        }
                    }
                }
                if(stepComp)break;
            }
        }
        
        if(stepComp){
            var methods=Object.keys(stepComp.$options?.methods||{});
            var nextMethods=methods.filter(function(m){return m.includes('next')||m.includes('Next')||m.includes('save')||m.includes('Save')});
            return{compName:stepComp.$options?.name||'',methods:methods.slice(0,20),nextMethods:nextMethods};
        }
        
        return{error:'no_step_comp',currentComp:currentComp};
    })()""")
    print(f"  next_result: {next_result}")

screenshot("final_result")

# ===== 最终报告 =====
print("\n" + "=" * 60)
print("E2E 测试报告")
print("=" * 60)
rpt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "e2e_report.json")
if os.path.exists(rpt_path):
    with open(rpt_path, "r", encoding="utf-8") as f:
        rpt = json.load(f)
    auth_types = set()
    for af in rpt.get('auth_findings',[]):
        if isinstance(af, dict) and af.get('auth'):
            for k, v in af['auth'].items():
                if v: auth_types.add(k)
    print(f"  总步骤数: {len(rpt.get('steps',[]))}")
    print(f"  认证类型: {list(auth_types)}")
    log("252.E2E报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final21.py 完成")
