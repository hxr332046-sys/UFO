#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final16: 修复剩余验证错误 → 详细地址/自贸区/行业类型/经营范围 → 遍历步骤"""
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

# ===== STEP 1: 填写详细地址 =====
print("STEP 1: 填写详细地址")
for label_text, val in [("详细地址", "民族大道166号16号楼5层501室"), ("生产经营地详细地址", "民族大道166号16号楼5层501室")]:
    r = ev(f"""(function(){{
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){{
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('{label_text}')){{
                var input=fi[i].querySelector('.el-input__inner');
                if(input&&!input.disabled){{
                    var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    setter.call(input,'{val}');input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));
                    return{{ok:true,label:label.textContent.trim()}};
                }}
            }}
        }}
        return{{ok:false}};
    }})()""")
    print(f"  {label_text}: {r}")

# ===== STEP 2: 是否自贸区 =====
print("\nSTEP 2: 是否自贸区")
ftz = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('自贸区')){
            // 找radio
            var radios=fi[i].querySelectorAll('.el-radio');
            var rTexts=[];
            for(var j=0;j<radios.length;j++){
                rTexts.push(radios[j].textContent?.trim()||'');
            }
            // 点击"否"
            for(var j=0;j<radios.length;j++){
                var t=radios[j].textContent?.trim()||'';
                if(t.includes('否')){
                    radios[j].click();
                    return{clicked:'否',options:rTexts};
                }
            }
            // 如果没有"否"，点第一个
            if(radios.length>0){
                radios[0].click();
                return{clicked:radios[0].textContent?.trim(),options:rTexts};
            }
            return{error:'no_radio',label:label.textContent.trim()};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  自贸区: {ftz}")

# ===== STEP 3: 行业类型 - 分组select =====
print("\nSTEP 3: 行业类型（分组select）")
# 点击select
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)

# 点击[I]分组选项
industry_r = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t.includes('[I]')&&!items[j].className?.includes('disabled')){
                    items[j].click();
                    return{clicked:t.substring(0,30)};
                }
            }
            // 如果没有[I]，列出所有
            var all=[];
            for(var j=0;j<items.length;j++){
                all.push({idx:j,text:items[j].textContent?.trim()?.substring(0,30)||'',disabled:items[j].className?.includes('disabled'),cls:items[j].className?.substring(0,30)||''});
            }
            return{items:all};
        }
    }
    return{error:'no_dropdown'};
})()""")
print(f"  industry: {industry_r}")
time.sleep(2)

# 检查是否展开了子选项
sub = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            var r=[];
            for(var j=0;j<Math.min(15,items.length);j++){
                r.push({idx:j,text:items[j].textContent?.trim()?.substring(0,40)||'',disabled:items[j].className?.includes('disabled'),cls:items[j].className?.includes('group')?'group':'leaf'});
            }
            return{items:r};
        }
    }
    return{error:'no_dropdown'};
})()""")
print(f"  sub items: {sub}")

# 选择子选项
if sub and sub.get('items'):
    for item in sub.get('items',[]):
        if not item.get('disabled') and not item.get('cls')=='group' and item.get('text',''):
            idx = item.get('idx',0)
            print(f"  选择: {item.get('text','')[:30]}")
            ev(f"""(function(){{
                var dropdowns=document.querySelectorAll('.el-select-dropdown');
                for(var i=0;i<dropdowns.length;i++){{
                    if(dropdowns[i].offsetParent!==null){{
                        var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
                        if(items[{idx}])items[{idx}].click();
                    }}
                }}
            }})()""")
            time.sleep(1)
            break
    else:
        # 如果所有leaf选项都为空，尝试通过Vue组件设置
        print("  leaf选项为空，通过Vue组件设置...")
        ev("""(function(){
            var fi=document.querySelectorAll('.el-form-item');
            for(var i=0;i<fi.length;i++){
                var label=fi[i].querySelector('.el-form-item__label');
                if(label&&label.textContent.trim().includes('行业类型')){
                    var sel=fi[i].querySelector('.el-select');
                    var comp=sel?.__vue__;
                    if(comp){
                        // 找到[I]选项并选择
                        var opts=comp.options||comp.cachedOptions||[];
                        for(var j=0;j<opts.length;j++){
                            var o=opts[j];
                            var t=o.currentLabel||o.label||'';
                            if(t.includes('[I]')){
                                comp.handleOptionSelect(o);
                                comp.$emit('input',o.value||o.currentValue);
                                return{selected:t.substring(0,30)};
                            }
                        }
                        // 检查group选项的children
                        for(var j=0;j<opts.length;j++){
                            var children=opts[j].children||[];
                            if(children.length>0){
                                var child=children[0];
                                comp.handleOptionSelect(child);
                                comp.$emit('input',child.value||child.currentValue);
                                return{selected:'first_child_of_'+(opts[j].currentLabel||opts[j].label||'').substring(0,10)};
                            }
                        }
                    }
                }
            }
        })()""")
        time.sleep(1)

# 关闭dropdown
ev("document.body.click()")
time.sleep(1)

# ===== STEP 4: 经营范围 =====
print("\nSTEP 4: 经营范围")
# 先分析经营范围字段的完整结构
scope_analysis = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var html=fi[i].innerHTML.substring(0,500);
            var btns=fi[i].querySelectorAll('button,.el-button,[class*="add"],[class*="btn"]');
            var btnTexts=[];
            for(var j=0;j<btns.length;j++){
                btnTexts.push({text:btns[j].textContent?.trim()||'',class:btns[j].className?.substring(0,30)||'',tag:btns[j].tagName});
            }
            var tags=fi[i].querySelectorAll('.el-tag,[class*="tag"]');
            var inputs=fi[i].querySelectorAll('input,textarea');
            var comp=fi[i].__vue__;
            var prop=comp?.prop||'';
            return{html:html,btnTexts:btnTexts,tagCount:tags.length,inputCount:inputs.length,prop:prop};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  scope_analysis: btnTexts={scope_analysis.get('btnTexts',[])} tags={scope_analysis.get('tagCount',0)} inputs={scope_analysis.get('inputCount',0)}")

# 点击"添加规范经营用语"按钮
if scope_analysis and scope_analysis.get('btnTexts'):
    for btn in scope_analysis.get('btnTexts',[]):
        if '添加' in btn.get('text','') or '规范' in btn.get('text',''):
            print(f"  点击: {btn.get('text','')}")
            # 精确点击这个按钮
            ev(f"""(function(){{
                var fi=document.querySelectorAll('.el-form-item');
                for(var i=0;i<fi.length;i++){{
                    var label=fi[i].querySelector('.el-form-item__label');
                    if(label&&label.textContent.trim().includes('经营范围')){{
                        var btns=fi[i].querySelectorAll('button,.el-button,[class*="add"]');
                        for(var j=0;j<btns.length;j++){{
                            if(btns[j].textContent?.trim()?.includes('添加')||btns[j].textContent?.trim()?.includes('规范')){{
                                btns[j].click();
                                // 也触发Vue事件
                                btns[j].dispatchEvent(new Event('click',{{bubbles:true}}));
                                return;
                            }}
                        }}
                    }}
                }}
            }})()""")
            time.sleep(3)
            break

# 检查弹出的内容
popup = ev("""(function(){
    // 检查所有可能弹出的元素
    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
            var title=dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'';
            var body=dialogs[i].querySelector('.el-dialog__body');
            return{type:'dialog',title:title,text:body?.innerText?.trim()?.substring(0,200)||'',html:body?.innerHTML?.substring(0,300)||''};
        }
    }
    var pickers=document.querySelectorAll('.tne-data-picker-viewer');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var text=pickers[i].textContent?.trim()?.substring(0,100)||'';
            var items=pickers[i].querySelectorAll('.tab-c .item');
            var itemTexts=Array.from(items).slice(0,5).map(function(x){return x.textContent?.trim()?.substring(0,20)});
            return{type:'picker',text:text,itemCount:items.length,itemTexts:itemTexts};
        }
    }
    var drawers=document.querySelectorAll('.el-drawer');
    for(var i=0;i<drawers.length;i++){
        if(drawers[i].offsetParent!==null){
            return{type:'drawer',text:drawers[i].querySelector('.el-drawer__body')?.innerText?.trim()?.substring(0,200)||''};
        }
    }
    // 检查新出现的iframe
    var iframes=document.querySelectorAll('iframe');
    for(var i=0;i<iframes.length;i++){
        var src=iframes[i].src||'';
        if(!src.includes('header')&&!src.includes('footer')){
            return{type:'iframe',src:src};
        }
    }
    return{type:'none'};
})()""")
print(f"  popup: {popup}")

if popup and popup.get('type') == 'picker':
    # 在picker中选择经营范围
    print("  在picker中选择经营范围...")
    # 先选行业大类[I]
    ev("""(function(){
        var pickers=document.querySelectorAll('.tne-data-picker-viewer');
        for(var i=0;i<pickers.length;i++){
            if(pickers[i].offsetParent!==null){
                var items=pickers[i].querySelectorAll('.tab-c .item');
                for(var j=0;j<items.length;j++){
                    var t=items[j].textContent?.trim()||'';
                    if(t.includes('信息传输')||t.includes('软件')||t.includes('[I]')){
                        items[j].click();return{clicked:t.substring(0,20)};
                    }
                }
            }
        }
    })()""")
    time.sleep(2)
    
    # 选择子类
    scope2 = ev("""(function(){
        var pickers=document.querySelectorAll('.tne-data-picker-viewer');
        for(var i=0;i<pickers.length;i++){
            if(pickers[i].offsetParent!==null){
                var items=pickers[i].querySelectorAll('.tab-c .item');
                var texts=Array.from(items).slice(0,8).map(function(x){return x.textContent?.trim()?.substring(0,25)});
                return{itemCount:items.length,texts:texts};
            }
        }
    })()""")
    print(f"  scope2: {scope2}")
    
    if scope2 and scope2.get('itemCount',0) > 0:
        # 选择"软件开发"
        ev("""(function(){
            var pickers=document.querySelectorAll('.tne-data-picker-viewer');
            for(var i=0;i<pickers.length;i++){
                if(pickers[i].offsetParent!==null){
                    var items=pickers[i].querySelectorAll('.tab-c .item');
                    for(var j=0;j<items.length;j++){
                        var t=items[j].textContent?.trim()||'';
                        if(t.includes('软件开发')){
                            items[j].click();return{clicked:t};
                        }
                    }
                    if(items.length>0)items[0].click();
                }
            }
        })()""")
        time.sleep(2)
        
        # 可能还有更细的分类
        scope3 = ev("""(function(){
            var pickers=document.querySelectorAll('.tne-data-picker-viewer');
            for(var i=0;i<pickers.length;i++){
                if(pickers[i].offsetParent!==null){
                    var items=pickers[i].querySelectorAll('.tab-c .item');
                    var texts=Array.from(items).slice(0,5).map(function(x){return x.textContent?.trim()?.substring(0,25)});
                    return{itemCount:items.length,texts:texts};
                }
            }
        })()""")
        print(f"  scope3: {scope3}")
        
        if scope3 and scope3.get('itemCount',0) > 0:
            ev("""(function(){
                var pickers=document.querySelectorAll('.tne-data-picker-viewer');
                for(var i=0;i<pickers.length;i++){
                    if(pickers[i].offsetParent!==null){
                        var items=pickers[i].querySelectorAll('.tab-c .item');
                        if(items.length>0)items[0].click();
                    }
                }
            })()""")
            time.sleep(1)
    
    # 确认
    ev("""(function(){
        var picker=document.querySelector('.tne-data-picker');
        var btns=picker?.querySelectorAll('button,[class*="confirm"]');
        if(btns){
            for(var i=0;i<btns.length;i++){
                if(btns[i].textContent?.trim()?.includes('确定')||btns[i].textContent?.trim()?.includes('确认')){
                    btns[i].click();return;
                }
            }
        }
        document.body.click();
    })()""")
    time.sleep(2)

elif popup and popup.get('type') == 'dialog':
    # 在对话框中操作
    print("  在对话框中选择经营范围...")
    # 搜索
    ev("""(function(){
        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent!==null){
                var search=dialogs[i].querySelector('.el-input__inner');
                if(search){
                    var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    setter.call(search,'软件开发');
                    search.dispatchEvent(new Event('input',{bubbles:true}));
                }
            }
        }
    })()""")
    time.sleep(2)
    
    # 选择checkbox
    ev("""(function(){
        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent!==null){
                var checkboxes=dialogs[i].querySelectorAll('.el-checkbox');
                for(var j=0;j<Math.min(3,checkboxes.length);j++){
                    if(!checkboxes[j].className?.includes('is-checked'))checkboxes[j].click();
                }
                var btns=dialogs[i].querySelectorAll('button,.el-button');
                for(var j=0;j<btns.length;j++){
                    if(btns[j].textContent?.trim()?.includes('确定')||btns[j].textContent?.trim()?.includes('确认')){
                        btns[j].click();return;
                    }
                }
            }
        }
    })()""")
    time.sleep(2)

screenshot("step4_scope")

# ===== STEP 5: 验证 =====
print("\nSTEP 5: 验证")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if not errs:
    print("  ✅ 验证通过！")
    log("200.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤直到提交页
    print("\nSTEP 6: 遍历步骤")
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
            log("201.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    log("200.验证失败", {"errors":errs})
    
    # 如果只有行业类型和经营范围问题，尝试直接设置数据
    if '行业类型' in str(errs) or '经营范围' in str(errs):
        print("\n  尝试通过Vue数据模型设置...")
        ev("""(function(){
            var app=document.getElementById('app');
            var vm=app?.__vue__;
            function findBDI(vm,depth){
                if(depth>10)return null;
                if(vm.$data?.businessDataInfo)return vm;
                var children=vm.$children||[];
                for(var i=0;i<children.length;i++){var r=findBDI(children[i],depth+1);if(r)return r}
                return null;
            }
            var inst=findBDI(vm,0);
            if(!inst)return;
            var bdi=inst.$data.businessDataInfo;
            
            // 设置行业类型
            if('namePreIndustryTypeCode' in bdi)Vue.set(bdi,'namePreIndustryTypeCode','I64');
            if('industryTypeCode' in bdi)Vue.set(bdi,'industryTypeCode','I64');
            if('industryType' in bdi)Vue.set(bdi,'industryType','信息传输、软件和信息技术服务业');
            
            // 设置经营范围
            if('businessScope' in bdi)Vue.set(bdi,'businessScope','软件开发;信息技术咨询服务;数据处理服务');
            if('businessArea' in bdi)Vue.set(bdi,'businessArea','软件开发;信息技术咨询服务;数据处理服务');
            if('scopeItems' in bdi)Vue.set(bdi,'scopeItems',[{name:'软件开发',code:'I6410'}]);
            
            inst.$forceUpdate();
        })()""")
        time.sleep(2)
        
        # 再次保存
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(5)
        
        errs3 = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
        page3 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  Vue.set后: errors={errs3} hash={page3.get('hash')} forms={page3.get('formCount',0)}")

screenshot("final_result")

# ===== 最终报告 =====
print("\n" + "=" * 60)
print("E2E 测试最终报告")
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
    log("202.E2E最终报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final16.py 完成")
