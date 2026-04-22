#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step23: 操作其他来源名称对话框 → 填写 → 确定 → 进入设立登记"""
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
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":10000}}))
    for _ in range(20):
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r.get("result",{}).get("result",{}).get("value")
        except:
            return None
    return None

# 1. 恢复token
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
})()""")

# 2. 确认在名称选择页
print("=== 1. 当前页面 ===")
state = ev("({hash:location.hash, text:(document.body.innerText||'').substring(0,200)})")
print(f"  hash: {(state or {}).get('hash','?')}")
print(f"  text: {(state or {}).get('text','')[:120]}")

# 3. 点击"其他来源名称"按钮（精确点击button元素）
print("\n=== 2. 点击其他来源名称按钮 ===")
click = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('其他来源名称')&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:t};
        }
    }
    // 也找span/div
    var all=document.querySelectorAll('span,div');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='其他来源名称'&&all[i].offsetParent!==null&&all[i].children.length===0){
            all[i].click();
            return{clicked:t,tag:all[i].tagName};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click: {click}")
time.sleep(3)

# 4. 分析对话框内容
print("\n=== 3. 对话框分析 ===")
dialog = ev("""(function(){
    var dgs=document.querySelectorAll('.el-dialog__wrapper,.el-dialog');
    var r=[];
    for(var i=0;i<dgs.length;i++){
        var dg=dgs[i];
        var visible=dg.className?.includes('open')||dg.style?.display!=='none';
        if(!visible)continue;
        var title=dg.querySelector('.el-dialog__title,.el-dialog__header')?.textContent?.trim()||'';
        var body=dg.querySelector('.el-dialog__body');
        var bodyText=body?.textContent?.trim()?.substring(0,200)||'';
        var bodyHtml=body?.innerHTML?.substring(0,500)||'';
        var formItems=body?body.querySelectorAll('.el-form-item').length:0;
        var inputs=body?body.querySelectorAll('input,textarea,select').length:0;
        var btns=body?body.querySelectorAll('button,.el-button').length:0;
        r.push({title:title,bodyText:bodyText,formItems:formItems,inputs:inputs,btns:btns,bodyHtml:bodyHtml});
    }
    return r;
})()""")
for d in (dialog or []):
    print(f"  title: {d.get('title','')}")
    print(f"  formItems: {d.get('formItems',0)} inputs: {d.get('inputs',0)} btns: {d.get('btns',0)}")
    print(f"  bodyText: {d.get('bodyText','')[:150]}")
    print(f"  bodyHtml: {d.get('bodyHtml','')[:200]}")

# 5. 填写对话框中的表单
print("\n=== 4. 填写对话框表单 ===")
fill = ev("""(function(){
    var dgs=document.querySelectorAll('.el-dialog__wrapper,.el-dialog');
    var dg=null;
    for(var i=0;i<dgs.length;i++){
        var visible=dgs[i].className?.includes('open')||dgs[i].style?.display!=='none';
        if(visible){dg=dgs[i];break}
    }
    if(!dg)return{error:'no_dialog'};
    var body=dg.querySelector('.el-dialog__body');
    if(!body)return{error:'no_body'};
    
    // 找所有form-item
    var fi=body.querySelectorAll('.el-form-item');
    var filled=[];
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        var input=fi[i].querySelector('.el-input__inner,.el-textarea__inner');
        var sel=fi[i].querySelector('.el-select');
        var labelText=label?.textContent?.trim()||'';
        var ph=input?.placeholder||'';
        
        if(input&&!input.disabled){
            var val='';
            if(labelText.includes('名称')||ph.includes('名称'))val='广西智信数据科技有限公司';
            else if(labelText.includes('字号')||ph.includes('字号'))val='智信数据';
            else if(labelText.includes('行业')||ph.includes('行业'))val='科技';
            else if(labelText.includes('组织形式')||ph.includes('组织形式'))val='有限公司';
            else if(labelText.includes('来源')||ph.includes('来源'))val='1';
            else if(labelText.includes('文号')||ph.includes('文号'))val='2026第001号';
            else if(labelText.includes('日期')||ph.includes('日期'))val='2026-04-13';
            else if(ph)val='test';
            
            if(val){
                var setter=Object.getOwnPropertyDescriptor(window[input.tagName==='TEXTAREA'?'HTMLTextAreaElement':'HTMLInputElement'].prototype,'value').set;
                setter.call(input,val);
                input.dispatchEvent(new Event('input',{bubbles:true}));
                input.dispatchEvent(new Event('change',{bubbles:true}));
                filled.push({label:labelText,ph:ph,val:val});
            }
        }
        // select
        if(sel){
            filled.push({label:labelText,type:'select',needManual:true});
        }
    }
    return{filled:filled,totalFormItems:fi.length};
})()""")
print(f"  fill: {json.dumps(fill or {}, ensure_ascii=False)[:400]}")

# 6. 点击对话框的"确 定"
print("\n=== 5. 点击确 定 ===")
confirm = ev("""(function(){
    var dgs=document.querySelectorAll('.el-dialog__wrapper,.el-dialog');
    var dg=null;
    for(var i=0;i<dgs.length;i++){
        var visible=dgs[i].className?.includes('open')||dgs[i].style?.display!=='none';
        if(visible){dg=dgs[i];break}
    }
    if(!dg)return{error:'no_dialog'};
    var btns=dg.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('确 定')||t.includes('确定')||t.includes('确认')){
            btns[i].click();
            return{clicked:t};
        }
    }
    return{error:'no_confirm_btn'};
})()""")
print(f"  confirm: {confirm}")
time.sleep(5)

# 7. 检查结果
page = ev("""(function(){
    return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,
    inputCount:document.querySelectorAll('input,textarea,select').length,
    dialogVisible:document.querySelectorAll('.el-dialog__wrapper.open,.el-dialog[aria-hidden=false]').length>0,
    text:(document.body.innerText||'').substring(0,400)};
})()""")
print(f"  hash: {(page or {}).get('hash','?')}")
print(f"  forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  dialog: {(page or {}).get('dialogVisible',False)}")
print(f"  text: {(page or {}).get('text','')[:250]}")

# 8. 如果对话框关闭了但还在名称选择页，可能需要选择名称
if not (page or {}).get('dialogVisible',False) and (page or {}).get('hash','') == '#/index/select-prise?entType=1100':
    print("\n=== 6. 名称列表检查 ===")
    names = ev("""(function(){
        var tables=document.querySelectorAll('.el-table');
        var r=[];
        for(var i=0;i<tables.length;i++){
            var rows=tables[i].querySelectorAll('.el-table__row');
            for(var j=0;j<rows.length;j++){
                r.push({j:j,text:rows[j].textContent?.trim()?.substring(0,50)||''});
            }
        }
        // 也检查列表/卡片
        var items=document.querySelectorAll('[class*="name-item"],[class*="prise-item"],[class*="list-item"]');
        for(var i=0;i<items.length;i++){
            r.push({type:'item',text:items[i].textContent?.trim()?.substring(0,30)||''});
        }
        return{tableRows:r,emptyText:(document.body.innerText||'').includes('暂无数据')};
    })()""")
    print(f"  names: {names}")
    
    # 如果有名称列表，点击第一个
    if names and not names.get('emptyText'):
        ev("""(function(){
            var rows=document.querySelectorAll('.el-table__row');
            if(rows.length>0)rows[0].click();
        })()""")
        time.sleep(3)

# 9. 如果到了新页面（设立登记表单），探查
page2 = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, inputCount:document.querySelectorAll('input,textarea,select').length, text:(document.body.innerText||'').substring(0,300)})")
print(f"\n=== 7. 当前状态 ===")
print(f"  hash: {(page2 or {}).get('hash','?')}")
print(f"  forms: {(page2 or {}).get('formCount',0)} inputs: {(page2 or {}).get('inputCount',0)}")
print(f"  text: {(page2 or {}).get('text','')[:200]}")

# 如果有表单，填写
fc = (page2 or {}).get('formCount',0)
ic = (page2 or {}).get('inputCount',0)
if fc > 0 or ic > 0:
    print("\n=== 8. 表单详细探查 ===")
    form = ev("""(function(){
        var fi=document.querySelectorAll('.el-form-item');
        var r=[];
        for(var i=0;i<fi.length;i++){
            var item=fi[i],label=item.querySelector('.el-form-item__label');
            var input=item.querySelector('.el-input__inner,.el-textarea__inner');
            var sel=item.querySelector('.el-select');
            var upload=item.querySelector('.el-upload');
            var tp='unknown';
            if(input)tp=input.tagName==='TEXTAREA'?'textarea':'input';
            if(sel)tp='select';if(upload)tp='upload';
            var info={i:i,label:label?.textContent?.trim()||'',type:tp,required:item.className.includes('is-required')};
            if(input){info.ph=input.placeholder||'';info.disabled=input.disabled}
            r.push(info);
        }
        var steps=document.querySelectorAll('.el-step');
        var stepList=[];
        for(var i=0;i<steps.length;i++){stepList.push(steps[i].querySelector('.el-step__title')?.textContent?.trim()||'')}
        return{fields:r,steps:stepList,buttons:Array.from(document.querySelectorAll('button,.el-button')).map(function(b){return b.textContent?.trim()}).filter(function(t){return t&&t.length<20}).slice(0,20)};
    })()""")
    if form:
        log("48.设立登记表单", {"formCount":len(form.get("fields",[])),"steps":form.get("steps",[]),"buttons":form.get("buttons",[])})
        log("48a.字段详情", {"fields":form.get("fields",[])[:60]})
        for f in form.get("fields",[])[:40]:
            print(f"  [{f.get('i')}] {f.get('label','')} ({f.get('type','')}) req={f.get('required')} ph={f.get('ph','')}")

        # 填写
        MATERIALS = {
            "公司名称":"广西智信数据科技有限公司","名称":"广西智信数据科技有限公司",
            "注册资本":"100","经营范围":"软件开发","住所":"南宁市青秀区民族大道166号",
            "法定代表人":"陈明辉","身份证":"450103199001151234","联系电话":"13877151234",
            "邮箱":"chenmh@example.com","监事":"李芳","财务负责人":"张丽华",
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
                        return{{ok:false,label:label.textContent.trim(),reason:'no_input'}};
                    }}
                }}
                return{{ok:false,label:kw,reason:'not_found'}};
            }})()""")
            results.append(r or {"ok":False,"label":kw,"reason":"cdp_err"})
        ok=[r for r in results if r and r.get("ok")]
        fail=[r for r in results if r and not r.get("ok")]
        log("49.填写测试",{"ok":len(ok),"fail":len(fail),"ok_list":ok,"fail_list":fail},
            issues=[f"填写失败:{r.get('label','')}({r.get('reason','')})" for r in fail])
        print(f"\n  填写: ok={len(ok)} fail={len(fail)}")
        for r in fail: print(f"    ❌ {r.get('label','')} ({r.get('reason','')})")

        auth=ev("""(function(){var t=document.body.innerText||'';return{faceAuth:t.includes('人脸'),smsAuth:t.includes('验证码'),bankAuth:t.includes('银行卡'),realName:t.includes('实名认证'),signAuth:t.includes('电子签名'),digitalCert:t.includes('数字证书'),caAuth:t.includes('CA')}})()""")
        if auth: log("50.认证检测",auth); print(f"  认证: {auth}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step23.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step23 完成")
