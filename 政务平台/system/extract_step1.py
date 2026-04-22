#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""提取表单字段元数据 - Step1: form items"""
import json, time, requests, websocket, os

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schemas")
os.makedirs(SCHEMA_DIR, exist_ok=True)

def ev(js, timeout=15):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
    ws.settimeout(timeout + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            ws.close()
            return r.get("result", {}).get("result", {}).get("value")

# Step1: form items
items = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()?.replace(/[：:]$/,'')||'';
        if(!label)continue;
        var hasCascader=!!items[i].querySelector('.el-cascader,[class*="cascader"]');
        var hasTneCascader=!!items[i].querySelector('[class*="tne-data-cascader"],[class*="tneCascader"]');
        var hasSelect=!!items[i].querySelector('.el-select,[class*="tne-select"]');
        var hasInput=!!items[i].querySelector('input.el-input__inner');
        var hasRadio=!!items[i].querySelector('.el-radio');
        var hasCheckbox=!!items[i].querySelector('.el-checkbox');
        var hasBtn=!!items[i].querySelector('button');
        var hasDate=!!items[i].querySelector('.el-date-editor,[class*="date"]');
        var hasNumber=!!items[i].querySelector('.el-input-number');
        var hasTextarea=!!items[i].querySelector('textarea');
        var inp=items[i].querySelector('input.el-input__inner,textarea');
        var value=inp?.value||'';
        var ph=inp?.getAttribute('placeholder')||'';
        var errEl=items[i].querySelector('.el-form-item__error');
        var err=errEl?.textContent?.trim()||'';
        var compType='unknown';
        if(hasTneCascader)compType='tne-data-cascader';
        else if(hasCascader)compType='el-cascader';
        else if(hasBtn&&hasSelect)compType='select-with-dialog';
        else if(hasBtn)compType='button-dialog';
        else if(hasSelect)compType='el-select';
        else if(hasRadio)compType='el-radio-group';
        else if(hasCheckbox)compType='el-checkbox-group';
        else if(hasDate)compType='el-date-picker';
        else if(hasNumber)compType='el-input-number';
        else if(hasTextarea)compType='el-textarea';
        else if(hasInput)compType='el-input';
        r.push({i:i,label:label,compType:compType,value:value?.substring(0,60)||'',placeholder:ph,error:err});
    }
    return r;
})()""")

print("=== FORM ITEMS ===")
for f in (items or []):
    req = "★" if f.get('error') else " "
    print(f"  {req} [{f['i']:2d}] {f['label']:20s} {f['compType']:20s} val={f.get('value','')[:25]} ph={f.get('placeholder','')[:20]} err={f.get('error','')}")

with open(os.path.join(SCHEMA_DIR, "form_items.json"), "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

# Step2: bdi keys
bdi = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var comp=find(vm,0);
    if(!comp)return null;
    var bdi=comp.$data.businessDataInfo;
    var keys=Object.keys(bdi).sort();
    var sample={};
    for(var i=0;i<keys.length;i++){
        var v=bdi[keys[i]];
        if(v!==null&&v!==undefined&&v!=='')sample[keys[i]]=String(v).substring(0,80);
    }
    return {totalKeys:keys.length,filledKeys:Object.keys(sample).length,sample:sample};
})()""")

print("\n=== businessDataInfo ===")
if bdi:
    print(f"  总字段: {bdi.get('totalKeys')}, 有值: {bdi.get('filledKeys')}")
    for k, v in bdi.get('sample', {}).items():
        print(f"  {k}: {v}")
    with open(os.path.join(SCHEMA_DIR, "bdi_fields.json"), "w", encoding="utf-8") as f:
        json.dump(bdi, f, ensure_ascii=False, indent=2)

# Step3: residenceForm
ri = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return null;
    var form=ri.residenceForm||ri.$data?.residenceForm||{};
    var keys=Object.keys(form).sort();
    var sample={};
    for(var i=0;i<keys.length;i++){
        var v=form[keys[i]];
        if(v!==null&&v!==undefined&&v!=='')sample[keys[i]]=String(v).substring(0,80);
    }
    return {totalKeys:keys.length,filledKeys:Object.keys(sample).length,sample:sample,methods:Object.keys(ri.$options?.methods||{}).filter(function(m){return !m.startsWith('_')}).slice(0,30)};
})()""")

print("\n=== residenceForm ===")
if ri:
    print(f"  总字段: {ri.get('totalKeys')}, 有值: {ri.get('filledKeys')}")
    print(f"  方法: {ri.get('methods', [])}")
    for k, v in ri.get('sample', {}).items():
        print(f"  {k}: {v}")
    with open(os.path.join(SCHEMA_DIR, "residence_form.json"), "w", encoding="utf-8") as f:
        json.dump(ri, f, ensure_ascii=False, indent=2)

# Step4: busineseForm
bi = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return null;
    var form=bi.busineseForm||bi.$data?.busineseForm||{};
    var keys=Object.keys(form).sort();
    var sample={};
    for(var i=0;i<keys.length;i++){
        var v=form[keys[i]];
        if(v!==null&&v!==undefined&&v!=='')sample[keys[i]]=String(v).substring(0,80);
    }
    return {totalKeys:keys.length,filledKeys:Object.keys(sample).length,sample:sample,methods:Object.keys(bi.$options?.methods||{}).filter(function(m){return !m.startsWith('_')}).slice(0,30)};
})()""")

print("\n=== busineseForm ===")
if bi:
    print(f"  总字段: {bi.get('totalKeys')}, 有值: {bi.get('filledKeys')}")
    print(f"  方法: {bi.get('methods', [])}")
    for k, v in bi.get('sample', {}).items():
        print(f"  {k}: {v}")
    with open(os.path.join(SCHEMA_DIR, "businese_form.json"), "w", encoding="utf-8") as f:
        json.dump(bi, f, ensure_ascii=False, indent=2)

# Step5: 验证规则
rules = ev("""(function(){
    var forms=document.querySelectorAll('.el-form');
    var allRules={};
    for(var i=0;i<forms.length;i++){
        var comp=forms[i].__vue__;
        if(!comp||!comp.rules)continue;
        var formName=comp.$parent?.$options?.name||comp.$options?.name||'form_'+i;
        var r={};
        var keys=Object.keys(comp.rules);
        for(var j=0;j<keys.length;j++){
            var rl=comp.rules[keys[j]];
            var arr=[];
            for(var k=0;k<rl.length;k++){
                arr.push({required:!!rl[k].required,message:rl[k].message||'',trigger:rl[k].trigger||'',type:rl[k].type||''});
            }
            r[keys[j]]=arr;
        }
        allRules[formName]=r;
    }
    return allRules;
})()""")

print("\n=== 验证规则 ===")
if rules:
    for formName, formRules in rules.items():
        print(f"  [{formName}]")
        for prop, ruleList in formRules.items():
            for rule in ruleList:
                req = "★" if rule.get('required') else " "
                print(f"    {req} {prop}: {rule.get('message', '')} (trigger={rule.get('trigger', '')})")
    with open(os.path.join(SCHEMA_DIR, "validation_rules.json"), "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

print("\n✅ 提取完成，数据保存在 schemas/ 目录")
