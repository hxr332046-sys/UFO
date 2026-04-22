#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过UI点击保存按钮 + 对比请求body"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page: return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: 先修复从业人数 - 通过触发el-form验证
# ============================================================
print("Step 1: 修复从业人数验证")
# 检查从业人数input的Vue绑定
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return;
    var form=ri.registForm||ri.$data?.registForm;
    if(!form)return;
    // 设置值
    ri.$set(form,'operatorNum','5');
    ri.$set(form,'empNum','5');
    // 触发验证
    var elForm=ri.$refs?.registFormRef||ri.$refs?.elForm;
    if(elForm){{
        elForm.validate(function(){{}});
    }}
}})()""")

# 通过DOM设置从业人数
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('从业人数')){
            var comp=input.__vue__;
            if(comp){
                comp.$emit('input','5');
                comp.$emit('change','5');
            }
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(input,'5');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
            input.dispatchEvent(new Event('blur',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 2: 拦截请求 - 不修改body，看原始请求
# ============================================================
print("\nStep 2: 拦截原始请求")
ev("""(function(){
    window.__orig_body=null;
    window.__orig_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__orig_body=body||'';
            var self=this;
            self.addEventListener('load',function(){
                window.__orig_resp={status:self.status,text:self.responseText||''};
            });
        }
        return origSend.apply(this,arguments);
    };
})()""")

# ============================================================
# Step 3: 通过UI点击保存按钮
# ============================================================
print("\nStep 3: 点击保存按钮")
click_result = ev("""(function(){
    // 找保存/暂存按钮
    var btns=document.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('暂存')||t.includes('保存草稿')||t.includes('保存')){
            btns[i].click();
            return{clicked:t,idx:i};
        }
    }
    // 也找带保存文字的span/div
    var els=document.querySelectorAll('[class*="btn"],[class*="button"],[class*="save"]');
    for(var i=0;i<els.length;i++){
        var t=els[i].textContent?.trim()||'';
        if(t.includes('暂存')||t.includes('保存草稿')){
            els[i].click();
            return{clicked:t,tag:els[i].tagName};
        }
    }
    return 'no_save_btn';
})()""")
print(f"  点击: {click_result}")
time.sleep(5)

# 检查结果
orig_body = ev("window.__orig_body")
orig_resp = ev("window.__orig_resp")

if isinstance(orig_body, str):
    print(f"  body长度: {len(orig_body)}")
    try:
        bobj = json.loads(orig_body)
        # 对比关键字段
        for k in ['namePreFlag','operatorNum','empNum','distCode','businessAddress','busiAreaData','busiAreaCode','genBusiArea','entryCode','itemId','busiDateEnd']:
            v = bobj.get(k, 'MISSING')
            if isinstance(v, str) and len(v) > 50:
                v = v[:50] + '...'
            print(f"    {k}: {v}")
    except:
        print(f"  body前200: {orig_body[:200]}")

if isinstance(orig_resp, dict):
    print(f"\n  API status={orig_resp.get('status')}")
    text = orig_resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            print(f"  code={p.get('code')} msg={p.get('msg','')[:60]}")
        except:
            print(f"  raw: {text[:100]}")

# ============================================================
# Step 4: 如果没有保存按钮，找flow-control的按钮
# ============================================================
if click_result == 'no_save_btn':
    print("\nStep 4: 找flow-control按钮")
    btns = ev("""(function(){
        var all=document.querySelectorAll('button,[role="button"],.el-button');
        var r=[];
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.length>0&&t.length<30)r.push({idx:i,text:t,cls:all[i].className?.substring(0,30)||'',visible:all[i].offsetParent!==null});
        }
        return r;
    })()""")
    print(f"  按钮: {btns}")

# ============================================================
# Step 5: 检查验证错误
# ============================================================
print("\nStep 5: 验证错误")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  {errors}")

print("\n✅ 完成")
