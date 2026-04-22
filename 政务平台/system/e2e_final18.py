#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final18: 经营范围选择对话框(tni-dialog) + 行业类型懒加载select"""
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

# ===== STEP 1: 分析经营范围选择对话框 =====
print("STEP 1: 经营范围选择对话框")
scope_dialog = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
    for(var i=0;i<dialogs.length;i++){
        var text=dialogs[i].textContent?.trim()||'';
        if(text.includes('经营范围选择')){
            var html=dialogs[i].innerHTML.substring(0,500);
            var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
            var bodyHtml=body?.innerHTML?.substring(0,500)||'';
            var bodyText=body?.innerText?.trim()?.substring(0,200)||'';
            var inputs=body?.querySelectorAll('input,textarea,select')||[];
            var btns=body?.querySelectorAll('button,.el-button')||[];
            var checkboxes=body?.querySelectorAll('.el-checkbox')||[];
            var tables=body?.querySelectorAll('table,.el-table')||[];
            var trees=body?.querySelectorAll('.el-tree,[class*="tree"]')||[];
            var tabs=body?.querySelectorAll('.el-tabs,[class*="tab"]')||[];
            
            // 找所有可交互元素
            var interactives=body?.querySelectorAll('[class*="item"],[class*="node"],[class*="option"],[class*="select"],[class*="check"]')||[];
            var interactiveInfo=[];
            for(var j=0;j<Math.min(10,interactives.length);j++){
                interactiveInfo.push({class:interactives[j].className?.substring(0,40)||'',text:interactives[j].textContent?.trim()?.substring(0,20)||''});
            }
            
            return{
                found:true,
                bodyText:bodyText,
                inputCount:inputs.length,
                btnCount:btns.length,
                checkboxCount:checkboxes.length,
                tableCount:tables.length,
                treeCount:trees.length,
                tabCount:tabs.length,
                interactiveCount:interactives.length,
                interactiveInfo:interactiveInfo,
                bodyHtml:bodyHtml
            };
        }
    }
    return{found:false};
})()""")
print(f"  found: {scope_dialog.get('found')}")
if scope_dialog.get('found'):
    print(f"  bodyText: {scope_dialog.get('bodyText','')[:100]}")
    print(f"  inputs: {scope_dialog.get('inputCount',0)} btns: {scope_dialog.get('btnCount',0)} checkboxes: {scope_dialog.get('checkboxCount',0)}")
    print(f"  tables: {scope_dialog.get('tableCount',0)} trees: {scope_dialog.get('treeCount',0)} tabs: {scope_dialog.get('tabCount',0)}")
    print(f"  interactives: {scope_dialog.get('interactiveCount',0)}")
    print(f"  interactiveInfo: {scope_dialog.get('interactiveInfo',[])}")
    print(f"  bodyHtml: {scope_dialog.get('bodyHtml','')[:200]}")

# ===== STEP 2: 在经营范围对话框中搜索并选择 =====
print("\nSTEP 2: 经营范围搜索选择")
if scope_dialog.get('found'):
    # 查找搜索框
    search_result = ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var text=dialogs[i].textContent?.trim()||'';
            if(text.includes('经营范围选择')){
                var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
                if(!body)continue;
                
                // 找搜索输入框
                var inputs=body.querySelectorAll('input');
                var inputInfo=[];
                for(var j=0;j<inputs.length;j++){
                    inputInfo.push({idx:j,ph:inputs[j].placeholder||'',type:inputs[j].type||'',val:inputs[j].value||'',class:inputs[j].className?.substring(0,30)||''});
                }
                
                // 找所有按钮
                var btns=body.querySelectorAll('button,.el-button,[class*="btn"]');
                var btnInfo=[];
                for(var j=0;j<btns.length;j++){
                    btnInfo.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,20)||'',class:btns[j].className?.substring(0,30)||''});
                }
                
                // 找树形结构
                var trees=body.querySelectorAll('.el-tree,[class*="tree"]');
                var treeInfo=[];
                for(var j=0;j<trees.length;j++){
                    var nodes=trees[j].querySelectorAll('.el-tree-node,[class*="node"]');
                    treeInfo.push({nodeCount:nodes.length,firstNodes:Array.from(nodes).slice(0,5).map(function(n){return n.textContent?.trim()?.substring(0,20)})});
                }
                
                // 找tne-data-picker
                var pickers=body.querySelectorAll('.tne-data-picker,[class*="picker"]');
                var pickerInfo=[];
                for(var j=0;j<pickers.length;j++){
                    pickerInfo.push({idx:j,text:pickers[j].textContent?.trim()?.substring(0,50)||'',class:pickers[j].className?.substring(0,30)||''});
                }
                
                return{inputInfo:inputInfo,btnInfo:btnInfo,treeInfo:treeInfo,pickerInfo:pickerInfo};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  search: {search_result}")
    
    # 如果有搜索框，搜索"软件开发"
    if search_result and search_result.get('inputInfo'):
        for inp in search_result.get('inputInfo',[]):
            if '搜索' in inp.get('ph','') or '输入' in inp.get('ph','') or '查询' in inp.get('ph',''):
                idx = inp.get('idx',0)
                print(f"  搜索框 #{idx}: ph={inp.get('ph','')}")
                ev(f"""(function(){{
                    var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
                    for(var i=0;i<dialogs.length;i++){{
                        if(dialogs[i].textContent?.trim()?.includes('经营范围选择')){{
                            var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
                            var inputs=body?.querySelectorAll('input');
                            if(inputs[{idx}]){{
                                var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                                setter.call(inputs[{idx}],'软件开发');
                                inputs[{idx}].dispatchEvent(new Event('input',{{bubbles:true}}));
                                inputs[{idx}].dispatchEvent(new Event('change',{{bubbles:true}}));
                            }}
                        }}
                    }}
                }})()""")
                time.sleep(2)
                break
    
    # 如果有树，选择节点
    if search_result and search_result.get('treeInfo'):
        for tree in search_result.get('treeInfo',[]):
            if tree.get('nodeCount',0) > 0:
                print(f"  树节点: {tree.get('firstNodes',[])}")
                # 点击包含"软件"的节点
                ev("""(function(){
                    var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
                    for(var i=0;i<dialogs.length;i++){
                        if(dialogs[i].textContent?.trim()?.includes('经营范围选择')){
                            var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
                            var nodes=body?.querySelectorAll('.el-tree-node,[class*="node"]');
                            for(var j=0;j<(nodes?.length||0);j++){
                                var t=nodes[j].textContent?.trim()||'';
                                if(t.includes('软件')||t.includes('信息')){
                                    nodes[j].click();
                                    return{clicked:t.substring(0,20)};
                                }
                            }
                            // 没找到就点第一个
                            if(nodes&&nodes.length>0){
                                nodes[0].click();
                                return{clicked:'first'};
                            }
                        }
                    }
                })()""")
                time.sleep(2)
    
    # 如果有picker，选择
    if search_result and search_result.get('pickerInfo'):
        for pk in search_result.get('pickerInfo',[]):
            if pk.get('text',''):
                print(f"  picker: {pk.get('text','')[:30]}")
    
    # 点击确认按钮
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].textContent?.trim()?.includes('经营范围选择')){
                var btns=dialogs[i].querySelectorAll('button,.el-button,[class*="btn"]');
                for(var j=0;j<btns.length;j++){
                    var t=btns[j].textContent?.trim()||'';
                    if(t.includes('确定')||t.includes('确认')||t.includes('保存')||t.includes('添加')){
                        btns[j].click();
                        return{clicked:t};
                    }
                }
            }
        }
    })()""")
    time.sleep(2)

screenshot("step2_scope")

# ===== STEP 3: 行业类型 - 触发懒加载 =====
print("\nSTEP 3: 行业类型")
# 先关闭可能残留的dropdown
ev("document.body.click()")
time.sleep(1)

# 点击行业类型select触发懒加载
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input){
                input.click();
                input.focus();
                input.dispatchEvent(new Event('focus',{bubbles:true}));
            }
        }
    }
})()""")
time.sleep(3)

# 检查select组件的options是否已加载
sel_options = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');
            var comp=sel?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            var opts=comp.options||comp.cachedOptions||[];
            var optInfo=[];
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                var label2=o.currentLabel||o.label||'';
                var val=o.currentValue||o.value||'';
                var hasChildren=!!(o.children&&o.children.length>0);
                optInfo.push({idx:j,label:label2.substring(0,30),value:val,hasChildren:hasChildren,childCount:o.children?.length||0,disabled:o.disabled||false});
            }
            
            // 也检查dropdown
            var dropdown=document.querySelector('.el-select-dropdown');
            var dropdownItems=dropdown?.querySelectorAll('.el-select-dropdown__item')||[];
            var dropdownInfo=[];
            for(var j=0;j<dropdownItems.length;j++){
                dropdownInfo.push({idx:j,text:dropdownItems[j].textContent?.trim()?.substring(0,40)||'',disabled:dropdownItems[j].className?.includes('disabled'),group:dropdownItems[j].className?.includes('group')});
            }
            
            return{optCount:opts.length,optInfo:optInfo,dropdownCount:dropdownItems.length,dropdownInfo:dropdownInfo,value:comp.value,visible:comp.visible};
        }
    }
})()""")
print(f"  options: count={sel_options.get('optCount',0)}")
for o in (sel_options.get('optInfo') or []):
    print(f"    [{o.get('idx')}] {o.get('label','')[:25]} val={o.get('value','')} children={o.get('childCount',0)} disabled={o.get('disabled')}")
print(f"  dropdown: count={sel_options.get('dropdownCount',0)}")
for d in (sel_options.get('dropdownInfo') or []):
    print(f"    [{d.get('idx')}] {d.get('text','')[:30]} disabled={d.get('disabled')} group={d.get('group')}")

# 如果dropdown有可见选项，选择[I]
if sel_options.get('dropdownCount',0) > 0:
    for d in (sel_options.get('dropdownInfo') or []):
        if not d.get('disabled') and '[I]' in d.get('text',''):
            idx = d.get('idx',0)
            print(f"  选择: {d.get('text','')[:30]}")
            ev(f"""(function(){{
                var dropdown=document.querySelector('.el-select-dropdown');
                var items=dropdown?.querySelectorAll('.el-select-dropdown__item');
                if(items[{idx}])items[{idx}].click();
            }})()""")
            time.sleep(2)
            
            # 检查是否展开了子选项
            sub = ev("""(function(){
                var dropdown=document.querySelector('.el-select-dropdown');
                var items=dropdown?.querySelectorAll('.el-select-dropdown__item')||[];
                var r=[];
                for(var i=0;i<items.length;i++){
                    r.push({idx:i,text:items[i].textContent?.trim()?.substring(0,30)||'',disabled:items[i].className?.includes('disabled'),group:items[i].className?.includes('group')});
                }
                return{count:items.length,items:r.slice(0,10)};
            })()""")
            print(f"  sub: {sub}")
            
            # 选择子选项
            if sub and sub.get('count',0) > 0:
                for s in sub.get('items',[]):
                    if not s.get('disabled') and not s.get('group') and s.get('text',''):
                        sidx = s.get('idx',0)
                        print(f"  选择子项: {s.get('text','')[:20]}")
                        ev(f"""(function(){{
                            var dropdown=document.querySelector('.el-select-dropdown');
                            var items=dropdown?.querySelectorAll('.el-select-dropdown__item');
                            if(items[{sidx}])items[{sidx}].click();
                        }})()""")
                        time.sleep(1)
                        break
            break

# 如果选项仍然为空，通过Vue组件的remoteMethod触发加载
if sel_options.get('optCount',0) <= 4:
    print("  选项为空，尝试触发远程加载...")
    ev("""(function(){
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('行业类型')){
                var sel=fi[i].querySelector('.el-select');
                var comp=sel?.__vue__;
                if(comp){
                    // 触发remoteMethod
                    if(typeof comp.remoteMethod==='function'){
                        comp.remoteMethod('');
                    }
                    // 触发handleQueryChange
                    if(typeof comp.handleQueryChange==='function'){
                        comp.handleQueryChange('');
                    }
                    // 触发debouncedOnInputChange
                    if(typeof comp.debouncedOnInputChange==='function'){
                        comp.debouncedOnInputChange('');
                    }
                    // 设置filterable并搜索
                    comp.query='';
                    comp.$emit('querychange','');
                }
            }
        }
    })()""")
    time.sleep(3)
    
    # 再次检查
    sel2 = ev("""(function(){
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('行业类型')){
                var sel=fi[i].querySelector('.el-select');
                var comp=sel?.__vue__;
                var opts=comp?.options||comp?.cachedOptions||[];
                return{optCount:opts.length,first3:opts.slice(0,3).map(function(o){return{l:(o.currentLabel||o.label||'').substring(0,20),v:o.currentValue||o.value||'',c:o.children?.length||0}})};
            }
        }
    })()""")
    print(f"  sel2: {sel2}")

# 关闭dropdown
ev("document.body.click()")
time.sleep(1)

# ===== STEP 4: 验证 =====
print("\nSTEP 4: 验证")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if not errs:
    print("  ✅ 验证通过！")
    log("220.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
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
            print(f"\n  🔴 提交按钮！停止")
            log("221.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    log("220.验证失败", {"errors":errs})

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
    log("222.E2E最终报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final18.py 完成")
