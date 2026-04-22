#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final7: 处理级联选择器 + 填写所有必填字段 + 遍历步骤到提交页"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import load as load_report, log, add_auth_finding

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

# ===== STEP 1: 恢复token =====
print("STEP 1: 恢复token")
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

diag = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    text:(document.body.innerText||'').substring(0,60)};
})()""")
print(f"  hash={diag.get('hash')} forms={diag.get('formCount',0)} inputs={diag.get('inputCount',0)}")

if diag.get('formCount',0) == 0:
    print("  ❌ 无表单！")
    ws.close(); sys.exit(1)

# ===== STEP 2: 分析级联选择器 =====
print("\nSTEP 2: 分析级联选择器")
cascaders = ev("""(function(){
    var cas=document.querySelectorAll('.el-cascader');
    var r=[];
    for(var i=0;i<cas.length;i++){
        var fi=cas[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=cas[i].querySelector('.el-input__inner');
        var ph=input?.placeholder||'';
        var val=input?.value||'';
        r.push({i:i,label:label,ph:ph,val:val,required:fi?.className?.includes('is-required')||false});
    }
    return r;
})()""")
print(f"  cascaders: {cascaders}")

# ===== STEP 3: 处理级联选择器（选择广西/南宁/青秀区）=====
print("\nSTEP 3: 处理级联选择器")
for idx, cas in enumerate(cascaders or []):
    if cas.get('required') or cas.get('label','').includes('住所') or cas.get('label','').includes('地址'):
        print(f"  处理 cascader #{idx}: {cas.get('label','')}")
        # 点击cascader展开
        click_result = ev(f"""(function(){{
            var cas=document.querySelectorAll('.el-cascader');
            if(cas[{idx}]){{
                var input=cas[{idx}].querySelector('.el-input__inner');
                if(input)input.click();
                return{{clicked:true}};
            }}
            return{{clicked:false}};
        }})()""")
        time.sleep(1)
        
        # 选择第一级：广西壮族自治区
        ev("""(function(){
            var panels=document.querySelectorAll('.el-cascader-menu');
            if(panels.length>0){
                var items=panels[0].querySelectorAll('.el-cascader-node');
                for(var i=0;i<items.length;i++){
                    if(items[i].textContent?.trim()?.includes('广西')){
                        items[i].click();
                        return{selected:'广西'};
                    }
                }
            }
            return{error:'no_guangxi'};
        })()""")
        time.sleep(1)
        
        # 选择第二级：南宁市
        ev("""(function(){
            var panels=document.querySelectorAll('.el-cascader-menu');
            if(panels.length>1){
                var items=panels[1].querySelectorAll('.el-cascader-node');
                for(var i=0;i<items.length;i++){
                    if(items[i].textContent?.trim()?.includes('南宁')){
                        items[i].click();
                        return{selected:'南宁'};
                    }
                }
            }
            return{error:'no_nanning'};
        })()""")
        time.sleep(1)
        
        # 选择第三级：青秀区
        ev("""(function(){
            var panels=document.querySelectorAll('.el-cascader-menu');
            if(panels.length>2){
                var items=panels[2].querySelectorAll('.el-cascader-node');
                for(var i=0;i<items.length;i++){
                    if(items[i].textContent?.trim()?.includes('青秀')){
                        items[i].click();
                        return{selected:'青秀区'};
                    }
                }
                // 如果没有青秀区，选第一个
                if(items.length>0){items[0].click();return{selected:items[0].textContent?.trim()}}
            }
            return{error:'no_district'};
        })()""")
        time.sleep(1)
        
        # 关闭cascader
        ev("document.body.click()")
        time.sleep(1)

screenshot("step3_cascader")

# ===== STEP 4: 填写所有text input =====
print("\nSTEP 4: 填写所有可填写字段")
MATERIALS = {
    "企业名称":"广西智信数据科技有限公司","注册资本":"100",
    "详细地址":"民族大道166号","生产经营地详细地址":"民族大道166号",
    "联系电话":"13877151234","邮政编码":"530028","从业人数":"5",
    "申请执照副本数量":"1",
}

results=[]
for kw,val in MATERIALS.items():
    r=ev(f"""(function(){{
        var kw='{kw}',val='{val}';
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){{
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes(kw)){{
                var input=fi[i].querySelector('.el-input__inner,.el-textarea__inner');
                if(input&&!input.disabled){{
                    var setter=Object.getOwnPropertyDescriptor(window[input.tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                    setter.call(input,val);input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));
                    return{{ok:true,label:label.textContent.trim()}};
                }}
                return{{ok:false,label:label.textContent.trim(),reason:'no_input_or_disabled'}};
            }}
        }}
        return{{ok:false,label:kw,reason:'not_found'}};
    }})()""")
    results.append(r or {"ok":False,"label":kw,"reason":"cdp_err"})

ok=[r for r in results if r and r.get("ok")]
fail=[r for r in results if r and not r.get("ok")]
log("110.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
    issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
for r in ok: print(f"    ✅ {r.get('label','')}")
for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

# ===== STEP 5: 处理select下拉框 =====
print("\nSTEP 5: 处理select下拉框")
selects = ev("""(function(){
    var sels=document.querySelectorAll('.el-select');
    var r=[];
    for(var i=0;i<sels.length;i++){
        var fi=sels[i].closest('.el-form-item');
        var label=fi?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=sels[i].querySelector('.el-input__inner');
        var val=input?.value||'';
        var required=fi?.className?.includes('is-required')||false;
        if(!val&&required)r.push({i:i,label:label,val:val});
    }
    return r;
})()""")
print(f"  未填的required selects: {selects}")

# 尝试选择每个required select的第一个选项
for sel in (selects or []):
    idx = sel.get('i',0)
    print(f"  处理 select #{idx}: {sel.get('label','')}")
    # 点击展开
    ev(f"""(function(){{
        var sels=document.querySelectorAll('.el-select');
        if(sels[{idx}]){{
            var input=sels[{idx}].querySelector('.el-input__inner');
            if(input)input.click();
        }}
    }})()""")
    time.sleep(1)
    # 选择第一个选项
    ev("""(function(){
        var items=document.querySelectorAll('.el-select-dropdown__item');
        if(items.length>0){
            items[0].click();
            return{selected:items[0].textContent?.trim()};
        }
        return{error:'no_items'};
    })()""")
    time.sleep(1)

screenshot("step5_filled")

# ===== STEP 6: 点击保存并下一步 =====
print("\nSTEP 6: 点击保存并下一步")
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('保存并下一步')&&btns[i].offsetParent!==null){
            btns[i].click();return;
        }
    }
})()""")
time.sleep(5)

# 检查错误
errs = ev("""(function(){
    var msgs=document.querySelectorAll('.el-message,[class*="error"],.el-form-item__error');
    var r=[];
    for(var i=0;i<msgs.length;i++){
        var t=msgs[i].textContent?.trim()||'';
        if(t&&t.length<80&&t.length>2)r.push(t);
    }
    return r.slice(0,10);
})()""")
if errs:
    print(f"  ⚠️ 验证错误: {errs}")
    log("110b.验证错误", {"errors":errs})
else:
    page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body.innerText||'').substring(0,100)})")
    print(f"  hash={page.get('hash')} forms={page.get('formCount',0)} text={page.get('text','')[:60]}")

# ===== STEP 7: 遍历步骤直到提交页 =====
print("\nSTEP 7: 遍历步骤直到提交页（不点提交）")
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
        hash:location.hash,
        text:(document.body.innerText||'').substring(0,200)};
    })()""")
    
    step_info = current.get('step') or {}
    print(f"\n  步骤{step}: #{step_info.get('i','?')} {step_info.get('title','')} forms={current.get('formCount',0)} hash={current.get('hash','')[:30]}")
    print(f"  按钮: {current.get('buttons',[])} hasSubmit={current.get('hasSubmit')}")
    
    # 认证检测
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
        log("111.提交按钮检测", {"step":step,"stepTitle":step_info.get('title',''),"auth":auth,"buttons":current.get('buttons',[])})
        screenshot("step7_submit_page")
        break
    
    # 点击下一步
    clicked = False
    for btn_text in ['保存并下一步','保存至下一步','下一步']:
        click_result = ev(f"""(function(){{
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){{
                if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null){{
                    btns[i].click();return{{clicked:true,text:'{btn_text}'}};
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
    
    # 检查错误
    errs = ev("""(function(){
        var msgs=document.querySelectorAll('.el-message,[class*="error"],.el-form-item__error');
        var r=[];
        for(var i=0;i<msgs.length;i++){
            var t=msgs[i].textContent?.trim()||'';
            if(t&&t.length<80&&t.length>2)r.push(t);
        }
        return r.slice(0,5);
    })()""")
    if errs:
        print(f"  ⚠️ 错误: {errs}")
        # 如果有验证错误，尝试在新步骤填写
        # 检查是否到了新步骤
        new_hash = ev("location.hash")
        new_forms = ev("document.querySelectorAll('.el-form-item').length")
        print(f"  当前: hash={new_hash} forms={new_forms}")
        
        # 如果hash没变且forms没变，说明验证阻止了前进
        if new_hash == current.get('hash') and new_forms == current.get('formCount',0):
            print(f"  验证阻止前进，尝试填写缺失字段...")
            # 尝试填写缺失的select和cascader
            ev("""(function(){
                // 点击所有未填的required cascader
                var cas=document.querySelectorAll('.el-cascader');
                for(var i=0;i<cas.length;i++){
                    var fi=cas[i].closest('.el-form-item');
                    var input=cas[i].querySelector('.el-input__inner');
                    if(fi?.className?.includes('is-required')&&!input?.value){
                        input.click();
                    }
                }
            })()""")
            time.sleep(1)
            # 选择广西
            ev("""(function(){
                var panels=document.querySelectorAll('.el-cascader-menu');
                if(panels.length>0){
                    var items=panels[0].querySelectorAll('.el-cascader-node');
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('广西')){items[i].click();break}
                    }
                }
            })()""")
            time.sleep(1)
            # 选择南宁
            ev("""(function(){
                var panels=document.querySelectorAll('.el-cascader-menu');
                if(panels.length>1){
                    var items=panels[1].querySelectorAll('.el-cascader-node');
                    for(var i=0;i<items.length;i++){
                        if(items[i].textContent?.trim()?.includes('南宁')){items[i].click();break}
                    }
                }
            })()""")
            time.sleep(1)
            # 选择区
            ev("""(function(){
                var panels=document.querySelectorAll('.el-cascader-menu');
                if(panels.length>2){
                    var items=panels[2].querySelectorAll('.el-cascader-node');
                    if(items.length>0)items[0].click();
                }
            })()""")
            time.sleep(1)
            ev("document.body.click()")
            time.sleep(1)
            
            # 再次点击保存并下一步
            ev("""(function(){
                var btns=document.querySelectorAll('button,.el-button');
                for(var i=0;i<btns.length;i++){
                    if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){
                        btns[i].click();return;
                    }
                }
            })()""")
            time.sleep(5)

screenshot("step7_final")

# ===== 最终报告 =====
print("\n" + "=" * 60)
print("E2E 测试总结")
print("=" * 60)
load_report()
rpt = __import__('json').load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "e2e_report.json"), encoding="utf-8"))
print(f"  总步骤数: {len(rpt.get('steps',[]))}")
print(f"  认证发现: {len(rpt.get('auth_findings',[]))}")
print(f"  问题数: {len(rpt.get('issues',[]))}")
for af in rpt.get('auth_findings',[]):
    print(f"  🔐 {af}")

log("112.E2E测试完成", {
    "totalSteps":len(rpt.get('steps',[])),
    "authFindings":len(rpt.get('auth_findings',[])),
    "issues":len(rpt.get('issues',[]))
})

ws.close()
print("\n✅ e2e_final7.py 完成")
