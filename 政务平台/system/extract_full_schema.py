#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全盘提取页面所有表单字段：label、组件类型、当前值、选项、验证规则、所属form"""
import json, requests, websocket, time

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)

def ev(js, timeout=15):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
    ws.settimeout(timeout + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r.get("result", {}).get("result", {}).get("value")

# 先刷新确保干净状态
print("刷新页面...")
ev("location.reload()")
time.sleep(8)

# ====== 1. 提取所有el-form-item的完整信息 ======
print("\n===== 1. 所有表单字段 =====")
fields = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var comp=items[i].__vue__;
        var lb=items[i].querySelector('.el-form-item__label');
        if(!lb)continue;
        var label=lb.textContent.trim();
        var prop=comp?.prop||'';
        
        // 判断组件类型
        var compType='unknown';
        var currentValue='';
        var options=[];
        
        if(items[i].querySelector('.tne-data-picker')){
            compType='tne-data-picker';
            var inp=items[i].querySelector('input');
            currentValue=inp?.value||'';
        } else if(items[i].querySelector('.tne-select-tree')){
            compType='tne-select-tree';
            var inp=items[i].querySelector('input');
            currentValue=inp?.value||'';
        } else if(items[i].querySelector('.el-select')){
            compType='el-select';
            var sv=items[i].querySelector('.el-select').__vue__;
            currentValue=sv?.value||'';
            // 获取选项
            try{
                var opts=sv?.options||[];
                for(var j=0;j<opts.length;j++){
                    options.push({value:opts[j].value||'',label:opts[j].label||''});
                }
            }catch(e){}
        } else if(items[i].querySelector('.el-radio-group')){
            compType='el-radio-group';
            var rg=items[i].querySelector('.el-radio-group').__vue__;
            currentValue=rg?.value||'';
            var radios=items[i].querySelectorAll('.el-radio');
            for(var j=0;j<radios.length;j++){
                var rLabel=radios[j].textContent?.trim()||'';
                var rInput=radios[j].querySelector('input');
                var rVal=rInput?.value||'';
                options.push({value:rVal,label:rLabel});
            }
        } else if(items[i].querySelector('.el-input')){
            compType='el-input';
            var inp=items[i].querySelector('input');
            currentValue=inp?.value||'';
        } else if(items[i].querySelector('.tni-business-range')){
            compType='tni-business-range';
        } else if(items[i].querySelector('button')){
            compType='button';
        }
        
        // 验证错误
        var errEl=items[i].querySelector('.el-form-item__error');
        var error=errEl?.textContent?.trim()||'';
        
        // 是否必填
        var required=!!items[i].querySelector('.el-form-item__label--required, [class*="required"]');
        
        result.push({
            idx:i,
            label:label,
            prop:prop,
            compType:compType,
            currentValue:currentValue,
            options:options.slice(0,20),
            error:error,
            required:required
        });
    }
    return result;
})()""", timeout=20)

for f in (fields or []):
    opts_str = ""
    if f.get('options'):
        opts_str = f" options={f['options'][:5]}"
    req_str = " *必填" if f.get('required') else ""
    err_str = f" ❌{f['error']}" if f.get('error') else ""
    print(f"  [{f['idx']}] {f['label']}: type={f['compType']}, prop={f['prop']}, val='{f['currentValue']}'{opts_str}{req_str}{err_str}")

# ====== 2. 提取各form组件的数据模型 ======
print("\n===== 2. 各组件form数据 =====")
forms = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    
    var fc=find(vm,0);
    var ri=findComp(vm,'residence-information',0);
    var bi=findComp(vm,'businese-info',0);
    
    // businessDataInfo
    var bdi=fc?.$data?.businessDataInfo||{};
    var bdiKeys=Object.keys(bdi);
    var bdiData={};
    for(var i=0;i<bdiKeys.length;i++){
        var v=bdi[bdiKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')bdiData[bdiKeys[i]]=v;
        else if(v===null)bdiData[bdiKeys[i]]=null;
        else if(t==='object')bdiData[bdiKeys[i]]=t+':'+(Array.isArray(v)?'['+v.length+']':'{'+Object.keys(v).length+'}');
    }
    
    // residenceForm
    var rf=ri?.residenceForm||{};
    var rfData={};
    var rfKeys=Object.keys(rf);
    for(var i=0;i<rfKeys.length;i++){
        var v=rf[rfKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')rfData[rfKeys[i]]=v;
        else if(v===null)rfData[rfKeys[i]]=null;
        else if(t==='object')rfData[rfKeys[i]]=t+':'+(Array.isArray(v)?'['+v.length+']':'{'+Object.keys(v).length+'}');
    }
    
    // busineseForm
    var bf=bi?.busineseForm||{};
    var bfData={};
    var bfKeys=Object.keys(bf);
    for(var i=0;i<bfKeys.length;i++){
        var v=bf[bfKeys[i]];
        var t=typeof v;
        if(t==='string'||t==='number'||t==='boolean')bfData[bfKeys[i]]=v;
        else if(v===null)bfData[bfKeys[i]]=null;
        else if(t==='object')bfData[bfKeys[i]]=t+':'+(Array.isArray(v)?'['+v.length+']':'{'+Object.keys(v).length+'}');
    }
    
    // ri的其他data
    var riData={};
    var riKeys=Object.keys(ri?.$data||{});
    var important=['productionDistList','distList','provincesProduction','deepForm'];
    for(var i=0;i<riKeys.length;i++){
        if(important.includes(riKeys[i])){
            var v=ri.$data[riKeys[i]];
            riData[riKeys[i]]=typeof v==='object'?(Array.isArray(v)?'['+v?.length+']':'{'+Object.keys(v||{}).length+'}'):v;
        }
    }
    
    return {bdi:bdiData, residenceForm:rfData, busineseForm:bfData, riExtra:riData};
})()""", timeout=20)

if forms:
    print("\n--- businessDataInfo ---")
    for k,v in sorted(forms.get('bdi',{}).items()):
        print(f"  {k}: {v}")
    print("\n--- residenceForm ---")
    for k,v in sorted(forms.get('residenceForm',{}).items()):
        print(f"  {k}: {v}")
    print("\n--- busineseForm ---")
    for k,v in sorted(forms.get('busineseForm',{}).items()):
        print(f"  {k}: {v}")
    print("\n--- riExtra ---")
    for k,v in sorted(forms.get('riExtra',{}).items()):
        print(f"  {k}: {v}")

# ====== 3. 保存完整数据 ======
output = {
    "fields": fields,
    "forms": forms,
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
}
with open("g:/UFO/政务平台/schemas/full_page_extract.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n已保存到 schemas/full_page_extract.json")

ws.close()
