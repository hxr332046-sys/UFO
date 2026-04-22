#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证cascader值 + 尝试保存表单"""
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
# Step 1: 检查所有关键字段值
# ============================================================
print("Step 1: 检查关键字段值")
fields = ev("""(function(){
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
    var fd=bdi.flowData||{};
    var keys=Object.keys(bdi);
    var result={};
    // 关键字段
    var important=['registerCapital','entPhone','postcode','distCode','distCodeName',
        'address','detAddress','regionCode','detBusinessAddress',
        'itemIndustryTypeCode','industryTypeName','businessArea','busiAreaCode',
        'busiPeriod','busiDateEnd','multiIndustry','industryId',
        'entType','entTypeName','busType','shouldInvestWay',
        'fisDistCode','havaAdress','isSelectDistCode','isBusinessRegMode',
        'secretaryServiceEnt','namePreFlag','partnerNum'];
    for(var i=0;i<important.length;i++){
        var k=important[i];
        if(k in bdi)result[k]=String(bdi[k]).substring(0,50);
        else if(k in fd)result[k]=String(fd[k]).substring(0,50);
    }
    return result;
})()""")
print(f"  关键字段: {fields}")

# ============================================================
# Step 2: 检查cascader组件值
# ============================================================
print("\nStep 2: cascader组件值")
cascader_vals = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业住所')||label.includes('生产经营地址')){
            var cascader=items[i].querySelector('.tne-data-picker,[class*="cascader"]');
            if(cascader){
                var comp=cascader.__vue__;
                result.push({
                    label:label.substring(0,15),
                    value:comp.value||comp.modelValue||comp.$props?.value||'',
                    selected:comp.selected||'',
                    inputSelected:comp.inputSelected||'',
                    presentText:comp.presentText||comp.$data?.inputSelected||''
                });
            }
        }
    }
    return result;
})()""")
print(f"  cascader值: {cascader_vals}")

# ============================================================
# Step 3: 检查验证状态
# ============================================================
print("\nStep 3: 验证状态")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 4: 尝试保存（草稿）
# ============================================================
print("\nStep 4: 保存草稿")
save_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return{error:'no_comp'};
    
    // 检查save方法
    var methods=comp.$options?.methods||{};
    var methodNames=Object.keys(methods);
    var saveMethods=methodNames.filter(function(m){return m.includes('save')||m.includes('Save')||m.includes('submit')||m.includes('Submit')});
    
    // 尝试调用save
    if(typeof comp.save==='function'){
        try{
            comp.save('working');
            return{called:'save',args:'working',methods:saveMethods};
        }catch(e){
            return{error:e.message,methods:saveMethods};
        }
    }
    
    // 找保存按钮
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('保存')||t.includes('暂存'))&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:t,methods:saveMethods};
        }
    }
    
    return{error:'no_save',methods:saveMethods};
})()""", timeout=15)
print(f"  保存结果: {save_result}")
time.sleep(3)

# ============================================================
# Step 5: 检查保存后状态
# ============================================================
print("\nStep 5: 保存后状态")
errors_after = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors_after}")

# 检查是否有成功提示
msg = ev("""(function(){
    var msgs=document.querySelectorAll('.el-message,[class*="message"],[class*="notification"],[class*="toast"]');
    var r=[];
    for(var i=0;i<msgs.length;i++){
        var t=msgs[i].textContent?.trim()||'';
        if(t)r.push(t.substring(0,50));
    }
    return r;
})()""")
print(f"  消息提示: {msg}")

# 检查hash是否变化
hash = ev("location.hash")
print(f"  当前路由: {hash}")

print("\n✅ 完成")
