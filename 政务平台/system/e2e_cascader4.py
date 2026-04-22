#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过loadAllData加载cascader数据+4级选择+验证通过"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
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

# ============================================================
# Step 1: 回到guide/base
# ============================================================
print("Step 1: 回到guide/base")
ev("""(function(){
    document.getElementById('app').__vue__.$router.push('/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=');
})()""")
time.sleep(3)

# ============================================================
# Step 2: 分析tne-data-picker的distCodeValidator
# ============================================================
print("Step 2: distCodeValidator源码")
validator_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var fn=comp.$options?.methods?.distCodeValidator;
    if(!fn)return'no_method';
    return fn.toString().substring(0,300);
})()""")
print(f"  {validator_src}")

# ============================================================
# Step 3: 查看ElForm的distList验证规则
# ============================================================
print("\nStep 3: distList验证规则")
rules = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.$refs?.form;
    if(!form)return'no_form';
    var rules=form.rules||{};
    var distRule=rules.distList||rules.distCode||rules.address||[];
    return {distListRule:distRule.map(function(r){return JSON.stringify(r).substring(0,100)}),ruleKeys:Object.keys(rules)};
})()""")
print(f"  {json.dumps(rules, ensure_ascii=False)[:300] if isinstance(rules,dict) else rules}")

# ============================================================
# Step 4: 加载cascader数据
# ============================================================
print("\nStep 4: loadAllData")
load_result = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    // 调用loadAllData
    return new Promise(function(resolve){
        vm.loadAllData().then(function(){
            var dl=vm.$data?.dataList||[];
            resolve({loaded:true,dataListLen:dl.length,first3:dl.slice(0,3).map(function(d){return d.text||d.label||d.name||d.allName||JSON.stringify(d).substring(0,30)})});
        }).catch(function(e){
            resolve({error:e.message||String(e)});
        });
    });
})()""", timeout=20)
print(f"  {load_result}")
time.sleep(2)

# ============================================================
# Step 5: 通过面板选择地址（4级：省/市/区/街道）
# ============================================================
print("\nStep 5: 面板选择地址")

# 点击cascader input
ev("""(function(){
    var el=document.querySelector('.wherecascader .el-input__inner');
    if(el)el.click();
})()""")
time.sleep(2)

# 查看面板
panel = ev("""(function(){
    var menus=document.querySelectorAll('.el-cascader-menu');
    var result=[];
    for(var i=0;i<menus.length;i++){
        var items=menus[i].querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        var texts=[];
        for(var j=0;j<Math.min(items.length,5);j++){
            var t=items[j].textContent?.trim()||'';
            var rect=items[j].getBoundingClientRect();
            if(rect.width>0)texts.push(t.substring(0,15));
        }
        result.push({menuIdx:i,items:texts});
    }
    return result;
})()""")
print(f"  面板: {panel}")

# 如果面板有数据，逐级点击
if isinstance(panel, list) and panel:
    # 点击广西
    ev("""(function(){
        var items=document.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            var rect=items[i].getBoundingClientRect();
            if(t.includes('广西')&&rect.width>0){items[i].click();return true;}
        }
        return false;
    })()""")
    time.sleep(1)
    
    # 点击南宁
    ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        if(menus.length<2)return false;
        var items=menus[1].querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            var rect=items[i].getBoundingClientRect();
            if(t.includes('南宁')&&rect.width>0){items[i].click();return true;}
        }
        return false;
    })()""")
    time.sleep(1)
    
    # 点击青秀区
    ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        if(menus.length<3)return false;
        var items=menus[2].querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            var rect=items[i].getBoundingClientRect();
            if(t.includes('青秀')&&rect.width>0){items[i].click();return true;}
        }
        return false;
    })()""")
    time.sleep(1)
    
    # 查看是否有第4级(街道)
    menus4 = ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        if(menus.length<4)return {hasLevel4:false,menuCount:menus.length};
        var items=menus[3].querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        var texts=[];
        for(var j=0;j<Math.min(items.length,5);j++){
            var t=items[j].textContent?.trim()||'';
            var rect=items[j].getBoundingClientRect();
            if(rect.width>0)texts.push(t.substring(0,15));
        }
        return {hasLevel4:true,items:texts};
    })()""")
    print(f"  第4级: {menus4}")
    
    # 如果有第4级，选择第一个街道
    if isinstance(menus4, dict) and menus4.get('hasLevel4'):
        ev("""(function(){
            var menus=document.querySelectorAll('.el-cascader-menu');
            if(menus.length<4)return;
            var items=menus[3].querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
            for(var i=0;i<items.length;i++){
                var rect=items[i].getBoundingClientRect();
                if(rect.width>0){items[i].click();return items[i].textContent?.trim()?.substring(0,15);}
            }
        })()""")
        time.sleep(1)
    else:
        # 没有4级，直接关闭面板
        ev("document.body.click()")
        time.sleep(1)

# ============================================================
# Step 6: 验证cascader值
# ============================================================
print("\nStep 6: 验证cascader")
val = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    var input=el.querySelector('input');
    return {
        value:JSON.stringify(vm.value||vm.$data?.value||vm.$props?.value).substring(0,60),
        inputVal:input?input.value:'',
        checkValue:vm.$data?.checkValue,
        selected:JSON.stringify(vm.$data?.selected).substring(0,80)
    };
})()""")
print(f"  {val}")

# ============================================================
# Step 7: 验证错误检查
# ============================================================
print("\nStep 7: 验证错误")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  {errors}")

# ============================================================
# Step 8: 调用fzjgFlowSave
# ============================================================
print("\nStep 8: fzjgFlowSave")
# 拦截
ev("""(function(){
    window.__all_xhr=[];window.__jump_args=[];
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        window.__all_xhr.push({url:(this.__url||'').substring(0,80),bodyLen:(body||'').length});
        return origSend.apply(this,arguments);
    };
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router;
    if(router&&router.jump){
        var origJump=router.jump.bind(router);
        router.jump=function(){window.__jump_args.push(Array.from(arguments).map(function(a){return typeof a==='object'?JSON.stringify(a).substring(0,200):String(a)}));return origJump.apply(router,arguments)};
    }
})()""")

save_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    try{comp.fzjgFlowSave();return{called:true}}catch(e){return{error:e.message.substring(0,100)}}
})()""", timeout=20)
print(f"  {save_result}")
time.sleep(8)

xhr = ev("window.__all_xhr")
jump = ev("window.__jump_args")
cur = ev("location.hash")
comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    return {flowControl:!!findComp(vm,'flow-control',0),withoutName:!!findComp(vm,'without-name',0),hash:location.hash};
})()""")

print(f"  XHR: {xhr}")
print(f"  jump: {jump}")
print(f"  路由: {cur}")
print(f"  组件: {comps}")

if isinstance(comps, dict) and comps.get('withoutName'):
    ev("""(function(){var vm=document.getElementById('app').__vue__;function f(vm,n,d){if(d>20)return null;if(vm.$options?.name===n)return vm;for(var i=0;i<vm.$children.length;i++){var r=f(vm.$children[i],n,d+1);if(r)return r}return null}var wn=f(vm,'without-name',0);if(wn)wn.toNotName()})()""")
    time.sleep(5)
    comps2 = ev("""(function(){var vm=document.getElementById('app').__vue__;function f(vm,n,d){if(d>20)return null;if(vm.$options?.name===n)return vm;for(var i=0;i<vm.$children.length;i++){var r=f(vm.$children[i],n,d+1);if(r)return r}return null}return{flowControl:!!f(vm,'flow-control',0),hash:location.hash}})()""")
    print(f"  toNotName后: {comps2}")

print("\n✅ 完成")
