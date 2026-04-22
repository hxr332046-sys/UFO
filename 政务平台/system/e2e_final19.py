#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final19: 直接通过Vue数据模型设置行业类型+经营范围 → 验证 → 遍历步骤"""
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

# ===== STEP 1: 深入分析行业类型和经营范围的Vue组件 =====
print("STEP 1: 分析行业类型和经营范围Vue组件")
field_analysis = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var r={};
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(!label)continue;
        var lt=label.textContent?.trim()||'';
        
        if(lt.includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');
            var comp=sel?.__vue__;
            // 向上遍历找有行业数据的组件
            var c=comp;
            for(var d=0;d<10&&c;d++){
                var data=c.$data||{};
                for(var k in data){
                    var v=data[k];
                    if(v&&typeof v==='object'){
                        var keys=Object.keys(v);
                        // 找包含industry的字段
                        var industryKeys=keys.filter(function(k2){return k2.toLowerCase().includes('industry')||k2.toLowerCase().includes('type')});
                        if(industryKeys.length>0){
                            r.industryComp={depth:d,compName:c.$options?.name||'',dataKey:k,industryKeys:industryKeys,values:industryKeys.map(function(k2){return{key:k2,val:JSON.stringify(v[k2]).substring(0,50)}})};
                            break;
                        }
                    }
                }
                if(r.industryComp)break;
                c=c.$parent;
            }
        }
        
        if(lt.includes('经营范围')){
            var fiComp=fi[i].__vue__;
            var c=fiComp;
            for(var d=0;d<10&&c;d++){
                var data=c.$data||{};
                for(var k in data){
                    var v=data[k];
                    if(v&&typeof v==='object'){
                        var keys=Object.keys(v);
                        var scopeKeys=keys.filter(function(k2){return k2.toLowerCase().includes('scope')||k2.toLowerCase().includes('area')||k2.toLowerCase().includes('business')});
                        if(scopeKeys.length>0){
                            r.scopeComp={depth:d,compName:c.$options?.name||'',dataKey:k,scopeKeys:scopeKeys,values:scopeKeys.map(function(k2){return{key:k2,val:JSON.stringify(v[k2]).substring(0,50)}})};
                            break;
                        }
                    }
                }
                if(r.scopeComp)break;
                c=c.$parent;
            }
        }
    }
    return r;
})()""")
print(f"  industry: {field_analysis.get('industryComp')}")
print(f"  scope: {field_analysis.get('scopeComp')}")

# ===== STEP 2: 找到businessDataInfo并分析所有字段 =====
print("\nSTEP 2: 找businessDataInfo")
bdi = ev("""(function(){
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
    var bdi=inst.$data.businessDataInfo;
    
    // 找行业和经营范围相关字段
    var allKeys=Object.keys(bdi);
    var industryKeys=allKeys.filter(function(k){var kl=k.toLowerCase();return kl.includes('industry')||kl.includes('type')||kl.includes('phmeconmy')||kl.includes('economy')});
    var scopeKeys=allKeys.filter(function(k){var kl=k.toLowerCase();return kl.includes('scope')||kl.includes('area')||kl.includes('businessarea')});
    
    return{
        compName:inst.$options?.name||'',
        industryKeys:industryKeys,
        industryValues:industryKeys.map(function(k){return{key:k,val:JSON.stringify(bdi[k]).substring(0,80)}}),
        scopeKeys:scopeKeys,
        scopeValues:scopeKeys.map(function(k){return{key:k,val:JSON.stringify(bdi[k]).substring(0,80)}}),
        allKeysCount:allKeys.length,
        allKeysSample:allKeys.slice(0,50)
    };
})()""")
print(f"  compName: {bdi.get('compName','')}")
print(f"  industryKeys: {bdi.get('industryKeys',[])}")
print(f"  industryValues: {bdi.get('industryValues',[])}")
print(f"  scopeKeys: {bdi.get('scopeKeys',[])}")
print(f"  scopeValues: {bdi.get('scopeValues',[])}")
print(f"  allKeys({bdi.get('allKeysCount',0)}): {bdi.get('allKeysSample',[])}")

# ===== STEP 3: 直接设置行业类型和经营范围 =====
print("\nSTEP 3: 设置行业类型和经营范围")
set_result = ev("""(function(){
    var Vue=window.Vue||document.getElementById('app')?.__vue__?.constructor;
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
    var bdi=inst.$data.businessDataInfo;
    var results=[];
    
    // 设置行业类型相关字段
    var industryMap={
        'namePreIndustryTypeCode':'I',
        'industryTypeCode':'I',
        'industryType':'信息传输、软件和信息技术服务业',
        'phmeconmyType':'I',
        'phmeconmyTypeCode':'I',
        'economyType':'I',
        'economyTypeCode':'I',
        'noIndustry':'',
        'industrySpecial':'',
        'mustCNSType':'',
        'flowTypeSign':''
    };
    for(var k in industryMap){
        if(k in bdi){
            var old=JSON.stringify(bdi[k]).substring(0,30);
            Vue.set(bdi,k,industryMap[k]);
            results.push({key:k,old:old,new:industryMap[k],type:'industry'});
        }
    }
    
    // 设置经营范围相关字段
    var scopeMap={
        'businessScope':'软件开发;信息技术咨询服务;数据处理和存储支持服务',
        'businessArea':'软件开发;信息技术咨询服务;数据处理和存储支持服务',
        'scopeItems':[{name:'软件开发',code:'I6410'},{name:'信息技术咨询服务',code:'I6411'}],
        'businessScopeCode':'I6410;I6411',
        'businessAreaCode':'I6410;I6411'
    };
    for(var k in scopeMap){
        if(k in bdi){
            var old=JSON.stringify(bdi[k]).substring(0,30);
            Vue.set(bdi,k,scopeMap[k]);
            results.push({key:k,old:old,new:JSON.stringify(scopeMap[k]).substring(0,30),type:'scope'});
        }
    }
    
    inst.$forceUpdate();
    return{results:results};
})()""")
print(f"  set_result: {set_result}")
time.sleep(2)

# ===== STEP 4: 验证 =====
print("\nSTEP 4: 验证")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if errs:
    log("230.验证错误", {"errors":errs})
    
    # 如果仍有行业类型/经营范围错误，尝试更深入的方法
    if any('行业类型' in e or '经营范围' in e for e in (errs or [])):
        print("\n  尝试更深入的设置...")
        
        # 找到行业类型select组件并直接设置值
        ev("""(function(){
            var fi=document.querySelectorAll('.el-form-item');
            for(var i=0;i<fi.length;i++){
                var label=fi[i].querySelector('.el-form-item__label');
                if(label&&label.textContent.trim().includes('行业类型')){
                    var sel=fi[i].querySelector('.el-select');
                    var comp=sel?.__vue__;
                    if(comp){
                        // 直接设置value
                        comp.$emit('input','I');
                        comp.$emit('change','I');
                        comp.value='I';
                        comp.currentValue='I';
                        comp.selectedLabel='信息传输、软件和信息技术服务业';
                        comp.$forceUpdate();
                    }
                }
            }
        })()""")
        time.sleep(1)
        
        # 找到经营范围的Vue组件并设置
        ev("""(function(){
            var fi=document.querySelectorAll('.el-form-item');
            for(var i=0;i<fi.length;i++){
                var label=fi[i].querySelector('.el-form-item__label');
                if(label&&label.textContent.trim().includes('经营范围')){
                    var comp=fi[i].__vue__;
                    // 向上找包含businessArea的组件
                    var c=comp;
                    for(var d=0;d<10&&c;d++){
                        var data=c.$data||{};
                        for(var k in data){
                            if(k==='businessArea'||k==='businessScope'){
                                Vue.set(data,k,'软件开发;信息技术咨询服务;数据处理和存储支持服务');
                            }
                        }
                        c=c.$parent;
                    }
                }
            }
        })()""")
        time.sleep(1)
        
        # 再次验证
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(5)
        
        errs2 = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
        page2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  第二次: errors={errs2} hash={page2.get('hash')} forms={page2.get('formCount',0)}")
        
        if not errs2:
            errs = errs2
            page = page2

if not errs:
    print("  ✅ 验证通过！")
    log("230.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤
    print("\nSTEP 5: 遍历步骤到提交页")
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
            print(f"\n  🔴 提交按钮！停止（不点击）")
            log("231.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    print(f"  ⚠️ 最终验证错误: {errs}")

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
    print(f"  问题数: {len(rpt.get('issues',[]))}")
    log("232.E2E报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final19.py 完成")
