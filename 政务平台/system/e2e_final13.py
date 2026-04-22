#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final13: 交互tne-data-picker区域选择器 → 行业类型select → 经营范围 → 通过验证 → 遍历步骤"""
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

# ===== STEP 1: 处理企业住所 - tne-data-picker =====
print("STEP 1: 企业住所区域选择器")
# 点击企业住所input
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('企业住所')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input)input.click();
            return;
        }
    }
})()""")
time.sleep(2)

# 分析tne-data-picker结构
picker = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,.tne-data-picker');
    var r=[];
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var cols=pickers[i].querySelectorAll('.tne-data-picker__column,[class*="column"],[class*="list"],[class*="group"]');
            var items=pickers[i].querySelectorAll('.tne-data-picker__item,[class*="item"],li,[class*="option"]');
            var itemTexts=[];
            for(var j=0;j<Math.min(10,items.length);j++){
                itemTexts.push(items[j].textContent?.trim()||'');
            }
            r.push({idx:i,className:pickers[i].className?.substring(0,50),cols:cols.length,items:items.length,itemTexts:itemTexts});
        }
    }
    return r;
})()""")
print(f"  picker: {picker}")

# 选择广西壮族自治区
print("  选择广西...")
ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t.includes('广西')){
                    items[j].click();
                    return{selected:'广西'};
                }
            }
        }
    }
    return{error:'not_found'};
})()""")
time.sleep(2)

# 检查是否出现了南宁市选项
picker2 = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            var itemTexts=[];
            for(var j=0;j<Math.min(15,items.length);j++){
                var t=items[j].textContent?.trim()||'';
                if(t&&t.length<30)itemTexts.push(t);
            }
            return{items:items.length,texts:itemTexts};
        }
    }
    return{error:'no_picker'};
})()""")
print(f"  picker2: {picker2}")

# 选择南宁市
print("  选择南宁...")
ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t.includes('南宁')&&!t.includes('广西')){
                    items[j].click();
                    return{selected:'南宁'};
                }
            }
        }
    }
    return{error:'not_found'};
})()""")
time.sleep(2)

# 选择青秀区
print("  选择青秀区...")
ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t.includes('青秀')){
                    items[j].click();
                    return{selected:'青秀区'};
                }
            }
            // 如果没有青秀区，选第一个
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t&&t.length<20&&!t.includes('广西')&&!t.includes('南宁')){
                    items[j].click();
                    return{selected:t};
                }
            }
        }
    }
    return{error:'not_found'};
})()""")
time.sleep(2)

# 检查是否还有街道选择
picker3 = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            var itemTexts=[];
            for(var j=0;j<Math.min(10,items.length);j++){
                var t=items[j].textContent?.trim()||'';
                if(t&&t.length<30)itemTexts.push(t);
            }
            return{items:items.length,texts:itemTexts};
        }
    }
    return{error:'no_picker'};
})()""")
print(f"  picker3(街道): {picker3}")

# 如果有街道，选第一个
if picker3 and picker3.get('items',0) > 0:
    ev("""(function(){
        var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
        for(var i=0;i<pickers.length;i++){
            if(pickers[i].offsetParent!==null){
                var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
                for(var j=0;j<items.length;j++){
                    var t=items[j].textContent?.trim()||'';
                    if(t&&t.length<30&&!t.includes('广西')&&!t.includes('南宁')&&!t.includes('青秀')){
                        items[j].click();
                        return{selected:t};
                    }
                }
            }
        }
    })()""")
    time.sleep(1)

# 点击确定/确认按钮
print("  确认选择...")
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,[class*="confirm"],[class*="ok"],[class*="sure"]');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('确定')||t.includes('确认')||t.includes('完成')||t.includes('保存'))&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:t};
        }
    }
    // 也检查picker内的确认按钮
    var pickers=document.querySelectorAll('.tne-data-picker');
    for(var i=0;i<pickers.length;i++){
        var pbtns=pickers[i].querySelectorAll('button,[class*="btn"],[class*="confirm"]');
        for(var j=0;j<pbtns.length;j++){
            pbtns[j].click();
            return{clicked:'picker_btn'};
        }
    }
    // 如果没有确认按钮，点击外部关闭
    document.body.click();
    return{clicked:'body'};
})()""")
time.sleep(2)

screenshot("step1_addr1")

# ===== STEP 2: 处理生产经营地址 =====
print("\nSTEP 2: 生产经营地址")
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('生产经营地址')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input)input.click();
            return;
        }
    }
})()""")
time.sleep(2)

# 同样选择广西→南宁→青秀区
print("  选择广西...")
ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            for(var j=0;j<items.length;j++){
                if(items[j].textContent?.trim()?.includes('广西')){
                    items[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(2)

print("  选择南宁...")
ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t.includes('南宁')&&!t.includes('广西')){
                    items[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(2)

print("  选择青秀区...")
ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker-viewer,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var items=pickers[i].querySelectorAll('[class*="item"],[class*="option"],li,div');
            for(var j=0;j<items.length;j++){
                if(items[j].textContent?.trim()?.includes('青秀')){
                    items[j].click();return;
                }
            }
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t&&t.length<20&&!t.includes('广西')&&!t.includes('南宁')){
                    items[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(2)

# 确认
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,[class*="confirm"]');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('确定')||t.includes('确认')||t.includes('完成'))&&btns[i].offsetParent!==null){
            btns[i].click();return;
        }
    }
    document.body.click();
})()""")
time.sleep(2)

screenshot("step2_addr2")

# ===== STEP 3: 行业类型select =====
print("\nSTEP 3: 行业类型select")
# 点击行业类型select
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input)input.click();
            return;
        }
    }
})()""")
time.sleep(2)

# 选择[I]信息传输、软件和信息技术服务业
ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null||dropdowns[i].style?.display!=='none'){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                if(t.includes('信息传输')||t.includes('软件')||t.includes('[I]')){
                    items[j].click();
                    return{selected:t.substring(0,30)};
                }
            }
        }
    }
    return{error:'not_found'};
})()""")
time.sleep(2)

screenshot("step3_industry")

# ===== STEP 4: 经营范围 =====
print("\nSTEP 4: 经营范围")
# 点击添加规范经营用语按钮
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btns=fi[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if(t.includes('添加')||t.includes('规范')){
                    btns[j].click();
                    return{clicked:t};
                }
            }
        }
    }
})()""")
time.sleep(3)

# 检查弹出的内容
scope_popup = ev("""(function(){
    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
            var title=dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'';
            var body=dialogs[i].querySelector('.el-dialog__body');
            var text=body?.innerText?.trim()?.substring(0,200)||'';
            var html=body?.innerHTML?.substring(0,300)||'';
            var inputs=body?.querySelectorAll('input,textarea,select')?.length||0;
            var btns=body?.querySelectorAll('button,.el-button')?.length||0;
            return{type:'dialog',title:title,text:text,inputs:inputs,btns:btns,html:html};
        }
    }
    // 检查drawer
    var drawers=document.querySelectorAll('.el-drawer');
    for(var i=0;i<drawers.length;i++){
        if(drawers[i].offsetParent!==null){
            return{type:'drawer',text:drawers[i].innerText?.trim()?.substring(0,200)||''};
        }
    }
    // 检查新的picker
    var pickers=document.querySelectorAll('.tne-data-picker,[class*="picker"]');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            return{type:'picker',text:pickers[i].innerText?.trim()?.substring(0,200)||''};
        }
    }
    return{type:'none'};
})()""")
print(f"  scope_popup: {scope_popup}")

if scope_popup and scope_popup.get('type') == 'dialog':
    # 在对话框中搜索并选择经营范围
    print("  处理经营范围对话框...")
    # 搜索"软件开发"
    ev("""(function(){
        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent!==null){
                var search=dialogs[i].querySelector('.el-input__inner');
                if(search){
                    var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    setter.call(search,'软件开发');
                    search.dispatchEvent(new Event('input',{bubbles:true}));
                    search.dispatchEvent(new Event('change',{bubbles:true}));
                }
            }
        }
    })()""")
    time.sleep(2)
    
    # 选择搜索结果
    ev("""(function(){
        var dialogs=document.querySelectorAll('.el-dialog__wrapper');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent!==null){
                // 找checkbox并点击
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

screenshot("step4_scope")

# ===== STEP 5: 验证 =====
print("\nSTEP 5: 保存并下一步")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if not errs:
    print("  ✅ 验证通过！")
    log("170.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤直到提交页
    print("\nSTEP 6: 遍历步骤直到提交页")
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
        print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)} hash={current.get('hash','')[:30]}")
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
            log("171.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    print(f"  ⚠️ 验证错误: {errs}")
    log("170.验证失败", {"errors":errs})

screenshot("final_result")

# ===== 最终报告 =====
print("\n" + "=" * 60)
print("E2E 测试最终报告")
print("=" * 60)
rpt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "e2e_report.json")
if os.path.exists(rpt_path):
    with open(rpt_path, "r", encoding="utf-8") as f:
        rpt = json.load(f)
    print(f"  总步骤数: {len(rpt.get('steps',[]))}")
    print(f"  问题数: {len(rpt.get('issues',[]))}")
    
    # 去重认证发现
    auth_types = set()
    for af in rpt.get('auth_findings',[]):
        if isinstance(af, dict) and af.get('auth'):
            for k, v in af['auth'].items():
                if v: auth_types.add(k)
    print(f"  认证类型: {list(auth_types)}")
    print(f"  认证发现数: {len(rpt.get('auth_findings',[]))}")
    
    log("172.E2E最终报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final13.py 完成")
