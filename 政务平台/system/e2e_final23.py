#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final23: 检查当前状态 → 分析验证逻辑 → 正确设值 → 前进"""
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

# ===== STEP 1: 检查当前页面状态 =====
print("STEP 1: 当前页面状态")
state = ev("""(function(){
    return{
        hash:location.hash,
        title:document.title,
        formCount:document.querySelectorAll('.el-form-item').length,
        bodyText:(document.body?.innerText||'').substring(0,200),
        hasVue:!!document.getElementById('app')?.__vue__
    };
})()""")
print(f"  state: {state}")

# 如果表单消失了，需要重新导航
if state.get('formCount',0) == 0:
    print("  表单消失，重新导航...")
    ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        if(vm&&vm.$router){
            vm.$router.push('/flow/base/basic-info');
        }
    })()""")
    time.sleep(3)
    
    state2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  state2: {state2}")
    
    if state2.get('formCount',0) == 0:
        # 可能需要完整重新导航
        print("  需要完整重新导航...")
        ev("""(function(){
            location.hash='#/flow/base/basic-info';
        })()""")
        time.sleep(5)
        state3 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  state3: {state3}")

screenshot("step1_state")

# ===== STEP 2: 深入分析验证逻辑 =====
print("\nSTEP 2: 分析验证逻辑")
# 找businese-info组件的验证方法
validation = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    
    function findComp(vm,name,depth){
        if(depth>12)return null;
        if(vm.$options?.name===name)return vm;
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){var r=findComp(children[i],name,depth+1);if(r)return r}
        return null;
    }
    
    var biComp=findComp(vm,'businese-info',0);
    if(!biComp)return{error:'no_businese_info'};
    
    // 找验证相关方法
    var methods=Object.keys(biComp.$options?.methods||{});
    var validateMethods=methods.filter(function(m){
        return m.toLowerCase().includes('valid')||m.toLowerCase().includes('check')||m.toLowerCase().includes('verify')||m.toLowerCase().includes('rule');
    });
    
    // 找保存/下一步方法
    var saveMethods=methods.filter(function(m){
        return m.toLowerCase().includes('save')||m.toLowerCase().includes('next')||m.toLowerCase().includes('submit')||m.toLowerCase().includes('step');
    });
    
    // 获取组件data
    var dataKeys=Object.keys(biComp.$data||{});
    
    // 找行业类型和经营范围在data中的值
    var industryVal=null;
    var scopeVal=null;
    for(var k in biComp.$data){
        var kl=k.toLowerCase();
        if(kl.includes('industry')||kl.includes('phmeconmy')){
            industryVal=industryVal||{};
            industryVal[k]=JSON.stringify(biComp.$data[k])?.substring(0,50);
        }
        if(kl.includes('scope')||kl.includes('area')||kl.includes('businessarea')){
            scopeVal=scopeVal||{};
            scopeVal[k]=JSON.stringify(biComp.$data[k])?.substring(0,50);
        }
    }
    
    // 检查computed
    var computed=Object.keys(biComp.$options?.computed||{});
    
    return{
        methods:methods.slice(0,30),
        validateMethods:validateMethods,
        saveMethods:saveMethods,
        dataKeys:dataKeys.slice(0,30),
        industryVal:industryVal,
        scopeVal:scopeVal,
        computed:computed.slice(0,10)
    };
})()""")
print(f"  validateMethods: {validation.get('validateMethods',[])}")
print(f"  saveMethods: {validation.get('saveMethods',[])}")
print(f"  industryVal: {validation.get('industryVal')}")
print(f"  scopeVal: {validation.get('scopeVal')}")
print(f"  dataKeys: {validation.get('dataKeys',[])}")

# ===== STEP 3: 分析save/next方法的源码 =====
print("\nSTEP 3: 分析save方法源码")
for m in (validation.get('saveMethods') or []):
    src = ev(f"""(function(){{
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        function findComp(vm,name,depth){{
            if(depth>12)return null;
            if(vm.$options?.name===name)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){{var r=findComp(children[i],name,depth+1);if(r)return r}}
            return null;
        }}
        var biComp=findComp(vm,'businese-info',0);
        if(biComp&&biComp.$options?.methods?.{m}){{
            return biComp.$options.methods.{m}.toString().substring(0,300);
        }}
        return null;
    }})()""")
    if src:
        print(f"  {m}: {src[:200]}...")

# ===== STEP 4: 找validateRules或validate方法 =====
print("\nSTEP 4: 找验证规则")
for m in (validation.get('validateMethods') or []):
    src = ev(f"""(function(){{
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        function findComp(vm,name,depth){{
            if(depth>12)return null;
            if(vm.$options?.name===name)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){{var r=findComp(children[i],name,depth+1);if(r)return r}}
            return null;
        }}
        var biComp=findComp(vm,'businese-info',0);
        if(biComp&&biComp.$options?.methods?.{m}){{
            return biComp.$options.methods.{m}.toString().substring(0,500);
        }}
        return null;
    }})()""")
    if src:
        print(f"  {m}: {src[:300]}...")

# ===== STEP 5: 找到行业类型和经营范围的正确数据字段 =====
print("\nSTEP 5: 找行业类型和经营范围的正确数据字段")
# 分析businese-info组件的data
data_analysis = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    function findComp(vm,name,depth){
        if(depth>12)return null;
        if(vm.$options?.name===name)return vm;
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){var r=findComp(children[i],name,depth+1);if(r)return r}
        return null;
    }
    var biComp=findComp(vm,'businese-info',0);
    if(!biComp)return{error:'no_comp'};
    
    // 获取所有data
    var data=biComp.$data;
    var allKeys=Object.keys(data);
    
    // 找行业类型相关
    var industryKeys=allKeys.filter(function(k){
        var kl=k.toLowerCase();
        return kl.includes('industry')||kl.includes('phmeconmy')||kl.includes('typecode')||kl.includes('typename');
    });
    var industryVals={};
    for(var i=0;i<industryKeys.length;i++){
        industryVals[industryKeys[i]]=JSON.stringify(data[industryKeys[i]])?.substring(0,80);
    }
    
    // 找经营范围相关
    var scopeKeys=allKeys.filter(function(k){
        var kl=k.toLowerCase();
        return kl.includes('scope')||kl.includes('area')||kl.includes('business');
    });
    var scopeVals={};
    for(var i=0;i<scopeKeys.length;i++){
        scopeVals[scopeKeys[i]]=JSON.stringify(data[scopeKeys[i]])?.substring(0,80);
    }
    
    // 找formRules
    var formKeys=allKeys.filter(function(k){
        return k.toLowerCase().includes('rule')||k.toLowerCase().includes('form');
    });
    var formVals={};
    for(var i=0;i<formKeys.length;i++){
        var v=data[formKeys[i]];
        formVals[formKeys[i]]={type:typeof v,isArray:Array.isArray(v),keys:typeof v==='object'&&v!==null?Object.keys(v).slice(0,10):[]};
    }
    
    return{
        industryKeys:industryKeys,industryVals:industryVals,
        scopeKeys:scopeKeys,scopeVals:scopeVals,
        formKeys:formKeys,formVals:formVals,
        allKeysCount:allKeys.length
    };
})()""")
print(f"  industry: keys={data_analysis.get('industryKeys',[])} vals={data_analysis.get('industryVals',{})}")
print(f"  scope: keys={data_analysis.get('scopeKeys',[])} vals={data_analysis.get('scopeVals',{})}")
print(f"  form: keys={data_analysis.get('formKeys',[])} vals={data_analysis.get('formVals',{})}")

# ===== STEP 6: 正确设置行业类型和经营范围 =====
print("\nSTEP 6: 正确设置行业类型和经营范围")
set_result = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    function findComp(vm,name,depth){
        if(depth>12)return null;
        if(vm.$options?.name===name)return vm;
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){var r=findComp(children[i],name,depth+1);if(r)return r}
        return null;
    }
    var biComp=findComp(vm,'businese-info',0);
    if(!biComp)return{error:'no_comp'};
    
    var results=[];
    
    // 设置行业类型 - 根据数据模型分析
    var industryFields={
        'namePreIndustryTypeCode':'I',
        'namePreIndustryTypeName':'信息传输、软件和信息技术服务业',
    };
    for(var k in industryFields){
        if(k in biComp.$data){
            biComp.$set(biComp.$data,k,industryFields[k]);
            results.push({key:k,val:industryFields[k],scope:'businese-info'});
        }
    }
    
    // 设置经营范围 - 需要找到正确的字段
    // 先检查businessArea的类型和当前值
    if('businessArea' in biComp.$data){
        var ba=biComp.$data.businessArea;
        results.push({key:'businessArea',type:typeof ba,isArray:Array.isArray(ba),currentVal:JSON.stringify(ba)?.substring(0,50)});
        
        // 如果是字符串，直接设置
        if(typeof ba==='string'||ba===null){
            biComp.$set(biComp.$data,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
            results.push({key:'businessArea',set:'string'});
        }
    }
    
    // 检查genBusiArea
    if('genBusiArea' in biComp.$data){
        var gba=biComp.$data.genBusiArea;
        results.push({key:'genBusiArea',type:typeof gba,isArray:Array.isArray(gba),currentVal:JSON.stringify(gba)?.substring(0,50)});
        if(typeof gba==='string'||gba===null){
            biComp.$set(biComp.$data,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
            results.push({key:'genBusiArea',set:'string'});
        }
    }
    
    biComp.$forceUpdate();
    return{results:results};
})()""")
print(f"  set_result: {set_result}")
time.sleep(2)

# ===== STEP 7: 也设置businessDataInfo =====
print("\nSTEP 7: 设置businessDataInfo")
ev("""(function(){
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
    if(!inst)return;
    var bdi=inst.$data.businessDataInfo;
    
    // 设置行业类型
    inst.$set(bdi,'namePreIndustryTypeCode','I');
    inst.$set(bdi,'namePreIndustryTypeName','信息传输、软件和信息技术服务业');
    
    // 设置经营范围 - 字符串格式
    inst.$set(bdi,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    inst.$set(bdi,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    inst.$set(bdi,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    
    inst.$forceUpdate();
})()""")
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
    log("270.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
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
            log("271.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    log("270.验证失败", {"errors":errs})
    
    # 分析错误来源 - 找到验证函数
    print("\n  分析验证函数...")
    val_src = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        function findComp(vm,name,depth){
            if(depth>12)return null;
            if(vm.$options?.name===name)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){var r=findComp(children[i],name,depth+1);if(r)return r}
            return null;
        }
        var biComp=findComp(vm,'businese-info',0);
        if(!biComp)return{error:'no_comp'};
        
        // 找所有包含"行业类型"或"经营范围"验证的方法
        var methods=biComp.$options?.methods||{};
        var results=[];
        for(var m in methods){
            var src=methods[m].toString();
            if(src.includes('行业类型')||src.includes('经营范围')||src.includes('industryType')||src.includes('businessArea')){
                results.push({method:m,src:src.substring(0,200)});
            }
        }
        return{count:results.length,methods:results};
    })()""")
    print(f"  validation methods: {val_src}")

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
    log("272.E2E报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final23.py 完成")
