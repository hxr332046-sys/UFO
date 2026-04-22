#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final15: 按tne-data-picker DOM结构精确选择 → 广西→南宁→青秀区 → 行业类型 → 经营范围"""
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

def pick_region(form_label):
    """在tne-data-picker中选择 广西→南宁→青秀区"""
    print(f"\n  选择区域: {form_label}")
    
    # 点击input触发picker
    ev(f"""(function(){{
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){{
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('{form_label}')){{
                var input=fi[i].querySelector('.el-input__inner');
                if(input)input.click();
                return;
            }}
        }}
    }})()""")
    time.sleep(2)
    
    # 选择广西 - 点击.tab-c .item
    print("    选择广西...")
    r1 = ev("""(function(){
        var viewer=document.querySelector('.tne-data-picker-viewer');
        if(!viewer)return{error:'no_viewer'};
        var items=viewer.querySelectorAll('.tab-c .item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('广西')){
                items[i].click();
                return{clicked:t.substring(0,10)};
            }
        }
        return{error:'no_guangxi',itemCount:items.length};
    })()""")
    print(f"    广西: {r1}")
    time.sleep(2)
    
    # 选择南宁 - picker已更新，现在显示市级选项
    print("    选择南宁...")
    r2 = ev("""(function(){
        var viewer=document.querySelector('.tne-data-picker-viewer');
        if(!viewer)return{error:'no_viewer'};
        var items=viewer.querySelectorAll('.tab-c .item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('南宁')){
                items[i].click();
                return{clicked:t.substring(0,10)};
            }
        }
        return{error:'no_nanning',itemCount:items.length,first3:Array.from(items).slice(0,3).map(function(x){return x.textContent?.trim()?.substring(0,15)})};
    })()""")
    print(f"    南宁: {r2}")
    time.sleep(2)
    
    # 选择青秀区
    print("    选择青秀区...")
    r3 = ev("""(function(){
        var viewer=document.querySelector('.tne-data-picker-viewer');
        if(!viewer)return{error:'no_viewer'};
        var items=viewer.querySelectorAll('.tab-c .item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('青秀')){
                items[i].click();
                return{clicked:t.substring(0,10)};
            }
        }
        // 如果没有青秀区，选第一个
        if(items.length>0){
            items[0].click();
            return{clicked:items[0].textContent?.trim()?.substring(0,10)};
        }
        return{error:'no_district',itemCount:items.length};
    })()""")
    print(f"    青秀区: {r3}")
    time.sleep(2)
    
    # 检查是否还有街道级别
    r4 = ev("""(function(){
        var viewer=document.querySelector('.tne-data-picker-viewer');
        if(!viewer)return{error:'no_viewer'};
        var selectedList=viewer.querySelector('.selected-list');
        var selectedItems=selectedList?.querySelectorAll('.selected-item')||[];
        var texts=[];
        for(var i=0;i<selectedItems.length;i++){
            texts.push(selectedItems[i].textContent?.trim()||'');
        }
        var tabItems=viewer.querySelectorAll('.tab-c .item');
        var tabTexts=Array.from(tabItems).slice(0,5).map(function(x){return x.textContent?.trim()?.substring(0,15)});
        return{selectedTexts:texts,tabItemCount:tabItems.length,tabTexts:tabTexts};
    })()""")
    print(f"    当前选择: {r4}")
    
    # 如果有街道选项，选第一个
    if r4 and r4.get('tabItemCount',0) > 0:
        print("    选择街道...")
        ev("""(function(){
            var viewer=document.querySelector('.tne-data-picker-viewer');
            var items=viewer?.querySelectorAll('.tab-c .item');
            if(items&&items.length>0)items[0].click();
        })()""")
        time.sleep(1)
    
    # 确认 - 找确认按钮或点击外部
    ev("""(function(){
        // 找picker的确认按钮
        var picker=document.querySelector('.tne-data-picker');
        var btns=picker?.querySelectorAll('button,[class*="confirm"],[class*="ok"],[class*="sure"]');
        if(btns){
            for(var i=0;i<btns.length;i++){
                var t=btns[i].textContent?.trim()||'';
                if(t.includes('确定')||t.includes('确认')||t.includes('完成')){
                    btns[i].click();return;
                }
            }
        }
        // 没有确认按钮，点击外部关闭
        document.body.click();
    })()""")
    time.sleep(2)
    
    # 验证input值
    val = ev(f"""(function(){{
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){{
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('{form_label}')){{
                var input=fi[i].querySelector('.el-input__inner');
                return{{value:input?.value||'',ph:input?.placeholder||''}};
            }}
        }}
    }})()""")
    print(f"    结果: {val}")

# ===== STEP 1: 企业住所 =====
print("STEP 1: 企业住所")
pick_region("企业住所")
screenshot("step1_domicile")

# ===== STEP 2: 生产经营地址 =====
print("\nSTEP 2: 生产经营地址")
pick_region("生产经营地址")
screenshot("step2_business_addr")

# ===== STEP 3: 行业类型 =====
print("\nSTEP 3: 行业类型")
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

# 分析dropdown - 它可能是分组select
dropdown = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            var r=[];
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                var cls=items[j].className||'';
                var disabled=cls.includes('disabled');
                var isGroup=cls.includes('group')||t.startsWith('[');
                r.push({idx:j,text:t.substring(0,50),disabled:disabled,isGroup:isGroup});
            }
            return{visible:true,items:r};
        }
    }
    return{visible:false};
})()""")
print(f"  dropdown: {dropdown}")

# 选择非disabled的选项
if dropdown and dropdown.get('visible'):
    for item in dropdown.get('items',[]):
        if not item.get('disabled') and not item.get('isGroup') and item.get('text',''):
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
        # 如果所有选项都是group，点击[I]选项
        for item in dropdown.get('items',[]):
            if '[I]' in item.get('text','') and not item.get('disabled'):
                idx = item.get('idx',0)
                print(f"  选择group: {item.get('text','')[:30]}")
                ev(f"""(function(){{
                    var dropdowns=document.querySelectorAll('.el-select-dropdown');
                    for(var i=0;i<dropdowns.length;i++){{
                        if(dropdowns[i].offsetParent!==null){{
                            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
                            if(items[{idx}])items[{idx}].click();
                        }}
                    }}
                }})()""")
                time.sleep(2)
                
                # 可能弹出子select
                sub_dropdown = ev("""(function(){
                    var dropdowns=document.querySelectorAll('.el-select-dropdown');
                    for(var i=0;i<dropdowns.length;i++){
                        if(dropdowns[i].offsetParent!==null){
                            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
                            var r=[];
                            for(var j=0;j<Math.min(10,items.length);j++){
                                r.push({idx:j,text:items[j].textContent?.trim()?.substring(0,30)||'',disabled:items[j].className?.includes('disabled')});
                            }
                            return{items:r};
                        }
                    }
                    return{error:'no_sub'};
                })()""")
                print(f"  sub_dropdown: {sub_dropdown}")
                
                # 选第一个非disabled
                if sub_dropdown and sub_dropdown.get('items'):
                    for si in sub_dropdown.get('items',[]):
                        if not si.get('disabled') and si.get('text',''):
                            sidx = si.get('idx',0)
                            ev(f"""(function(){{
                                var dropdowns=document.querySelectorAll('.el-select-dropdown');
                                for(var i=0;i<dropdowns.length;i++){{
                                    if(dropdowns[i].offsetParent!==null){{
                                        var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
                                        if(items[{sidx}])items[{sidx}].click();
                                    }}
                                }}
                            }})()""")
                            time.sleep(1)
                            break
                break

screenshot("step3_industry")

# ===== STEP 4: 经营范围 =====
print("\nSTEP 4: 经营范围")
# 点击添加按钮
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btns=fi[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')||btns[j].textContent?.trim()?.includes('规范')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(3)

# 检查弹出的picker
scope = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker');
    for(var i=0;i<pickers.length;i++){
        var viewer=pickers[i].querySelector('.tne-data-picker-viewer');
        if(viewer&&viewer.offsetParent!==null){
            var text=viewer.textContent?.trim()?.substring(0,100)||'';
            var items=viewer.querySelectorAll('.tab-c .item');
            var itemTexts=Array.from(items).slice(0,5).map(function(x){return x.textContent?.trim()?.substring(0,20)});
            return{visible:true,text:text,itemCount:items.length,itemTexts:itemTexts};
        }
    }
    // 检查dialog
    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null){
            return{type:'dialog',title:dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'',text:dialogs[i].querySelector('.el-dialog__body')?.textContent?.trim()?.substring(0,100)||''};
        }
    }
    return{type:'none'};
})()""")
print(f"  scope: {scope}")

if scope and scope.get('visible'):
    # 在picker中选择经营范围
    # 选择[I]信息传输、软件和信息技术服务业
    print("  选择行业分类...")
    ev("""(function(){
        var pickers=document.querySelectorAll('.tne-data-picker');
        for(var i=0;i<pickers.length;i++){
            var viewer=pickers[i].querySelector('.tne-data-picker-viewer');
            if(viewer&&viewer.offsetParent!==null){
                var items=viewer.querySelectorAll('.tab-c .item');
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
    
    # 选择子分类
    scope2 = ev("""(function(){
        var pickers=document.querySelectorAll('.tne-data-picker');
        for(var i=0;i<pickers.length;i++){
            var viewer=pickers[i].querySelector('.tne-data-picker-viewer');
            if(viewer&&viewer.offsetParent!==null){
                var items=viewer.querySelectorAll('.tab-c .item');
                var itemTexts=Array.from(items).slice(0,5).map(function(x){return x.textContent?.trim()?.substring(0,20)});
                return{itemCount:items.length,itemTexts:itemTexts};
            }
        }
    })()""")
    print(f"  scope2: {scope2}")
    
    if scope2 and scope2.get('itemCount',0) > 0:
        # 选择"软件开发"
        ev("""(function(){
            var pickers=document.querySelectorAll('.tne-data-picker');
            for(var i=0;i<pickers.length;i++){
                var viewer=pickers[i].querySelector('.tne-data-picker-viewer');
                if(viewer&&viewer.offsetParent!==null){
                    var items=viewer.querySelectorAll('.tab-c .item');
                    for(var j=0;j<items.length;j++){
                        var t=items[j].textContent?.trim()||'';
                        if(t.includes('软件开发')){
                            items[j].click();return{clicked:t.substring(0,20)};
                        }
                    }
                    // 没找到就选第一个
                    if(items.length>0)items[0].click();
                }
            }
        })()""")
        time.sleep(2)
    
    # 确认
    ev("""(function(){
        var picker=document.querySelector('.tne-data-picker');
        var btns=picker?.querySelectorAll('button,[class*="confirm"],[class*="ok"]');
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
    print("  ✅ 验证通过！进入下一步")
    log("190.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # 遍历步骤
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
            print(f"\n  🔴 提交按钮！停止")
            log("191.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    log("190.验证失败", {"errors":errs})

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
    log("192.E2E最终报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final15.py 完成")
