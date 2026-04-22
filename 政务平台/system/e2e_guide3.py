#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过DOM定位guide页面的cascader并设置地址"""
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
# Step 1: 通过DOM找cascader的Vue实例
# ============================================================
print("Step 1: 通过DOM找cascader")
casc_info = ev("""(function(){
    // 找所有cascader DOM元素
    var casEls=document.querySelectorAll('.el-cascader,.tne-data-picker,[class*="cascader"]');
    var result=[];
    for(var i=0;i<casEls.length;i++){
        var el=casEls[i];
        var vm=el.__vue__;
        var visible=el.offsetParent!==null;
        if(!vm)continue;
        var name=vm.$options?.name||'';
        var value=vm.value||vm.$data?.value||vm.$props?.value;
        var placeholder=vm.$props?.placeholder||vm.placeholder||'';
        result.push({
            idx:i,name:name,value:JSON.stringify(value).substring(0,40),
            placeholder:placeholder,visible:visible,
            tag:el.tagName,cls:(el.className||'').substring(0,30)
        });
    }
    return result;
})()""")
print(f"  cascader元素: {casc_info}")

# ============================================================
# Step 2: 通过DOM找所有form-item的Vue实例
# ============================================================
print("\nStep 2: form-item组件")
form_items = ev("""(function(){
    var els=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<els.length;i++){
        var vm=els[i].__vue__;
        if(!vm)continue;
        var label=vm.$props?.label||vm.label||els[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var prop=vm.$props?.prop||vm.prop||'';
        var visible=els[i].offsetParent!==null;
        if(visible&&label){
            result.push({idx:i,label:label.substring(0,20),prop:prop,visible:visible});
        }
    }
    return result;
})()""")
if isinstance(form_items, list):
    for f in form_items:
        print(f"  {f}")
else:
    print(f"  {form_items}")

# ============================================================
# Step 3: 找到guide页面的根Vue实例
# ============================================================
print("\nStep 3: guide根Vue实例")
root_info = ev("""(function(){
    // 找ElCard的Vue实例
    var card=document.querySelector('.el-card');
    if(!card)return'no_card';
    var vm=card.__vue__;
    // 向上找到有ElForm子组件的父级
    while(vm){
        var childNames=(vm.$children||[]).map(function(c){return c.$options?.name||''});
        if(childNames.includes('ElForm')){
            var methods=Object.keys(vm.$options?.methods||{});
            var data=vm.$data||{};
            var dataKeys=Object.keys(data);
            var dataVals={};
            for(var i=0;i<dataKeys.length;i++){
                var v=data[dataKeys[i]];
                if(v===null||v===undefined||v===''||v===false)continue;
                if(Array.isArray(v))dataVals[dataKeys[i]]='A['+v.length+']:'+JSON.stringify(v).substring(0,50);
                else if(typeof v==='object')dataVals[dataKeys[i]]=JSON.stringify(v).substring(0,60);
                else dataVals[dataKeys[i]]=v;
            }
            return {name:vm.$options?.name,methods:methods,dataVals:dataVals};
        }
        vm=vm.$parent;
    }
    return 'not_found';
})()""")
print(f"  {json.dumps(root_info, ensure_ascii=False)[:500] if isinstance(root_info,dict) else root_info}")

# ============================================================
# Step 4: 直接找到cascader DOM并设置值
# ============================================================
print("\nStep 4: 设置cascader值")
set_result = ev("""(function(){
    var casEls=document.querySelectorAll('.el-cascader,.tne-data-picker');
    for(var i=0;i<casEls.length;i++){
        var el=casEls[i];
        var vm=el.__vue__;
        if(!vm)continue;
        var name=vm.$options?.name||'';
        var visible=el.offsetParent!==null;
        if(!visible)continue;
        
        // 设置值
        var addrValue=['450000','450100','450103'];
        vm.$emit('input',addrValue);
        vm.$emit('change',addrValue);
        
        // 也尝试直接设置
        if(vm.$data){
            vm.$set(vm.$data,'value',addrValue);
        }
        if(vm.$props&&vm.$props.value!==undefined){
            // 通过父组件设置
            var parent=vm.$parent;
            if(parent){
                // 找到绑定value的prop
                var modelExpr=vm.$vnode?.data?.model?.expression||'';
                if(modelExpr){
                    // 设置父组件数据
                    var keys=modelExpr.split('.');
                    var target=parent;
                    for(var j=0;j<keys.length-1;j++){
                        target=target[keys[j]]||target.$data?.[keys[j]];
                    }
                    if(target)target[keys[keys.length-1]]=addrValue;
                }
            }
        }
        
        return {set:true,name:name,visible:visible};
    }
    return 'no_visible_cascader';
})()""")
print(f"  {set_result}")

# ============================================================
# Step 5: 尝试通过模拟点击cascader面板选择地址
# ============================================================
print("\nStep 5: 模拟cascader点击")
click_result = ev("""(function(){
    // 找cascader input并点击展开
    var casInputs=document.querySelectorAll('.el-cascader .el-input__inner,.tne-data-picker .el-input__inner');
    var clicked=[];
    for(var i=0;i<casInputs.length;i++){
        var rect=casInputs[i].getBoundingClientRect();
        if(rect.width>0&&rect.height>0){
            casInputs[i].click();
            clicked.push({idx:i,placeholder:casInputs[i].placeholder||''});
        }
    }
    return clicked;
})()""")
print(f"  点击cascader: {click_result}")
time.sleep(1)

# 查看展开的面板
panel_info = ev("""(function(){
    var panels=document.querySelectorAll('.el-cascader-panel,.el-cascader-menus,.el-popper');
    var result=[];
    for(var i=0;i<panels.length;i++){
        var visible=panels[i].offsetParent!==null||panels[i].style?.display!=='none';
        if(visible){
            var items=panels[i].querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
            var texts=[];
            for(var j=0;j<Math.min(items.length,10);j++){
                texts.push(items[j].textContent?.trim()?.substring(0,15)||'');
            }
            result.push({idx:i,visible:true,items:texts});
        }
    }
    return result;
})()""")
print(f"  面板: {panel_info}")

# 如果面板展开了，点击"广西壮族自治区"
if isinstance(panel_info, list) and panel_info:
    ev("""(function(){
        var nodes=document.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<nodes.length;i++){
            var t=nodes[i].textContent?.trim()||'';
            if(t.includes('广西')){
                nodes[i].click();
                return {clicked:t};
            }
        }
        return 'no_guangxi';
    })()""")
    time.sleep(1)
    
    # 点击南宁市
    ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        // 第二个菜单
        var menu2=menus[1];
        if(!menu2)return'no_menu2';
        var items=menu2.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('南宁')){
                items[i].click();
                return {clicked:t};
            }
        }
        return 'no_nanning';
    })()""")
    time.sleep(1)
    
    # 点击青秀区
    ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        var menu3=menus[2];
        if(!menu3)return'no_menu3';
        var items=menu3.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('青秀')){
                items[i].click();
                return {clicked:t};
            }
        }
        return 'no_qingxiu';
    })()""")
    time.sleep(1)

# ============================================================
# Step 6: 点击下一步
# ============================================================
print("\nStep 6: 点击下一步")
errors_before = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误(前): {errors_before}")

click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('下一步')&&!all[i].disabled){
            all[i].click();
            return {clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  点击: {click}")
time.sleep(5)

errors_after = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误(后): {errors_after}")

cur = ev("location.hash")
print(f"  路由: {cur}")

# ============================================================
# Step 7: 检查组件
# ============================================================
print("\nStep 7: 检查组件")
comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    return {flowControl:!!fc,withoutName:!!wn,hash:location.hash};
})()""")
print(f"  {comps}")

if isinstance(comps, dict) and comps.get('withoutName'):
    ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0);
        if(wn)wn.toNotName();
    })()""")
    time.sleep(5)
    comps2 = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        return {flowControl:!!fc,hash:location.hash};
    })()""")
    print(f"  toNotName后: {comps2}")

print("\n✅ 完成")
