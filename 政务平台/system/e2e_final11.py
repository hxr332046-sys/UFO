#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final11: 深入cascader组件内部 → 用组件方法设值 → select精确选择 → 经营范围对话框"""
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

# ===== STEP 1: 深入分析cascader组件内部结构 =====
print("STEP 1: 深入分析cascader组件")
cas_deep = ev("""(function(){
    var cas=document.querySelectorAll('.el-cascader');
    var r=[];
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=cas[i].__vue__;
        if(!comp)continue;
        
        // 获取组件所有属性
        var props=comp.$props||{};
        var propKeys=Object.keys(props);
        
        // 获取value/v-model
        var value=comp.value;
        var presentValue=comp.presentValue;
        var currentValue=comp.currentValue;
        
        // 获取cascader配置
        var cascaderConfig=comp.config||{};
        
        // 获取options（可能需要从props获取）
        var options=comp.options||props.options||[];
        var optLen=options.length;
        var optSample=[];
        if(optLen>0){
            for(var j=0;j<Math.min(3,optLen);j++){
                var o=options[j];
                optSample.push({
                    label:o.label||'',value:o.value||'',
                    children:o.children?.length||0
                });
            }
        }
        
        // 获取panel
        var panel=comp.menu||comp.panel;
        var hasPanel=!!panel;
        
        // 获取绑定的form-item prop
        var formItemComp=fi?.__vue__;
        var prop=formItemComp?.prop||'';
        
        r.push({
            idx:i,label:label,
            value:value,presentValue:presentValue,currentValue:currentValue,
            prop:prop,
            optLen:optLen,optSample:optSample,
            hasPanel:hasPanel,
            propKeys:propKeys.slice(0,10),
            cascaderConfigKeys:Object.keys(cascaderConfig).slice(0,5)
        });
    }
    return r;
})()""")
for c in (cas_deep or []):
    print(f"\n  cascader #{c.get('idx')}: {c.get('label','')}")
    print(f"    prop: {c.get('prop','')}")
    print(f"    value: {c.get('value')}")
    print(f"    presentValue: {c.get('presentValue')}")
    print(f"    currentValue: {c.get('currentValue')}")
    print(f"    options: {c.get('optLen',0)} sample: {c.get('optSample',[])}")
    print(f"    hasPanel: {c.get('hasPanel')}")
    print(f"    propKeys: {c.get('propKeys',[])}")

# ===== STEP 2: 如果cascader options为空，尝试激活它 =====
print("\nSTEP 2: 激活cascader获取options")
for idx in range(len(cas_deep or [])):
    c = (cas_deep or [])[idx]
    if c.get('optLen',0) == 0:
        print(f"  cascader #{idx} options为空，尝试激活...")
        # 点击cascader触发懒加载
        ev(f"""(function(){{
            var cas=document.querySelectorAll('.el-cascader');
            var input=cas[{idx}]?.querySelector('.el-input__inner');
            if(input)input.click();
        }})()""")
        time.sleep(2)
        
        # 检查panel是否出现
        panel_check = ev("""(function(){
            var panels=document.querySelectorAll('.el-cascader-menus,.el-cascader__dropdown');
            var visiblePanels=[];
            for(var i=0;i<panels.length;i++){
                if(panels[i].offsetParent!==null||panels[i].style?.display!=='none'){
                    var menus=panels[i].querySelectorAll('.el-cascader-menu');
                    var items0=menus[0]?.querySelectorAll('.el-cascader-node')||[];
                    visiblePanels.push({menuCount:menus.length,items0:items0.length,sample:Array.from(items0).slice(0,3).map(function(n){return n.textContent?.trim()||''})});
                }
            }
            return visiblePanels;
        })()""")
        print(f"    panels: {panel_check}")
        
        # 如果panel出现了，选择广西
        if panel_check and len(panel_check) > 0 and panel_check[0].get('items0',0) > 0:
            print(f"    选择广西...")
            ev("""(function(){
                var menus=document.querySelectorAll('.el-cascader-menu');
                if(menus.length>0){
                    var items=menus[0].querySelectorAll('.el-cascader-node');
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('广西')){
                            items[i].click();return{selected:'广西'};
                        }
                    }
                    if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
                }
                return{error:'no_items'};
            })()""")
            time.sleep(2)
            
            # 选择南宁
            ev("""(function(){
                var menus=document.querySelectorAll('.el-cascader-menu');
                if(menus.length>1){
                    var items=menus[1].querySelectorAll('.el-cascader-node');
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('南宁')){
                            items[i].click();return{selected:'南宁'};
                        }
                    }
                    if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
                }
                return{error:'no_nanning'};
            })()""")
            time.sleep(2)
            
            # 选择青秀区
            ev("""(function(){
                var menus=document.querySelectorAll('.el-cascader-menu');
                if(menus.length>2){
                    var items=menus[2].querySelectorAll('.el-cascader-node');
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('青秀')){
                            items[i].click();return{selected:'青秀区'};
                        }
                    }
                    if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
                }
                return{error:'no_district'};
            })()""")
            time.sleep(1)
            
            # 关闭
            ev("document.body.click()")
            time.sleep(1)
        else:
            # panel没出现，尝试通过组件方法
            print(f"    panel未出现，尝试组件方法...")
            ev(f"""(function(){{
                var cas=document.querySelectorAll('.el-cascader');
                var comp=cas[{idx}]?.__vue__;
                if(comp){{
                    // 尝试激活
                    if(comp.handleActivatorClick)comp.handleActivatorClick();
                    if(comp.toggleMenu)comp.toggleMenu();
                    if(comp.handleFocus)comp.handleFocus();
                }}
            }})()""")
            time.sleep(2)
            
            # 再次检查panel
            panel2 = ev("""(function(){
                var menus=document.querySelectorAll('.el-cascader-menu');
                return{menuCount:menus.length,items0:menus[0]?.querySelectorAll('.el-cascader-node')?.length||0};
            })()""")
            print(f"    panel2: {panel2}")

# ===== STEP 3: 验证cascader值 =====
print("\nSTEP 3: 验证cascader值")
cas_vals = ev("""(function(){
    var cas=document.querySelectorAll('.el-cascader');
    var r=[];
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=cas[i].__vue__;
        var input=cas[i].querySelector('.el-input__inner');
        r.push({idx:i,label:label,inputVal:input?.value||'',compVal:comp?.value,presentVal:comp?.presentValue});
    }
    return r;
})()""")
print(f"  cascader values: {cas_vals}")

# ===== STEP 4: 处理select - 精确选择 =====
print("\nSTEP 4: 处理select精确选择")
# 先分析select dropdown结构
sel_analysis = ev("""(function(){
    var sels=document.querySelectorAll('.el-select');
    var r=[];
    for(var i=0;i<sels.length;i++){
        var fi=sels[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=sels[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        var comp=sels[i].__vue__;
        if(!comp)continue;
        
        // 获取options
        var opts=comp.options||comp.cachedOptions||[];
        var optSample=[];
        for(var j=0;j<Math.min(5,opts.length);j++){
            var o=opts[j];
            optSample.push({
                label:o.currentLabel||o.label||o.text||'',
                value:o.currentValue||o.value||o.currentKey||'',
                disabled:o.disabled||false
            });
        }
        
        r.push({idx:i,label:label,val:val,optCount:opts.length,optSample:optSample,compName:comp.$options?.name||''});
    }
    return r;
})()""")
for s in (sel_analysis or []):
    print(f"  select #{s.get('idx')}: {s.get('label','')} val={s.get('val','')} count={s.get('optCount',0)}")
    print(f"    sample: {s.get('optSample',[])}")

# 精确选择行业类型
for s in (sel_analysis or []):
    if '行业类型' in s.get('label','') and not s.get('val',''):
        print(f"\n  选择行业类型...")
        # 找到合适的选项
        opts = s.get('optSample',[])
        if opts:
            # 选择包含"软件"或"信息技术"的选项
            target_val = None
            target_label = None
            for o in opts:
                if '软件' in o.get('label','') or '信息' in o.get('label','') or '技术' in o.get('label',''):
                    target_val = o.get('value')
                    target_label = o.get('label')
                    break
            if not target_val and opts:
                target_val = opts[0].get('value')
                target_label = opts[0].get('label')
            
            if target_val:
                idx = s.get('idx',0)
                ev(f"""(function(){{
                    var sels=document.querySelectorAll('.el-select');
                    var comp=sels[{idx}]?.__vue__;
                    if(comp){{
                        comp.handleOptionSelect({{value:'{target_val}',currentLabel:'{target_label}'}});
                        comp.$emit('input','{target_val}');
                    }}
                }})()""")
                print(f"    选择: {target_label} ({target_val})")
                time.sleep(1)

# ===== STEP 5: 处理经营范围 =====
print("\nSTEP 5: 处理经营范围")
# 点击"添加规范经营用语"
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btns=fi[i].querySelectorAll('button,.el-button,.add-btn,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if(t.includes('添加')||t.includes('规范')){
                    btns[j].click();
                    return{clicked:t};
                }
            }
        }
    }
    return{error:'not_found'};
})()""")
time.sleep(3)

# 检查对话框或新面板
dialog_check = ev("""(function(){
    // 检查el-dialog
    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
            var title=dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'';
            var body=dialogs[i].querySelector('.el-dialog__body');
            var bodyText=body?.innerText?.trim()?.substring(0,200)||'';
            var bodyHtml=body?.innerHTML?.substring(0,300)||'';
            return{type:'dialog',title:title,bodyText:bodyText,bodyHtml:bodyHtml};
        }
    }
    // 检查el-popover
    var popovers=document.querySelectorAll('.el-popover');
    for(var i=0;i<popovers.length;i++){
        if(popovers[i].offsetParent!==null){
            return{type:'popover',text:popovers[i].innerText?.trim()?.substring(0,200)||''};
        }
    }
    // 检查新iframe
    var iframes=document.querySelectorAll('iframe');
    for(var i=0;i<iframes.length;i++){
        return{type:'iframe',src:iframes[i].src||''};
    }
    // 检查drawer
    var drawers=document.querySelectorAll('.el-drawer');
    for(var i=0;i<drawers.length;i++){
        if(drawers[i].offsetParent!==null){
            return{type:'drawer',text:drawers[i].innerText?.trim()?.substring(0,200)||''};
        }
    }
    return{type:'none'};
})()""")
print(f"  dialog_check: {dialog_check}")

# 如果有对话框，处理它
if dialog_check and dialog_check.get('type') != 'none':
    dtype = dialog_check.get('type')
    print(f"  处理 {dtype}...")
    
    if dtype == 'dialog':
        # 在对话框中搜索并选择经营范围
        ev("""(function(){
            var dialogs=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<dialogs.length;i++){
                if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
                    // 找搜索框
                    var search=dialogs[i].querySelector('.el-input__inner');
                    if(search){
                        var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                        setter.call(search,'软件开发');
                        search.dispatchEvent(new Event('input',{bubbles:true}));
                        search.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                    // 找checkboxes
                    var checkboxes=dialogs[i].querySelectorAll('.el-checkbox');
                    for(var j=0;j<Math.min(3,checkboxes.length);j++){
                        if(!checkboxes[j].className?.includes('is-checked')){
                            checkboxes[j].click();
                        }
                    }
                    // 找确定按钮
                    var btns=dialogs[i].querySelectorAll('button,.el-button');
                    for(var j=0;j<btns.length;j++){
                        var t=btns[j].textContent?.trim()||'';
                        if(t.includes('确定')||t.includes('确认')||t.includes('保存')||t.includes('添加')){
                            btns[j].click();return;
                        }
                    }
                }
            }
        })()""")
        time.sleep(3)
    elif dtype == 'iframe':
        # iframe需要特殊处理
        print("  ⚠️ iframe中的经营范围，需要特殊处理")

# ===== STEP 6: 最终验证 =====
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

errs = ev("""(function(){
    var msgs=document.querySelectorAll('.el-form-item__error,.el-message');
    var r=[];
    for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}
    return r.slice(0,10);
})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

screenshot("step6_result")

if not errs:
    print("  ✅ 验证通过！")
    log("150.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤
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
            log("151.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
                print(f"  验证阻止")
                break
else:
    print(f"  ⚠️ 仍有验证错误: {errs}")
    log("150.验证失败", {"errors":errs})
    
    # 最后尝试：通过Vue.set强制设值
    print("\n  最后尝试：Vue.set强制设值...")
    force_result = ev("""(function(){
        var Vue=window.Vue||document.getElementById('app')?.__vue__?.constructor;
        if(!Vue)return{error:'no_Vue'};
        
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        
        // 递归找businessDataInfo
        function findBDI(vm,depth){
            if(depth>10)return null;
            if(vm.$data?.businessDataInfo)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){
                var r=findBDI(children[i],depth+1);
                if(r)return r;
            }
            return null;
        }
        
        var inst=findBDI(vm,0);
        if(!inst)return{error:'no_bdi'};
        var bdi=inst.$data.businessDataInfo;
        
        // 设置地址字段
        var addrKeys=['domicileArea','domicileAreaCode','businessPlaceArea','businessPlaceAreaCode','domicileProvince','domicileCity','domicileDistrict','businessPlaceProvince','businessPlaceCity','businessPlaceDistrict'];
        var results=[];
        for(var i=0;i<addrKeys.length;i++){
            var k=addrKeys[i];
            if(k in bdi){
                var old=bdi[k];
                if(k.includes('Province'))Vue.set(bdi,k,'450000');
                else if(k.includes('City'))Vue.set(bdi,k,'450100');
                else if(k.includes('District')||k.includes('AreaCode'))Vue.set(bdi,k,'450103');
                else if(k.includes('Area'))Vue.set(bdi,k,['450000','450100','450103']);
                results.push({key:k,old:JSON.stringify(old),new:JSON.stringify(bdi[k])});
            }
        }
        
        // 设置行业类型
        var industryKeys=['industryType','industryTypeCode','namePreIndustryTypeCode','noIndustry'];
        for(var i=0;i<industryKeys.length;i++){
            var k=industryKeys[i];
            if(k in bdi && !bdi[k]){
                Vue.set(bdi,k,'I64');
                results.push({key:k,new:'I64'});
            }
        }
        
        inst.$forceUpdate();
        return{results:results,allKeys:Object.keys(bdi).filter(function(k){return k.toLowerCase().includes('area')||k.toLowerCase().includes('addr')||k.toLowerCase().includes('province')||k.toLowerCase().includes('city')||k.toLowerCase().includes('district')||k.toLowerCase().includes('industry'))});
    })()""")
    print(f"  force: {force_result}")
    time.sleep(2)
    
    # 再次保存
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(5)
    
    errs3 = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
    page3 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  最终: errors={errs3} hash={page3.get('hash')} forms={page3.get('formCount',0)}")
    
    if not errs3:
        print("  ✅ Vue.set后验证通过！")
    else:
        print(f"  ⚠️ 仍有错误，需要手动处理级联选择器")
        log("150b.最终验证", {"errors":errs3})

screenshot("final_result")

ws.close()
print("\n✅ e2e_final11.py 完成")
