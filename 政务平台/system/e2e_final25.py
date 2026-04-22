#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final25: 刷新页面 → 完整导航 → 填表 → 行业类型 → 经营范围 → 遍历"""
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
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20)
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

# ===== PHASE 0: 刷新页面恢复SPA =====
print("PHASE 0: 刷新页面")
ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'")
time.sleep(5)

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
time.sleep(2)

# 检查首页
home = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,100)})")
print(f"  首页: hash={home.get('hash','')} text={home.get('text','')[:50]}")

# ===== PHASE 1: 导航到表单 =====
print("\nPHASE 1: 导航到表单")

# 1a. 导航到企业开办专区
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)

# 1b. 点击"开始办理"
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(3)

# 1c. 导航到select-prise
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/select-prise')})()""")
time.sleep(2)

# 1d. 调用getHandleBusiness注册动态路由
ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    function findComp(vm,depth){
        if(depth>10)return null;
        if(vm.$options?.name==='select-prise')return vm;
        var children=vm.$children||[];
        for(var i=0;i<children.length;i++){var r=findComp(children[i],depth+1);if(r)return r}
        return null;
    }
    var sp=findComp(vm,0);
    if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness();
})()""")
time.sleep(3)

# 1e. 导航到表单
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base/basic-info')})()""")
time.sleep(5)

# 验证表单加载
form_check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  form: hash={form_check.get('hash')} forms={form_check.get('formCount',0)}")

if form_check.get('formCount',0) < 10:
    print("  等待表单加载...")
    time.sleep(5)
    form_check = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  form2: hash={form_check.get('hash')} forms={form_check.get('formCount',0)}")

if form_check.get('formCount',0) < 10:
    print("  ⚠️ 表单未加载，退出")
    log("290.表单未加载", {"hash":form_check.get('hash'),"formCount":form_check.get('formCount',0)})
    ws.close()
    sys.exit(1)

# ===== PHASE 2: 填写文本字段 =====
print("\nPHASE 2: 填写文本字段")
text_fields = {
    "详细地址": "民族大道166号16号楼5层501室",
    "生产经营地详细地址": "民族大道166号16号楼5层501室",
    "邮政编码": "530022",
    "联系电话": "0771-5888888",
    "企业电子邮箱": "test@gxzhixin.com",
}
for label, val in text_fields.items():
    r = ev(f"""(function(){{var fi=document.querySelectorAll('.el-form-item');for(var i=0;i<fi.length;i++){{var lb=fi[i].querySelector('.el-form-item__label');if(lb&&lb.textContent.trim().includes('{label}')){{var input=fi[i].querySelector('.el-input__inner');if(input&&!input.disabled){{var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(input,'{val}');input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));return{{ok:true}}}}}}}}}})()""")
    if r: print(f"  ✅ {label}")

# ===== PHASE 3: 区域选择器 =====
print("\nPHASE 3: 区域选择器")

def pick_region(form_label):
    ev(f"""(function(){{var fi=document.querySelectorAll('.el-form-item');for(var i=0;i<fi.length;i++){{var lb=fi[i].querySelector('.el-form-item__label');if(lb&&lb.textContent.trim().includes('{form_label}')){{var input=fi[i].querySelector('.el-input__inner');if(input)input.click();return}}}}}})()""")
    time.sleep(2)
    ev("""(function(){var v=document.querySelector('.tne-data-picker-viewer');if(!v)return;var items=v.querySelectorAll('.tab-c .item');for(var i=0;i<items.length;i++){if(items[i].textContent?.trim()?.includes('广西')){items[i].click();return}}})()""")
    time.sleep(2)
    ev("""(function(){var v=document.querySelector('.tne-data-picker-viewer');if(!v)return;var items=v.querySelectorAll('.tab-c .item');for(var i=0;i<items.length;i++){if(items[i].textContent?.trim()?.includes('南宁')){items[i].click();return}}})()""")
    time.sleep(2)
    ev("""(function(){var v=document.querySelector('.tne-data-picker-viewer');if(!v)return;var items=v.querySelectorAll('.tab-c .item');for(var i=0;i<items.length;i++){if(items[i].textContent?.trim()?.includes('青秀')){items[i].click();return}}if(items.length>0)items[0].click()})()""")
    time.sleep(1)
    ev("document.body.click()")
    time.sleep(1)
    val = ev(f"""(function(){{var fi=document.querySelectorAll('.el-form-item');for(var i=0;i<fi.length;i++){{var lb=fi[i].querySelector('.el-form-item__label');if(lb&&lb.textContent.trim().includes('{form_label}')){{var input=fi[i].querySelector('.el-input__inner');return input?.value||''}}}}}})()""")
    print(f"  {form_label}: {val}")

pick_region("企业住所")
pick_region("生产经营地址")

# 自贸区
ev("""(function(){var fi=document.querySelectorAll('.el-form-item');for(var i=0;i<fi.length;i++){var lb=fi[i].querySelector('.el-form-item__label');if(lb&&lb.textContent.trim().includes('自贸区')){var radios=fi[i].querySelectorAll('.el-radio');for(var j=0;j<radios.length;j++){if(radios[j].textContent?.trim()?.includes('否')){radios[j].click();return}}}}})()""")
print("  自贸区: 否")
time.sleep(1)

# ===== PHASE 4: 行业类型 =====
print("\nPHASE 4: 行业类型")

# 4a. 设置namePreIndustryTypeCode
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findBDI(vm,depth){if(depth>12)return null;if(vm.$data?.businessDataInfo)return vm;var children=vm.$children||[];for(var i=0;i<children.length;i++){var r=findBDI(children[i],depth+1);if(r)return r}return null}
    var inst=findBDI(vm,0);if(!inst)return;
    var bdi=inst.$data.businessDataInfo;
    inst.$set(bdi,'namePreIndustryTypeCode','I');
    inst.$set(bdi,'namePreIndustryTypeName','信息传输、软件和信息技术服务业');
    inst.$forceUpdate();
})()""")
time.sleep(1)

# 4b. 调用getIndustryList
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,depth){if(depth>12)return null;if(vm.$options?.name===name)return vm;var children=vm.$children||[];for(var i=0;i<children.length;i++){var r=findComp(children[i],name,depth+1);if(r)return r}return null}
    var biComp=findComp(vm,'businese-info',0);
    if(biComp&&typeof biComp.getIndustryList==='function')biComp.getIndustryList();
})()""")
time.sleep(3)

# 4c. 检查select选项
opts = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var lb=fi[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('行业类型')){
            var sel=fi[i].querySelector('.el-select');var comp=sel?.__vue__;if(!comp)return null;
            var opts=comp.options||[];
            var r=[];for(var j=0;j<opts.length;j++){var o=opts[j];r.push({idx:j,label:(o.currentLabel||o.label||'').substring(0,30),value:o.currentValue||o.value||'',children:o.children?.length||0,disabled:o.disabled||false})}
            return{optCount:opts.length,opts:r,compValue:comp.value};
        }
    }
    return null;
})()""")
if opts:
    print(f"  opts: count={opts.get('optCount',0)} compValue={opts.get('compValue')}")
    for o in (opts.get('opts') or []):
        if o.get('label',''):
            print(f"    [{o.get('idx')}] {o.get('label','')[:25]} children={o.get('children',0)}")
    
    # 4d. 选择行业类型
    selected = False
    if opts.get('opts'):
        for o in opts.get('opts'):
            if o.get('label','') and not o.get('disabled') and o.get('children',0) > 0:
                idx = o.get('idx',0)
                # 选择第一个子选项
                result = ev(f"""(function(){{
                    var fi=document.querySelectorAll('.el-form-item');
                    for(var i=0;i<fi.length;i++){{
                        var lb=fi[i].querySelector('.el-form-item__label');
                        if(lb&&lb.textContent.trim().includes('行业类型')){{
                            var sel=fi[i].querySelector('.el-select');var comp=sel?.__vue__;var opts=comp?.options||[];
                            var o=opts[{idx}];
                            if(o&&o.children&&o.children.length>0){{
                                var child=o.children[0];
                                comp.handleOptionSelect(child);comp.$emit('input',child.value||child.currentValue);
                                return{{selected:(child.currentLabel||child.label||'').substring(0,20)}};
                            }}
                        }}
                    }}
                }})()""")
                print(f"  选择子项: {result}")
                selected = True
                break
            elif o.get('label','') and not o.get('disabled'):
                idx = o.get('idx',0)
                result = ev(f"""(function(){{
                    var fi=document.querySelectorAll('.el-form-item');
                    for(var i=0;i<fi.length;i++){{
                        var lb=fi[i].querySelector('.el-form-item__label');
                        if(lb&&lb.textContent.trim().includes('行业类型')){{
                            var sel=fi[i].querySelector('.el-select');var comp=sel?.__vue__;var opts=comp?.options||[];
                            if(opts[{idx}]){{comp.handleOptionSelect(opts[{idx}]);comp.$emit('input',opts[{idx}].value||opts[{idx}].currentValue);return{{selected:(opts[{idx}].currentLabel||opts[{idx}].label||'').substring(0,20)}}}}
                        }}
                    }}
                }})()""")
                print(f"  选择: {result}")
                selected = True
                break
    
    if not selected:
        print("  ⚠️ 无有效选项")
else:
    print("  ⚠️ 未找到行业类型select")

# 验证select值
sel_val = ev("""(function(){var fi=document.querySelectorAll('.el-form-item');for(var i=0;i<fi.length;i++){var lb=fi[i].querySelector('.el-form-item__label');if(lb&&lb.textContent.trim().includes('行业类型')){var input=fi[i].querySelector('.el-input__inner');return input?.value||''}}})()""")
print(f"  select显示: {sel_val}")

# ===== PHASE 5: 经营范围 =====
print("\nPHASE 5: 经营范围")

# 5a. 点击"添加规范经营用语"
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var lb=fi[i].querySelector('.el-form-item__label');
        if(lb&&(lb.textContent.trim().includes('经营范围')||lb.textContent.trim().includes('许可经营项目'))){
            var btns=fi[i].querySelectorAll('button,.el-button');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')||btns[j].textContent?.trim()?.includes('规范')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(5)

# 5b. 分析对话框
dialog = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        var text=dialogs[i].textContent?.trim()||'';
        if(text.includes('经营范围选择')){
            var body=dialogs[i].querySelector('.el-dialog__body,[class*="body"]');
            return{
                found:true,
                bodyHtmlLen:body?.innerHTML?.length||0,
                bodyTextLen:body?.innerText?.trim()?.length||0,
                bodyText:body?.innerText?.trim()?.substring(0,200)||'',
                elementCount:body?.querySelectorAll('*')?.length||0
            };
        }
    }
    return{found:false};
})()""")
print(f"  dialog: found={dialog.get('found')} htmlLen={dialog.get('bodyHtmlLen',0)} textLen={dialog.get('bodyTextLen',0)} elements={dialog.get('elementCount',0)}")

# 5c. 如果对话框为空，等待
if dialog.get('found') and dialog.get('bodyHtmlLen',0) < 50:
    print("  等待对话框加载...")
    for wait in range(5):
        time.sleep(3)
        dialog2 = ev("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
            for(var i=0;i<dialogs.length;i++){
                if(dialogs[i].textContent?.trim()?.includes('经营范围选择')){
                    var body=dialogs[i].querySelector('.el-dialog__body,[class*="body"]');
                    return{htmlLen:body?.innerHTML?.length||0,textLen:body?.innerText?.trim()?.length||0,elements:body?.querySelectorAll('*')?.length||0,text:body?.innerText?.trim()?.substring(0,100)||''};
                }
            }
            return null;
        })()""")
        if dialog2 and dialog2.get('htmlLen',0) > 50:
            dialog = dialog2
            print(f"  加载完成: htmlLen={dialog2.get('htmlLen',0)} text={dialog2.get('text','')[:50]}")
            break
        print(f"  等待{wait+1}...")

# 5d. 如果有内容，交互
if dialog.get('bodyHtmlLen',0) > 50 or dialog.get('elementCount',0) > 5:
    print("  对话框有内容，交互...")
    # 搜索
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].textContent?.trim()?.includes('经营范围选择')){
                var inputs=dialogs[i].querySelectorAll('input');
                for(var j=0;j<inputs.length;j++){
                    var ph=inputs[j].placeholder||'';
                    if(ph.includes('搜索')||ph.includes('输入')||ph.includes('查询')||inputs[j].className?.includes('search')){
                        var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                        s.call(inputs[j],'软件开发');inputs[j].dispatchEvent(new Event('input',{bubbles:true}));return;
                    }
                }
            }
        }
    })()""")
    time.sleep(3)
    
    # 选择checkbox
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].textContent?.trim()?.includes('经营范围选择')){
                var checkboxes=dialogs[i].querySelectorAll('.el-checkbox');
                for(var j=0;j<Math.min(3,checkboxes.length);j++){
                    if(!checkboxes[j].className?.includes('is-checked'))checkboxes[j].click();
                }
                var btns=dialogs[i].querySelectorAll('button,.el-button');
                for(var j=0;j<btns.length;j++){
                    var t=btns[j].textContent?.trim()||'';
                    if(t.includes('确定')||t.includes('确认')||t.includes('保存')||t.includes('添加')){btns[j].click();return}
                }
            }
        }
    })()""")
    time.sleep(3)
else:
    print("  对话框内容为空，通过Vue设置...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,depth){if(depth>12)return null;if(vm.$options?.name===name)return vm;var children=vm.$children||[];for(var i=0;i<children.length;i++){var r=findComp(children[i],name,depth+1);if(r)return r}return null}
        var biComp=findComp(vm,'businese-info',0);
        if(!biComp)return;
        var data=biComp.$data;
        for(var k in data){
            var kl=k.toLowerCase();
            if((kl==='genbusiarea'||kl==='businessarea')&&typeof data[k]==='string'){
                biComp.$set(data,k,'软件开发;信息技术咨询服务;数据处理和存储支持服务');
            }
        }
        biComp.$forceUpdate();
    })()""")
    time.sleep(2)

screenshot("phase5_scope")

# ===== PHASE 6: 验证 =====
print("\nPHASE 6: 验证")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

if errs:
    print(f"  ⚠️ 验证错误: {errs}")
    log("290.验证失败", {"errors":errs,"hash":page.get('hash')})
    
    # 清除验证并重试
    ev("""(function(){var forms=document.querySelectorAll('.el-form');for(var i=0;i<forms.length;i++){var comp=forms[i].__vue__;if(comp&&typeof comp.clearValidate==='function')comp.clearValidate()}})()""")
    time.sleep(1)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(5)
    errs2 = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
    page2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  清除后: errors={errs2} hash={page2.get('hash')} forms={page2.get('formCount',0)}")
    if not errs2: errs = errs2; page = page2

if not errs:
    print("  ✅ 验证通过！")
    log("290.验证通过", {"hash":page.get('hash'),"formCount":page.get('formCount',0)})
    
    # ===== PHASE 7: 遍历步骤 =====
    print("\nPHASE 7: 遍历步骤到提交页")
    for step in range(12):
        current = ev("""(function(){
            var steps=document.querySelectorAll('.el-step');var active=null;
            for(var i=0;i<steps.length;i++){if(steps[i].className?.includes('is-active')){active={i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||''};break}}
            var btns=Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20});
            var hasSubmit=btns.some(function(t){return t.includes('提交')&&!t.includes('暂存')});
            return{step:active,hasSubmit:hasSubmit,buttons:btns.filter(function(t){return t.includes('下一步')||t.includes('提交')||t.includes('保存')||t.includes('暂存')||t.includes('预览')}).slice(0,5),formCount:document.querySelectorAll('.el-form-item').length,hash:location.hash};
        })()""")
        step_info = current.get('step') or {}
        print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)}")
        print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
        
        auth=ev("""(function(){var t=document.body.innerText||'';var html=document.body.innerHTML||'';return{faceAuth:t.includes('人脸')||html.includes('faceAuth'),smsAuth:t.includes('验证码')||t.includes('短信'),realName:t.includes('实名认证')||t.includes('实名'),signAuth:t.includes('电子签名')||t.includes('电子签章')||t.includes('签章'),digitalCert:t.includes('数字证书')||t.includes('CA锁'),caAuth:t.includes('CA认证')||html.includes('caAuth'),ukeyAuth:t.includes('UKey')||t.includes('U盾')}})()""")
        if any(auth.values() if auth else []):
            print(f"  ⚠️ 认证: {auth}")
            add_auth_finding({"step":step,"title":step_info.get('title',''),"auth":auth})
        
        if current.get('hasSubmit'):
            print(f"\n  🔴 提交按钮！停止")
            log("291.提交按钮", {"step":step,"auth":auth,"buttons":current.get('buttons',[])})
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
    log("292.E2E报告", {"totalSteps":len(rpt.get('steps',[])),"authTypes":list(auth_types),"issues":len(rpt.get('issues',[])),"lastErrors":errs})

ws.close()
print("\n✅ e2e_final25.py 完成")
