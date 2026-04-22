#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复: cascader值同步到form model + 正确保存"""
import json, time, requests, websocket

def ev(js, timeout=8):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=6)
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
# Step 1: 分析save方法签名
# ============================================================
print("Step 1: 分析save方法")
save_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return{error:'no_comp'};
    var saveSrc=comp.$options?.methods?.save?.toString()||'';
    var saveAndSubmitSrc=comp.$options?.methods?.saveAndSubmit?.toString()||'';
    return{
        saveSrc:saveSrc.substring(0,500),
        saveAndSubmitSrc:saveAndSubmitSrc.substring(0,500)
    };
})()""")
print(f"  save方法: {save_info}")

# ============================================================
# Step 2: 修复cascader同步 - 从cascader selected同步到form model
# ============================================================
print("\nStep 2: 修复cascader同步")

sync_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return{error:'no_comp'};
    var bdi=comp.$data.businessDataInfo;
    
    // 找所有cascader组件
    var items=document.querySelectorAll('.el-form-item');
    var syncs=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var cascader=items[i].querySelector('.tne-data-picker');
        if(!cascader)continue;
        var cComp=cascader.__vue__;
        if(!cComp)continue;
        
        var selected=cComp.selected||cComp.$data?.selected||[];
        var value=cComp.value||cComp.modelValue||cComp.$props?.value||[];
        
        if(label.includes('企业住所')&&!label.includes('详细')){
            // 从selected提取区码
            var distCode='';
            var distName='';
            var provinceName='';
            var cityName='';
            var fullAddr='';
            for(var j=0;j<selected.length;j++){
                var s=selected[j];
                if(j===0){provinceName=s.text||s.allName||'';fullAddr+=provinceName;}
                if(j===1){cityName=s.text||s.allName||'';fullAddr+='/'+cityName;}
                if(j===2){distCode=s.value||s.id||'';distName=s.text||s.allName||'';fullAddr+='/'+distName;}
            }
            if(distCode){
                comp.$set(bdi,'distCode',distCode);
                comp.$set(bdi,'distCodeName',distName);
                comp.$set(bdi,'fisDistCode',distCode);
                comp.$set(bdi,'address',fullAddr);
                comp.$set(bdi,'isSelectDistCode','1');
                comp.$set(bdi,'havaAdress','0');
                syncs.push({field:'企业住所',distCode:distCode,distName:distName,fullAddr:fullAddr});
            }
        }
        
        if(label.includes('生产经营地址')&&!label.includes('详细')){
            var regionCode='';
            var regionName='';
            var fullAddr2='';
            for(var j=0;j<selected.length;j++){
                var s=selected[j];
                if(j===0){fullAddr2+=s.text||s.allName||'';}
                if(j===1){fullAddr2+='/'+(s.text||s.allName||'');}
                if(j===2){regionCode=s.value||s.id||'';regionName=s.text||s.allName||'';fullAddr2+='/'+regionName;}
            }
            if(regionCode){
                comp.$set(bdi,'regionCode',regionCode);
                comp.$set(bdi,'regionName',regionName);
                comp.$set(bdi,'businessAddress',fullAddr2);
                syncs.push({field:'生产经营地址',regionCode:regionCode,regionName:regionName,fullAddr:fullAddr2});
            }
        }
    }
    
    // 也设置详细地址
    if(!bdi.detAddress||bdi.detAddress==='null'){
        comp.$set(bdi,'detAddress','民族大道100号');
    }
    if(!bdi.detBusinessAddress||bdi.detBusinessAddress==='null'){
        comp.$set(bdi,'detBusinessAddress','民族大道100号');
    }
    
    comp.$forceUpdate();
    return syncs;
})()""")
print(f"  同步结果: {sync_result}")

# ============================================================
# Step 3: 修复生产经营地址cascader（当前是容县，需改为青秀区）
# ============================================================
print("\nStep 3: 修复生产经营地址cascader")

fix_result = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('生产经营地址')&&!label.includes('详细')){
            var cascader=items[i].querySelector('.tne-data-picker');
            if(!cascader)continue;
            var comp=cascader.__vue__;
            if(!comp)continue;
            
            // 设置value为青秀区
            var val=['450000','450100','450103'];
            comp.$emit('input',val);
            comp.$emit('change',val);
            
            // 也设selected
            comp.$set(comp.$data,'selected',[
                {allName:'广西壮族自治区',id:'450000',isStreet:'N',value:'450000',text:'广西壮族自治区'},
                {allName:'南宁市',id:'450100',parentId:'450000',isStreet:'N',value:'450100',text:'南宁市'},
                {allName:'南宁市青秀区',id:'450103',parentId:'450100',isStreet:'N',value:'450103',text:'青秀区'}
            ]);
            comp.$set(comp.$data,'inputSelected',comp.$data.selected);
            
            return{fixed:true,value:val};
        }
    }
})()""")
print(f"  修复结果: {fix_result}")

# 重新同步
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    comp.$set(bdi,'regionCode','450103');
    comp.$set(bdi,'regionName','青秀区');
    comp.$set(bdi,'businessAddress','广西壮族自治区/南宁市/青秀区');
    comp.$set(bdi,'detBusinessAddress','民族大道100号');
    comp.$forceUpdate();
})()""")

# ============================================================
# Step 4: 验证字段值
# ============================================================
print("\nStep 4: 验证字段")
fields = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    return{
        distCode:bdi.distCode,
        distCodeName:bdi.distCodeName,
        address:bdi.address,
        detAddress:bdi.detAddress,
        regionCode:bdi.regionCode,
        regionName:bdi.regionName,
        businessAddress:bdi.businessAddress,
        detBusinessAddress:bdi.detBusinessAddress,
        itemIndustryTypeCode:bdi.itemIndustryTypeCode,
        businessArea:bdi.businessArea?.substring(0,30),
        entType:bdi.entType||bdi.flowData?.entType
    };
})()""")
print(f"  字段值: {fields}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 5: 保存 - 用正确参数
# ============================================================
print("\nStep 5: 保存")

# 先看保存按钮
save_btns = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    var r=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('保存')||t.includes('下一步')||t.includes('暂存'))&&btns[i].offsetParent!==null){
            r.push({idx:i,text:t,disabled:btns[i].disabled||btns[i].classList.contains('is-disabled')});
        }
    }
    return r;
})()""")
print(f"  保存按钮: {save_btns}")

# 尝试通过Vue方法保存，参数改为对象
save_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return{error:'no_comp'};
    
    // save方法签名分析：可能是save(btn, callback, sign)
    // sign='working'表示草稿
    // 尝试不同参数
    try{
        // 方式1: save(btn, cb, 'working')
        comp.save(null, null, 'working');
        return{called:'save(null,null,working)'};
    }catch(e1){
        try{
            // 方式2: save({sign:'working'})
            comp.save({sign:'working'});
            return{called:'save({sign:working})'};
        }catch(e2){
            try{
                // 方式3: saveAndSubmit
                comp.saveAndSubmit();
                return{called:'saveAndSubmit()'};
            }catch(e3){
                // 方式4: 点击保存按钮
                var btns=document.querySelectorAll('button,.el-button');
                for(var i=0;i<btns.length;i++){
                    var t=btns[i].textContent?.trim()||'';
                    if(t.includes('保存并下一步')&&btns[i].offsetParent!==null&&!btns[i].disabled){
                        btns[i].click();
                        return{clicked:t};
                    }
                }
                for(var i=0;i<btns.length;i++){
                    var t=btns[i].textContent?.trim()||'';
                    if(t.includes('保存')&&btns[i].offsetParent!==null&&!btns[i].disabled){
                        btns[i].click();
                        return{clicked:t};
                    }
                }
                return{errors:[e1.message,e2.message,e3.message]};
            }
        }
    }
})()""", timeout=15)
print(f"  保存结果: {save_result}")
time.sleep(5)

# 检查保存后状态
errors_after = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  保存后验证错误: {errors_after}")

msg = ev("""(function(){
    var msgs=document.querySelectorAll('.el-message,[class*="message"]');
    var r=[];
    for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}
    return r;
})()""")
print(f"  消息提示: {msg}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
