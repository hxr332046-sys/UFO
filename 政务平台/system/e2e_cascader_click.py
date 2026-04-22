#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过CDP DOM点击模拟cascader选择地址"""
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

def cdp_click(selector, index=0):
    """通过CDP Runtime.evaluate模拟真实DOM点击"""
    return ev(f"""(function(){{
        var els=document.querySelectorAll('{selector}');
        if(els.length<= {index})return'no_el';
        var el=els[{index}];
        var rect=el.getBoundingClientRect();
        if(rect.width===0)return'not_visible';
        el.dispatchEvent(new MouseEvent('mousedown',{{bubbles:true,clientX:rect.x+rect.width/2,clientY:rect.y+rect.height/2}}));
        el.dispatchEvent(new MouseEvent('mouseup',{{bubbles:true,clientX:rect.x+rect.width/2,clientY:rect.y+rect.height/2}}));
        el.dispatchEvent(new MouseEvent('click',{{bubbles:true,clientX:rect.x+rect.width/2,clientY:rect.y+rect.height/2}}));
        return {{clicked:true,text:el.textContent?.trim()?.substring(0,20)||''}};
    }})()""")

# ============================================================
# Step 1: 分析tne-data-picker组件
# ============================================================
print("Step 1: tne-data-picker组件分析")
picker_info = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    var name=vm.$options?.name||'';
    var props=vm.$props||{};
    var data=vm.$data||{};
    var methods=Object.keys(vm.$options?.methods||{});
    // 关键属性
    var value=vm.value||data.value||props.value;
    var options=data.options||data.list||data.dataList||props.options||[];
    var visible=data.dropDownVisible||data.visible||props.visible;
    
    return {
        name:name,
        value:JSON.stringify(value).substring(0,40),
        optionsType:typeof options,
        optionsIsArray:Array.isArray(options),
        optionsLen:Array.isArray(options)?options.length:0,
        optionsFirst3:Array.isArray(options)?options.slice(0,3).map(function(o){return o.label||o.name||o.text||JSON.stringify(o).substring(0,30)}):[],
        visible:visible,
        placeholder:props.placeholder||'',
        methods:methods.slice(0,10),
        dataKeys:Object.keys(data).slice(0,15)
    };
})()""")
print(f"  {json.dumps(picker_info, ensure_ascii=False)[:500] if isinstance(picker_info,dict) else picker_info}")

# ============================================================
# Step 2: 点击cascader input展开面板
# ============================================================
print("\nStep 2: 点击cascader展开")
# 先关闭可能已打开的面板
ev("document.body.click()")
time.sleep(0.5)

# 点击cascader input
click1 = cdp_click('.wherecascader .el-input__inner')
print(f"  点击input: {click1}")
time.sleep(2)

# 查看面板内容
panel = ev("""(function(){
    var panels=document.querySelectorAll('.el-cascader-menus,.el-cascader-panel,.el-popper[aria-hidden=false],.tne-data-picker .el-scrollbar');
    var result=[];
    for(var i=0;i<panels.length;i++){
        var visible=panels[i].offsetParent!==null&&panels[i].offsetHeight>0;
        if(!visible)continue;
        var items=panels[i].querySelectorAll('.el-cascader-node,.el-cascader-menu__item,li');
        var texts=[];
        for(var j=0;j<Math.min(items.length,15);j++){
            var t=items[j].textContent?.trim()||'';
            if(t)texts.push(t.substring(0,15));
        }
        result.push({idx:i,visible:true,items:texts,cls:(panels[i].className||'').substring(0,30)});
    }
    return result;
})()""")
print(f"  面板: {panel}")

# ============================================================
# Step 3: 如果面板有数据，点击广西
# ============================================================
print("\nStep 3: 点击广西")
if isinstance(panel, list) and panel:
    # 找包含省名的菜单
    guangxi = ev("""(function(){
        var items=document.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            var rect=items[i].getBoundingClientRect();
            if(t.includes('广西')&&rect.width>0){
                items[i].click();
                return {clicked:t,visible:true};
            }
        }
        return 'no_guangxi';
    })()""")
    print(f"  广西: {guangxi}")
    time.sleep(2)
    
    # 点击南宁
    nanning = ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        var menu2=menus.length>1?menus[1]:null;
        if(!menu2)return'no_menu2';
        var items=menu2.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            var rect=items[i].getBoundingClientRect();
            if(t.includes('南宁')&&rect.width>0){
                items[i].click();
                return {clicked:t};
            }
        }
        return 'no_nanning';
    })()""")
    print(f"  南宁: {nanning}")
    time.sleep(2)
    
    # 点击青秀区
    qingxiu = ev("""(function(){
        var menus=document.querySelectorAll('.el-cascader-menu');
        var menu3=menus.length>2?menus[2]:null;
        if(!menu3)return'no_menu3';
        var items=menu3.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            var rect=items[i].getBoundingClientRect();
            if(t.includes('青秀')&&rect.width>0){
                items[i].click();
                return {clicked:t};
            }
        }
        return 'no_qingxiu';
    })()""")
    print(f"  青秀区: {qingxiu}")
    time.sleep(1)
else:
    # 面板没数据，尝试通过Vue方法加载
    print("  面板无数据，尝试Vue方法...")
    load_result = ev("""(function(){
        var el=document.querySelector('.wherecascader');
        if(!el)return'no_el';
        var vm=el.__vue__;
        if(!vm)return'no_vm';
        // 查找loadData/fetchData方法
        var methods=Object.keys(vm.$options?.methods||{});
        for(var i=0;i<methods.length;i++){
            var m=methods[i];
            if(m.includes('load')||m.includes('fetch')||m.includes('init')||m.includes('getData')){
                try{vm[m]()}catch(e){}
            }
        }
        return {methods:methods};
    })()""")
    print(f"  {load_result}")
    time.sleep(3)
    
    # 重新点击
    ev("document.body.click()")
    time.sleep(0.5)
    cdp_click('.wherecascader .el-input__inner')
    time.sleep(2)
    
    panel2 = ev("""(function(){
        var items=document.querySelectorAll('.el-cascader-node,.el-cascader-menu__item');
        var texts=[];
        for(var j=0;j<Math.min(items.length,15);j++){
            var t=items[j].textContent?.trim()||'';
            var rect=items[j].getBoundingClientRect();
            if(t&&rect.width>0)texts.push(t.substring(0,15));
        }
        return texts;
    })()""")
    print(f"  面板items: {panel2}")

# ============================================================
# Step 4: 验证地址是否设置成功
# ============================================================
print("\nStep 4: 验证地址")
addr_val = ev("""(function(){
    var el=document.querySelector('.wherecascader');
    if(!el)return'no_el';
    var vm=el.__vue__;
    if(!vm)return'no_vm';
    var value=vm.value||vm.$data?.value||vm.$props?.value;
    var input=el.querySelector('input');
    var inputVal=input?input.value:'';
    return {value:JSON.stringify(value).substring(0,60),inputVal:inputVal};
})()""")
print(f"  地址值: {addr_val}")

# ============================================================
# Step 5: 点击下一步
# ============================================================
print("\nStep 5: 点击下一步")
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

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    return {flowControl:!!fc,withoutName:!!wn,hash:location.hash};
})()""")
print(f"  组件: {comps}")

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
