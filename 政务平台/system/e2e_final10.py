#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final10: 通过currentComp找到真正表单组件 → 设置cascader/select/经营范围 → 通过验证"""
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

# ===== STEP 1: 通过currentComp找到表单组件 =====
print("STEP 1: 找到表单组件")
form_comp = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    
    // 方法1: 通过matched找
    for(var i=0;i<matched.length;i++){
        var m=matched[i];
        var inst=m.instances?.default;
        if(inst){
            // 检查currentComp
            if(inst.$data?.currentComp){
                var compName=inst.$data.currentComp;
                // 找子组件
                var children=inst.$children||[];
                for(var j=0;j<children.length;j++){
                    var child=children[j];
                    if(child.$options?.name===compName||child.$el?.className?.includes(compName)){
                        return{found:'currentComp',compName:compName,childName:child.$options?.name,dataKeys:Object.keys(child.$data||{}).slice(0,20)};
                    }
                }
                // 也搜索所有子组件
                for(var j=0;j<children.length;j++){
                    var child=children[j];
                    var dk=Object.keys(child.$data||{});
                    if(dk.some(function(k){return k.includes('form')||k.includes('Form')})){
                        return{found:'child_with_form',compName:compName,childName:child.$options?.name,dataKeys:dk.slice(0,20)};
                    }
                }
            }
        }
    }
    
    // 方法2: 递归搜索所有组件
    function findDeep(vm,depth,path){
        if(depth>6)return null;
        var dk=Object.keys(vm.$data||{});
        // 检查是否有form数据
        for(var i=0;i<dk.length;i++){
            var v=vm.$data[dk[i]];
            if(v&&typeof v==='object'&&!Array.isArray(v)){
                var vk=Object.keys(v);
                if(vk.length>10&&vk.some(function(k){return k.includes('entName')||k.includes('regCap')||k.includes('address')})){
                    return{path:path+'.'+dk[i],compName:vm.$options?.name,dataKeys:dk.slice(0,20),formKeys:vk.slice(0,30)};
                }
            }
        }
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){
            var r=findDeep(children[i],depth+1,path+'.'+(children[i].$options?.name||i));
            if(r)return r;
        }
        return null;
    }
    
    return findDeep(vm,0,'root');
})()""")
print(f"  form_comp: {form_comp}")

# ===== STEP 2: 获取表单数据详情 =====
print("\nSTEP 2: 获取表单数据详情")
form_data = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    
    // 递归找表单
    function findForm(vm,depth){
        if(depth>8)return null;
        var dk=Object.keys(vm.$data||{});
        for(var i=0;i<dk.length;i++){
            var v=vm.$data[dk[i]];
            if(v&&typeof v==='object'&&!Array.isArray(v)){
                var vk=Object.keys(v);
                if(vk.length>10){
                    // 检查是否有地址相关字段
                    var addrKeys=vk.filter(function(k){
                        var kl=k.toLowerCase();
                        return kl.includes('address')||kl.includes('addr')||kl.includes('domicile')||kl.includes('area')||kl.includes('region')||kl.includes('province')||kl.includes('city')||kl.includes('district')||kl.includes('location')||kl.includes('place');
                    });
                    var industryKeys=vk.filter(function(k){
                        var kl=k.toLowerCase();
                        return kl.includes('industry')||kl.includes('type')||kl.includes('scope')||kl.includes('business')||kl.includes('trade');
                    });
                    if(addrKeys.length>0||industryKeys.length>0){
                        return{compName:vm.$options?.name,formKey:dk[i],addrKeys:addrKeys,industryKeys:industryKeys,
                        addrValues:addrKeys.map(function(k){return{key:k,val:JSON.stringify(v[k]).substring(0,50)}}),
                        industryValues:industryKeys.map(function(k){return{key:k,val:JSON.stringify(v[k]).substring(0,50)}}),
                        allKeys:vk.slice(0,40)};
                    }
                }
            }
        }
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){
            var r=findForm(children[i],depth+1);
            if(r)return r;
        }
        return null;
    }
    
    return findForm(vm,0);
})()""")
print(f"  compName: {form_data.get('compName','')}")
print(f"  formKey: {form_data.get('formKey','')}")
print(f"  addrKeys: {form_data.get('addrKeys',[])}")
print(f"  addrValues: {form_data.get('addrValues',[])}")
print(f"  industryKeys: {form_data.get('industryKeys',[])}")
print(f"  industryValues: {form_data.get('industryValues',[])}")
print(f"  allKeys: {form_data.get('allKeys',[])}")

# ===== STEP 3: 直接设置表单数据模型中的地址和行业字段 =====
print("\nSTEP 3: 直接设置表单数据模型")
set_result = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    
    function findForm(vm,depth){
        if(depth>8)return null;
        var dk=Object.keys(vm.$data||{});
        for(var i=0;i<dk.length;i++){
            var v=vm.$data[dk[i]];
            if(v&&typeof v==='object'&&!Array.isArray(v)){
                var vk=Object.keys(v);
                if(vk.length>10){
                    var addrKeys=vk.filter(function(k){
                        var kl=k.toLowerCase();
                        return kl.includes('address')||kl.includes('addr')||kl.includes('domicile')||kl.includes('area')||kl.includes('region')||kl.includes('province')||kl.includes('city')||kl.includes('district')||kl.includes('location')||kl.includes('place');
                    });
                    if(addrKeys.length>0)return{comp:vm,formKey:dk[i],form:v,addrKeys:addrKeys};
                }
            }
        }
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){
            var r=findForm(children[i],depth+1);
            if(r)return r;
        }
        return null;
    }
    
    var found=findForm(vm,0);
    if(!found)return{error:'no_form_found'};
    
    var form=found.form;
    var results=[];
    
    // 设置地址字段 - 450000=广西 450100=南宁 450103=青秀区
    for(var i=0;i<found.addrKeys.length;i++){
        var k=found.addrKeys[i];
        var v=form[k];
        if(Array.isArray(v)){
            // 级联选择器值格式
            form[k]=['450000','450100','450103'];
            results.push({key:k,old:Array.isArray(v)?v.join(','):JSON.stringify(v),new:'450000,450100,450103'});
        }else if(typeof v==='string'){
            form[k]='450103';
            results.push({key:k,old:v,new:'450103'});
        }else if(v===null||v===undefined){
            // 尝试设为数组
            form[k]=['450000','450100','450103'];
            results.push({key:k,old:'null',new:'450000,450100,450103'});
        }
    }
    
    // 设置行业类型字段
    var industryKeys=Object.keys(form).filter(function(k){
        var kl=k.toLowerCase();
        return kl.includes('industry')||kl.includes('type')||kl.includes('scope')||kl.includes('business')||kl.includes('trade');
    });
    for(var i=0;i<industryKeys.length;i++){
        var k=industryKeys[i];
        var v=form[k];
        if(v===null||v===undefined||v===''||(Array.isArray(v)&&v.length===0)){
            // 尝试设为字符串
            form[k]='I64';
            results.push({key:k,old:JSON.stringify(v),new:'I64'});
        }
    }
    
    found.comp.$forceUpdate();
    return{results:results,formKey:found.formKey};
})()""")
print(f"  set_result: {set_result}")
time.sleep(2)

# ===== STEP 4: 验证cascader是否正确显示 =====
print("\nSTEP 4: 验证cascader显示")
cas_check = ev("""(function(){
    var cas=document.querySelectorAll('.el-cascader');
    var r=[];
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=cas[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        r.push({idx:i,label:label,value:val});
    }
    return r;
})()""")
print(f"  cascader values: {cas_check}")

# ===== STEP 5: 如果cascader仍为空，尝试通过UI交互 =====
if all(c.get('value','') == '' for c in (cas_check or [])):
    print("\nSTEP 4b: 通过UI交互设置cascader")
    for idx in range(len(cas_check or [])):
        label = (cas_check or [])[idx].get('label','')
        print(f"  处理 cascader #{idx}: {label}")
        
        # 点击cascader input
        ev(f"""(function(){{
            var cas=document.querySelectorAll('.el-cascader');
            var input=cas[{idx}]?.querySelector('.el-input__inner');
            if(input)input.click();
        }})()""")
        time.sleep(1)
        
        # 检查下拉面板
        panel = ev("""(function(){
            var panels=document.querySelectorAll('.el-cascader-menu');
            if(panels.length===0)return{error:'no_panel'};
            var items0=panels[0]?.querySelectorAll('.el-cascader-node')||[];
            var sample=[];
            for(var i=0;i<Math.min(5,items0.length);i++){
                sample.push(items0[i].textContent?.trim()||'');
            }
            return{panelCount:panels.length,items0Count:items0.length,sample:sample};
        })()""")
        print(f"    panel: {panel}")
        
        if panel and panel.get('items0Count',0) > 0:
            # 选择广西
            ev("""(function(){
                var panels=document.querySelectorAll('.el-cascader-menu');
                var items=panels[0]?.querySelectorAll('.el-cascader-node')||[];
                for(var i=0;i<items.length;i++){
                    if(items[i].textContent?.trim()?.includes('广西')){
                        items[i].click();return{selected:'广西'};
                    }
                }
                // 如果没找到广西，选第一个
                if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
                return{error:'no_match'};
            })()""")
            time.sleep(1.5)
            
            # 选择南宁
            ev("""(function(){
                var panels=document.querySelectorAll('.el-cascader-menu');
                if(panels.length>1){
                    var items=panels[1]?.querySelectorAll('.el-cascader-node')||[];
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('南宁')){
                            items[i].click();return{selected:'南宁'};
                        }
                    }
                    if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
                }
                return{error:'no_panel2'};
            })()""")
            time.sleep(1.5)
            
            # 选择青秀区
            ev("""(function(){
                var panels=document.querySelectorAll('.el-cascader-menu');
                if(panels.length>2){
                    var items=panels[2]?.querySelectorAll('.el-cascader-node')||[];
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('青秀')){
                            items[i].click();return{selected:'青秀区'};
                        }
                    }
                    if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
                }
                // 如果只有2级，直接关闭
                document.body.click();
                return{error:'no_panel3'};
            })()""")
            time.sleep(1)
            
            # 关闭cascader
            ev("document.body.click()")
            time.sleep(1)
        else:
            print(f"    ⚠️ 无下拉面板！")

# ===== STEP 6: 处理行业类型select =====
print("\nSTEP 5: 处理行业类型select")
sel_result = ev("""(function(){
    var sels=document.querySelectorAll('.el-select');
    var results=[];
    for(var i=0;i<sels.length;i++){
        var fi=sels[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=sels[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        if(val)continue; // 已有值
        
        var comp=sels[i].__vue__;
        if(!comp)continue;
        
        // 点击展开
        input?.click();
        
        // 等待下拉出现
        var dropdown=document.querySelector('.el-select-dropdown');
        if(!dropdown)continue;
        
        var items=dropdown.querySelectorAll('.el-select-dropdown__item');
        if(items.length>0){
            // 选第一个非空选项
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t){
                    items[j].click();
                    results.push({label:label,selected:t});
                    break;
                }
            }
        }
    }
    return results;
})()""")
print(f"  sel_result: {sel_result}")
time.sleep(2)

# ===== STEP 7: 处理经营范围 =====
print("\nSTEP 6: 处理经营范围")
# 点击"添加规范经营用语"按钮后，可能弹出对话框
scope_btn = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btns=fi[i].querySelectorAll('button,.el-button');
            var r=[];
            for(var j=0;j<btns.length;j++){
                r.push(btns[j].textContent?.trim()||'');
            }
            // 检查是否有已填的经营范围
            var tags=fi[i].querySelectorAll('.el-tag');
            var tagTexts=[];
            for(var j=0;j<tags.length;j++){
                tagTexts.push(tags[j].textContent?.trim()||'');
            }
            return{buttons:r,tagCount:tags.length,tagTexts:tagTexts,html:fi[i].innerHTML.substring(0,200)};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  scope: {scope_btn}")

# 点击添加按钮
if scope_btn and scope_btn.get('buttons'):
    for btn_text in scope_btn.get('buttons',[]):
        if '添加' in btn_text or '规范' in btn_text:
            print(f"  点击: {btn_text}")
            ev("""(function(){
                var fi=document.querySelectorAll('.el-form-item');
                for(var i=0;i<fi.length;i++){
                    var label=fi[i].querySelector('.el-form-item__label');
                    if(label&&label.textContent.trim().includes('经营范围')){
                        var btns=fi[i].querySelectorAll('button,.el-button');
                        for(var j=0;j<btns.length;j++){
                            if(btns[j].textContent?.trim()?.includes('添加')||btns[j].textContent?.trim()?.includes('规范')){
                                btns[j].click();return;
                            }
                        }
                    }
                }
            })()""")
            time.sleep(3)
            break
    
    # 检查是否弹出对话框
    dialog = ev("""(function(){
        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].style?.display!=='none'&&dialogs[i].offsetParent!==null){
                var title=dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'';
                var body=dialogs[i].querySelector('.el-dialog__body')?.textContent?.trim()||'';
                return{title:title,body:body.substring(0,200),visible:true};
            }
        }
        return{visible:false};
    })()""")
    print(f"  dialog: {dialog}")
    
    if dialog and dialog.get('visible'):
        # 在对话框中选择经营范围
        # 搜索"软件开发"或选第一个
        ev("""(function(){
            var dialogs=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<dialogs.length;i++){
                if(dialogs[i].style?.display!=='none'){
                    // 找checkbox或table行
                    var checkboxes=dialogs[i].querySelectorAll('.el-checkbox,input[type="checkbox"]');
                    if(checkboxes.length>0){
                        // 选前3个
                        for(var j=0;j<Math.min(3,checkboxes.length);j++){
                            if(!checkboxes[j].checked){
                                checkboxes[j].click();
                            }
                        }
                    }
                    // 找确定按钮
                    var btns=dialogs[i].querySelectorAll('button,.el-button');
                    for(var j=0;j<btns.length;j++){
                        var t=btns[j].textContent?.trim()||'';
                        if(t.includes('确定')||t.includes('确认')||t.includes('保存')){
                            btns[j].click();
                            return{clicked:t};
                        }
                    }
                }
            }
        })()""")
        time.sleep(3)

screenshot("step6_scope")

# ===== STEP 8: 最终验证 =====
print("\nSTEP 7: 保存并下一步")
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

if not errs:
    print("  ✅ 验证通过！进入下一步")
    log("140.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤直到提交页
    print("\nSTEP 8: 遍历步骤直到提交页")
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
            log("141.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
            screenshot("step8_submit_page")
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
        errs2 = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,5)})()""")
        if errs2:
            print(f"  ⚠️ 错误: {errs2}")
            if new_hash == current.get('hash'):
                print(f"  验证阻止前进")
                break
else:
    print(f"  ⚠️ 仍有验证错误")
    log("140.验证失败", {"errors":errs})

screenshot("step_final")

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
    # 去重认证发现
    unique_auth = set()
    for af in rpt.get('auth_findings',[]):
        if isinstance(af,dict) and af.get('auth'):
            for k,v in af['auth'].items():
                if v: unique_auth.add(k)
    print(f"  认证类型: {list(unique_auth)}")
    log("142.E2E测试完成", {"totalSteps":len(rpt.get('steps',[])),"authFindings":len(rpt.get('auth_findings',[])),"authTypes":list(unique_auth),"issues":len(rpt.get('issues',[]))})

ws.close()
print("\n✅ e2e_final10.py 完成")
