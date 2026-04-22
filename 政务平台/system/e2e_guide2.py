#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""guide页面：定位正确组件 + 设置地址cascader + 下一步"""
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
# Step 1: 找到guide页面的实际组件实例
# ============================================================
print("Step 1: 找guide组件实例")
guide_comp = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    // 外层index
    var outerIdx=vm.$children?.[0]; // layout
    // 找到内层index (guide页面)
    function walk(vm,d,path){
        if(d>10)return null;
        var n=vm.$options?.name||'';
        // 检查是否是guide页面的组件(有ElCard+ElForm+tni-radio-group子组件)
        var childNames=(vm.$children||[]).map(function(c){return c.$options?.name||''});
        var hasRadio=childNames.some(function(n){return n.includes('radio')});
        var hasForm=childNames.some(function(n){return n==='ElForm'||n==='form-item'});
        if(n==='index'&&hasRadio&&hasForm){
            return {found:true,path:path,dataKeys:Object.keys(vm.$data||{}).slice(0,20),methods:Object.keys(vm.$options?.methods||{}).slice(0,15)};
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=walk(vm.$children[i],d+1,path+'/'+i);
            if(r)return r;
        }
        return null;
    }
    return walk(vm,0,'root');
})()""")
print(f"  {guide_comp}")

# ============================================================
# Step 2: 获取guide组件的完整data
# ============================================================
print("\nStep 2: guide组件data")
guide_data = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function walk(vm,d){
        if(d>10)return null;
        var n=vm.$options?.name||'';
        var childNames=(vm.$children||[]).map(function(c){return c.$options?.name||''});
        var hasRadio=childNames.some(function(n){return n.includes('radio')});
        var hasForm=childNames.some(function(n){return n==='ElForm'||n==='form-item'});
        if(n==='index'&&hasRadio&&hasForm){
            var data=vm.$data||{};
            var result={};
            Object.keys(data).forEach(function(k){
                var v=data[k];
                if(v===null||v===undefined||v===''||v===false)return;
                if(Array.isArray(v))result[k]='A['+v.length+']:'+JSON.stringify(v).substring(0,60);
                else if(typeof v==='object')result[k]=JSON.stringify(v).substring(0,80);
                else result[k]=v;
            });
            result._methods=Object.keys(vm.$options?.methods||{});
            return result;
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=walk(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    return walk(vm,0);
})()""")
print(f"  {json.dumps(guide_data, ensure_ascii=False)[:600] if isinstance(guide_data,dict) else guide_data}")

# ============================================================
# Step 3: 查找cascader组件并设置地址
# ============================================================
print("\nStep 3: 设置地址cascader")
addr_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function walk(vm,d){
        if(d>10)return null;
        var n=vm.$options?.name||'';
        var childNames=(vm.$children||[]).map(function(c){return c.$options?.name||''});
        var hasRadio=childNames.some(function(n){return n.includes('radio')});
        var hasForm=childNames.some(function(n){return n==='ElForm'||n==='form-item'});
        if(n==='index'&&hasRadio&&hasForm){
            // 这是guide组件
            var guideComp=vm;
            
            // 方法1: 直接设置data中的地址字段
            var d=guideComp.$data;
            var addrKeys=Object.keys(d).filter(function(k){
                return k.includes('addr')||k.includes('Addr')||k.includes('dist')||k.includes('area')||k.includes('region')||k.includes('location');
            });
            
            // 方法2: 找form model
            var elForm=null;
            function findElForm(vm,d){
                if(d>8)return;
                if(vm.$options?.name==='ElForm'){elForm=vm;return}
                for(var i=0;i<(vm.$children||[]).length;i++)findElForm(vm.$children[i],d+1);
            }
            findElForm(guideComp,0);
            
            var formModel=null;
            if(elForm)formModel=elForm.model||{};
            
            // 方法3: 找tne-data-picker
            var pickers=[];
            function findPicker(vm,d){
                if(d>15)return;
                var n=vm.$options?.name||'';
                if(n==='tne-data-picker'||n==='ElCascader'){
                    pickers.push({comp:vm,name:n,value:vm.value||vm.$data?.value});
                }
                for(var i=0;i<(vm.$children||[]).length;i++)findPicker(vm.$children[i],d+1);
            }
            findPicker(guideComp,0);
            
            // 设置picker值
            for(var i=0;i<pickers.length;i++){
                var p=pickers[i].comp;
                p.$emit('input',['450000','450100','450103']);
                p.$emit('change',['450000','450100','450103']);
            }
            
            // 设置form model地址字段
            if(formModel){
                var fmKeys=Object.keys(formModel);
                var fmAddrKeys=fmKeys.filter(function(k){
                    return k.includes('addr')||k.includes('Addr')||k.includes('dist')||k.includes('area')||k.includes('region');
                });
                for(var i=0;i<fmAddrKeys.length;i++){
                    guideComp.$set(formModel,fmAddrKeys[i],['450000','450100','450103']);
                }
            }
            
            return {
                addrDataKeys:addrKeys,
                formModelKeys:formModel?Object.keys(formModel):[],
                fmAddrKeys:formModel?Object.keys(formModel).filter(function(k){return k.includes('addr')||k.includes('dist')||k.includes('area')}):[],
                pickersFound:pickers.length,
                pickerValues:pickers.map(function(p){return p.value})
            };
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=walk(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    return walk(vm,0);
})()""")
print(f"  {json.dumps(addr_result, ensure_ascii=False)[:500] if isinstance(addr_result,dict) else addr_result}")

# ============================================================
# Step 4: 点击下一步
# ============================================================
print("\nStep 4: 点击下一步")
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

# 检查验证错误
errors = ev("""(function(){
    var errs=document.querySelectorAll('.el-form-item__error');
    var r=[];
    for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}
    return r;
})()""")
print(f"  验证错误: {errors}")

# 检查路由
cur = ev("location.hash")
print(f"  路由: {cur}")

# ============================================================
# Step 5: 检查组件
# ============================================================
print("\nStep 5: 检查组件")
comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    return {flowControl:!!fc,withoutName:!!wn,hash:location.hash};
})()""")
print(f"  {comps}")

if isinstance(comps, dict) and comps.get('withoutName'):
    print("  点击toNotName...")
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
