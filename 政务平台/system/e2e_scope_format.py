#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析busiAreaData正确格式: confirm方法 + 对话框交互"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 分析confirm方法源码
# ============================================================
print("Step 1: confirm/其他关键方法源码")
methods_src = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var m=comp.$options?.methods||{};
    return{
        confirm:m.confirm?.toString()?.substring(0,600)||'',
        handleAction:m.handleAction?.toString()?.substring(0,600)||'',
        treeSelectChange:m.treeSelectChange?.toString()?.substring(0,400)||'',
        handleDelBusinessRange:m.handleDelBusinessRange?.toString()?.substring(0,400)||'',
        businessChange:m.businessChange?.toString()?.substring(0,400)||'',
        becomeTree:m.becomeTree?.toString()?.substring(0,400)||''
    };
})()""")
if isinstance(methods_src, dict):
    for k,v in methods_src.items():
        if v: print(f"  {k}: {v[:200]}")

# ============================================================
# Step 2: 分析对话框组件 - 找tni-dialog内部组件
# ============================================================
print("\nStep 2: 对话框内部组件")
dlg_comp = ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        var comp=d.__vue__;
        if(!comp)continue;
        var name=comp.$options?.name||'';
        var dataKeys=Object.keys(comp.$data||{}).slice(0,15);
        var methodNames=Object.keys(comp.$options?.methods||{});
        var childNames=[];
        for(var j=0;j<(comp.$children||[]).length;j++){
            childNames.push(comp.$children[j].$options?.name||'?');
        }
        return{name:name,dataKeys:dataKeys,methods:methodNames,childNames:childNames};
    }
    return 'no_dialog_comp';
})()""")
print(f"  对话框组件: {dlg_comp}")

# ============================================================
# Step 3: 打开对话框并等待内容加载
# ============================================================
print("\nStep 3: 打开对话框(等待加载)")

# 先确保行业类型已选
ind_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型'))return items[i].querySelector('input')?.value||'';
    }
})()""")
print(f"  当前行业类型: {ind_val}")

# 点击添加按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return}
    }
})()""")
time.sleep(8)  # 等更久让对话框内容加载

# 再次深度分析对话框
dlg_deep = ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        var elCount=d.querySelectorAll('*').length;
        var iframes=d.querySelectorAll('iframe');
        var trees=d.querySelectorAll('.el-tree');
        var inputs=d.querySelectorAll('input');
        var checkboxes=d.querySelectorAll('.el-checkbox');
        var btns=d.querySelectorAll('button,.el-button');
        var tabs=d.querySelectorAll('.el-tabs__item,[class*="tab-item"]');
        
        // 列出所有子Vue组件
        var vueComps=[];
        function findVues(el,depth){
            if(depth>3)return;
            var v=el.__vue__;
            if(v&&v.$options?.name){
                vueComps.push({name:v.$options?.name,tag:el.tagName,depth:depth});
            }
            for(var j=0;j<el.children.length;j++){
                findVues(el.children[j],depth+1);
            }
        }
        findVues(d,0);
        
        // 获取body HTML
        var body=d.querySelector('.el-dialog__body,[class*="dialog-body"],.tni-dialog__body');
        var bodyHTML=body?body.innerHTML?.substring(0,500):'no body';
        
        return{
            elCount:elCount,
            iframes:iframes.length,
            iframeSrcs:Array.from(iframes).map(function(f){return f.src||f.getAttribute('src')||f.getAttribute('data-src')||''}),
            trees:trees.length,
            inputs:inputs.length,
            checkboxes:checkboxes.length,
            btns:btns.length,
            tabs:tabs.length,
            vueComps:vueComps.slice(0,15),
            bodyHTML:bodyHTML
        };
    }
    return 'no_dialog';
})()""")
print(f"  对话框深度: {dlg_deep}")

# ============================================================
# Step 4: 如果有iframe，通过CDP连接
# ============================================================
if isinstance(dlg_deep, dict) and dlg_deep.get('iframes', 0) > 0:
    print("\nStep 4: iframe CDP连接")
    targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for t in targets:
        url = t.get('url','')
        if 'jyfwyun' in url or 'scope' in url.lower() or 'business' in url.lower():
            print(f"  target: {t.get('type','')} {url[:80]}")
            if t.get('webSocketDebuggerUrl'):
                print(f"  ws: {t['webSocketDebuggerUrl']}")
elif isinstance(dlg_deep, dict) and dlg_deep.get('elCount',0) <= 10:
    print("\nStep 4: 对话框内容未加载 - 尝试触发加载")
    # 可能需要先选好行业类型和住所才能加载内容
    # 检查businese-info组件的handleAction方法
    ha_result = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var comp=findComp(vm,'businese-info',0);
        if(!comp)return{error:'no_comp'};
        
        // 尝试调用handleAction打开对话框
        if(typeof comp.handleAction==='function'){
            try{
                comp.handleAction();
                return{called:'handleAction'};
            }catch(e){
                return{error:e.message};
            }
        }
        return{error:'no_handleAction'};
    })()""")
    print(f"  handleAction: {ha_result}")
    time.sleep(5)
    
    # 再次检查对话框
    dlg2 = ev("""(function(){
        var ds=document.querySelectorAll('.tni-dialog');
        for(var i=0;i<ds.length;i++){
            var d=ds[i];
            if(d.offsetParent===null)continue;
            return{elCount:d.querySelectorAll('*').length,iframes:d.querySelectorAll('iframe').length,text:d.textContent?.trim()?.substring(0,100)||''};
        }
    })()""")
    print(f"  对话框更新: {dlg2}")

# ============================================================
# Step 5: 尝试通过API获取经营范围数据格式
# ============================================================
print("\nStep 5: 通过API获取经营范围格式")

# 拦截API
ev("""(function(){
    window.__scope_api=[];
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('scope')||url.includes('Scope')||url.includes('businessArea')||url.includes('jyfwyun')){
                window.__scope_api.push({url:url,status:self.status,resp:self.responseText?.substring(0,500)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 触发经营范围加载 - 通过businese-info的getIndustryList
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return;
    if(typeof comp.getIndustryList==='function'){
        try{comp.getIndustryList()}catch(e){return e.message}
    }
})()""")
time.sleep(3)

scope_api = ev("window.__scope_api")
if scope_api:
    for a in scope_api:
        print(f"  API: {a.get('url','')[:60]} status={a.get('status')}")
        resp = a.get('resp','')
        if resp:
            try:
                parsed = json.loads(resp)
                print(f"    code={parsed.get('code','')} keys={list(parsed.keys())[:5]}")
                if parsed.get('data'):
                    d = parsed['data']
                    if isinstance(d, list) and len(d) > 0:
                        print(f"    data[0]: {json.dumps(d[0],ensure_ascii=False)[:150]}")
                    elif isinstance(d, dict):
                        print(f"    data keys: {list(d.keys())[:10]}")
            except:
                print(f"    raw: {resp[:100]}")

# 关闭对话框
ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        var close=d.querySelector('[class*="close"]');
        if(close)close.click();
    }
    document.body.click();
})()""")

print("\n✅ 完成")
