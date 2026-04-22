#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""guide/base页面：设置地址cascader → 点下一步 → 进入flow-control"""
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: 回到guide/base页面
# ============================================================
print("Step 1: 回到guide/base")
ev("""(function(){
    document.getElementById('app').__vue__.$router.push('/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=');
})()""")
time.sleep(3)
cur = ev("location.hash")
print(f"  路由: {cur}")

# ============================================================
# Step 2: 分析guide/base组件
# ============================================================
print("\nStep 2: base组件分析")
base_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var base=findComp(vm,'base',0);
    if(!base)return'no_base';
    var methods=Object.keys(base.$options?.methods||{{}});
    var d=base.$data||{{}};
    var dataKeys=Object.keys(d);
    var dataVals={{}};
    for(var i=0;i<dataKeys.length;i++){{
        var v=d[dataKeys[i]];
        if(v===null||v===undefined||v===''||v===false)continue;
        if(Array.isArray(v))dataVals[dataKeys[i]]='A['+v.length+']';
        else if(typeof v==='object')dataVals[dataKeys[i]]=JSON.stringify(v).substring(0,80);
        else dataVals[dataKeys[i]]=v;
    }}
    return {{methods:methods,dataVals:dataVals,childNames:(base.$children||[]).map(function(c){{return c.$options?.name||''}}).slice(0,10)}};
}})()""")
print(f"  {json.dumps(base_info, ensure_ascii=False)[:500] if isinstance(base_info,dict) else base_info}")

# ============================================================
# Step 3: 查找cascader组件和地址字段
# ============================================================
print("\nStep 3: cascader和地址字段")
casc_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var base=findComp(vm,'base',0);
    if(!base)return'no_base';
    var d=base.$data||{{}};
    
    // 找所有cascader
    var cascaders=[];
    function findCascader(vm,d){{
        if(d>15)return;
        var n=vm.$options?.name||'';
        if(n.includes('cascader')||n.includes('Cascader')||n.includes('data-picker')||n.includes('data-picker')||n==='tne-data-picker'){{
            cascaders.push({{name:n,value:vm.value||vm.$data?.value,props:vm.$props?{{}}:{{}}}});
        }}
        for(var i=0;i<(vm.$children||[]).length;i++)findCascader(vm.$children[i],d+1);
    }}
    findCascader(base,0);
    
    // 找form-item组件
    var formItems=[];
    function findFormItems(vm,d){{
        if(d>10)return;
        var n=vm.$options?.name||'';
        if(n==='form-item'){{
            var prop=vm.$props?.prop||vm.prop||'';
            var label=vm.$props?.label||vm.label||'';
            formItems.push({{prop:prop,label:label}});
        }}
        for(var i=0;i<(vm.$children||[]).length;i++)findFormItems(vm.$children[i],d+1);
    }}
    findFormItems(base,0);
    
    return {{cascaders:cascaders,formItems:formItems}};
}})()""")
print(f"  {json.dumps(casc_info, ensure_ascii=False)[:500] if isinstance(casc_info,dict) else casc_info}")

# ============================================================
# Step 4: 查看base组件的form数据
# ============================================================
print("\nStep 4: form数据")
form_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var base=findComp(vm,'base',0);
    if(!base)return'no_base';
    // 查找form ref
    var form=base.$refs?.form||base.$refs?.elForm||base.$refs?.baseForm;
    if(!form){{
        // 遍历$refs
        var refs=Object.keys(base.$refs||{{}});
        return {{refs:refs,noForm:true}};
    }}
    var model=form.model||{{}};
    var rules=form.rules||{{}};
    return {{
        modelKeys:Object.keys(model),
        modelVals:Object.keys(model).map(function(k){{
            var v=model[k];
            if(v===null||v===undefined)return k+':null';
            if(Array.isArray(v))return k+':A['+v.length+']'+JSON.stringify(v).substring(0,40);
            return k+':'+JSON.stringify(v).substring(0,40);
        }}),
        ruleKeys:Object.keys(rules)
    }};
}})()""")
print(f"  {json.dumps(form_data, ensure_ascii=False)[:500] if isinstance(form_data,dict) else form_data}")

# ============================================================
# Step 5: 设置地址
# ============================================================
print("\nStep 5: 设置地址")
addr_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var base=findComp(vm,'base',0);
    if(!base)return'no_base';
    
    // 查找form
    var form=base.$refs?.form||base.$refs?.elForm||base.$refs?.baseForm;
    if(form&&form.model){{
        var m=form.model;
        // 设置地址字段
        var addrKeys=Object.keys(m).filter(function(k){{
            return k.includes('addr')||k.includes('Addr')||k.includes('dist')||k.includes('area')||k.includes('region');
        }});
        for(var i=0;i<addrKeys.length;i++){{
            base.$set(m,addrKeys[i],['450000','450100','450103']);
        }}
    }}
    
    // 也直接在$data上设置
    var d=base.$data;
    var allAddrKeys=Object.keys(d).filter(function(k){{
        return k.includes('addr')||k.includes('Addr')||k.includes('dist')||k.includes('area')||k.includes('region');
    }});
    for(var i=0;i<allAddrKeys.length;i++){{
        base.$set(d,allAddrKeys[i],['450000','450100','450103']);
    }}
    
    // 查找tne-data-picker并设置值
    var pickers=[];
    function findPicker(vm,depth){{
        if(depth>15)return;
        var n=vm.$options?.name||'';
        if(n==='tne-data-picker'){{
            pickers.push(vm);
        }}
        for(var i=0;i<(vm.$children||[]).length;i++)findPicker(vm.$children[i],depth+1);
    }}
    findPicker(base,0);
    
    for(var i=0;i<pickers.length;i++){{
        var p=pickers[i];
        p.$emit('input',['450000','450100','450103']);
        p.$emit('change',['450000','450100','450103']);
    }}
    
    return {{addrKeys:allAddrKeys,pickersFound:pickers.length,formAddrKeys:addrKeys||[]}};
}})()""")
print(f"  {addr_result}")

# ============================================================
# Step 6: 点击下一步
# ============================================================
print("\nStep 6: 点击下一步")
# 先检查验证错误
errors_before = ev("""(function(){
    var errs=document.querySelectorAll('.el-form-item__error');
    var r=[];
    for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}
    return r;
})()""")
print(f"  验证错误(前): {errors_before}")

# 点击下一步
click_result = ev("""(function(){
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
print(f"  点击: {click_result}")
time.sleep(5)

# 检查验证错误
errors_after = ev("""(function(){
    var errs=document.querySelectorAll('.el-form-item__error');
    var r=[];
    for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}
    return r;
})()""")
print(f"  验证错误(后): {errors_after}")

# ============================================================
# Step 7: 检查是否进入flow-control
# ============================================================
print("\nStep 7: 检查组件")
comps = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    var base=findComp(vm,'base',0);
    return {{flowControl:!!fc,withoutName:!!wn,base:!!base,hash:location.hash}};
}})()""")
print(f"  {comps}")

# 如果有without-name
if isinstance(comps, dict) and comps.get('withoutName'):
    print("  点击toNotName...")
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var wn=findComp(vm,'without-name',0);
        if(wn)wn.toNotName();
    }})()""")
    time.sleep(5)
    comps2 = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        return {{flowControl:!!fc,hash:location.hash}};
    }})()""")
    print(f"  toNotName后: {comps2}")

print("\n✅ 完成")
