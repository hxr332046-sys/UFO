#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final17: 行业类型分组select精确选择 + 经营范围iframe CDP访问"""
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

# ===== STEP 1: 分析行业类型select的Vue组件选项树 =====
print("STEP 1: 分析行业类型select选项树")
sel_tree = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');
            var comp=sel?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 获取完整选项树
            var opts=comp.options||comp.cachedOptions||[];
            var tree=[];
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                var item={
                    label:o.currentLabel||o.label||'',
                    value:o.currentValue||o.value||'',
                    disabled:o.disabled||false,
                    group:!!o.children,
                    childrenCount:o.children?.length||0
                };
                // 如果是group，列出子选项
                if(o.children&&o.children.length>0){
                    item.children=o.children.slice(0,3).map(function(c){
                        return{label:c.currentLabel||c.label||'',value:c.currentValue||c.value||'',disabled:c.disabled||false};
                    });
                }
                tree.push(item);
            }
            return{optCount:opts.length,tree:tree,compName:comp.$options?.name||'',value:comp.value};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  optCount: {sel_tree.get('optCount',0)} value: {sel_tree.get('value')}")
for t in (sel_tree.get('tree') or []):
    if t.get('group'):
        print(f"  GROUP: {t.get('label','')[:30]} children={t.get('childrenCount',0)}")
        for c in (t.get('children') or []):
            print(f"    child: {c.get('label','')[:30]} val={c.get('value','')} disabled={c.get('disabled')}")
    else:
        print(f"  LEAF: {t.get('label','')[:30]} val={t.get('value','')} disabled={t.get('disabled')}")

# ===== STEP 2: 通过Vue组件选择行业类型 =====
print("\nSTEP 2: 选择行业类型")
# 找到[I]分组的子选项并选择
sel_result = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');
            var comp=sel?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            var opts=comp.options||comp.cachedOptions||[];
            // 找[I]分组
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                var oLabel=o.currentLabel||o.label||'';
                if(oLabel.includes('[I]')&&o.children){
                    // 找"信息传输"子选项
                    for(var k=0;k<o.children.length;k++){
                        var child=o.children[k];
                        var cLabel=child.currentLabel||child.label||'';
                        if(cLabel.includes('信息传输')||cLabel.includes('软件')){
                            // 选择这个子选项
                            comp.handleOptionSelect(child);
                            return{selected:cLabel.substring(0,30),value:child.currentValue||child.value};
                        }
                    }
                    // 没找到就选第一个子选项
                    if(o.children.length>0){
                        var child=o.children[0];
                        comp.handleOptionSelect(child);
                        return{selected:'first_child',value:child.currentValue||child.value,label:(child.currentLabel||child.label||'').substring(0,30)};
                    }
                }
            }
            
            // 如果没有分组结构，直接找[I]选项
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                var oLabel=o.currentLabel||o.label||'';
                if(oLabel.includes('信息传输')||oLabel.includes('软件')){
                    comp.handleOptionSelect(o);
                    return{selected:oLabel.substring(0,30),value:o.currentValue||o.value};
                }
            }
            
            return{error:'no_match',optCount:opts.length};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  sel_result: {sel_result}")
time.sleep(2)

# 验证select值
sel_val = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            return{value:input?.value||''};
        }
    }
})()""")
print(f"  select显示值: {sel_val}")

# ===== STEP 3: 经营范围 - 通过CDP iframe上下文 =====
print("\nSTEP 3: 经营范围iframe")
# 先点击添加按钮
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

# 检查iframe
iframe_check = ev("""(function(){
    var iframes=document.querySelectorAll('iframe');
    var r=[];
    for(var i=0;i<iframes.length;i++){
        r.push({idx:i,src:iframes[i].src||'',id:iframes[i].id||'',name:iframes[i].name||'',visible:iframes[i].offsetParent!==null});
    }
    // 也检查tne-dialog
    var dialogs=document.querySelectorAll('.tne-dialog,[class*="dialog"]');
    var visibleDialogs=[];
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null){
            visibleDialogs.push({idx:i,class:dialogs[i].className?.substring(0,50),text:dialogs[i].textContent?.trim()?.substring(0,100)});
        }
    }
    return{iframes:r,visibleDialogs:visibleDialogs};
})()""")
print(f"  iframe_check: {iframe_check}")

# 尝试通过CDD访问iframe
# 先获取所有targets（包括iframe）
all_targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
iframe_targets = [t for t in all_targets if t.get("type") == "iframe"]
print(f"  iframe targets: {len(iframe_targets)}")
for t in iframe_targets:
    print(f"    {t.get('title','')[:30]} {t.get('url','')[:50]}")

# 如果有iframe target，连接并操作
if iframe_targets:
    iframe_ws_url = iframe_targets[0]["webSocketDebuggerUrl"]
    iframe_ws = websocket.create_connection(iframe_ws_url, timeout=30)
    
    def ev_iframe(js):
        iframe_ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":10000}}))
        for _ in range(10):
            try:
                iframe_ws.settimeout(10)
                r = json.loads(iframe_ws.recv())
                if r.get("id") == 1:
                    return r.get("result",{}).get("result",{}).get("value")
            except:
                return None
        return None
    
    # 检查iframe内容
    iframe_content = ev_iframe("""(function(){
        return{
            url:location.href,
            title:document.title,
            text:(document.body?.innerText||'').substring(0,200),
            html:(document.body?.innerHTML||'').substring(0,300)
        };
    })()""")
    print(f"  iframe content: {iframe_content}")
    
    # 如果iframe是经营范围选择器
    if iframe_content and '经营范围' in (iframe_content.get('text','') + iframe_content.get('html','')):
        print("  在iframe中选择经营范围...")
        # 搜索"软件开发"
        ev_iframe("""(function(){
            var search=document.querySelector('.el-input__inner,input[type="text"]');
            if(search){
                var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                setter.call(search,'软件开发');
                search.dispatchEvent(new Event('input',{bubbles:true}));
                search.dispatchEvent(new Event('change',{bubbles:true}));
            }
        })()""")
        time.sleep(2)
        
        # 选择搜索结果
        ev_iframe("""(function(){
            var checkboxes=document.querySelectorAll('.el-checkbox');
            for(var i=0;i<Math.min(3,checkboxes.length);i++){
                if(!checkboxes[i].className?.includes('is-checked'))checkboxes[i].click();
            }
            // 点击确定
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].textContent?.trim()?.includes('确定')||btns[i].textContent?.trim()?.includes('确认')){
                    btns[i].click();return;
                }
            }
        })()""")
        time.sleep(2)
    
    iframe_ws.close()
else:
    # 如果没有iframe target，尝试通过主页面访问iframe contentWindow
    print("  尝试通过contentWindow访问iframe...")
    iframe_access = ev("""(function(){
        var iframes=document.querySelectorAll('iframe');
        for(var i=0;i<iframes.length;i++){
            try{
                var doc=iframes[i].contentDocument||iframes[i].contentWindow?.document;
                if(doc){
                    return{accessible:true,text:(doc.body?.innerText||'').substring(0,200),html:(doc.body?.innerHTML||'').substring(0,300)};
                }
            }catch(e){
                return{accessible:false,error:e.message,src:iframes[i].src};
            }
        }
        return{error:'no_iframe'};
    })()""")
    print(f"  iframe_access: {iframe_access}")

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
    log("210.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
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
            log("211.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    log("210.验证失败", {"errors":errs})

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
    log("212.E2E最终报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final17.py 完成")
