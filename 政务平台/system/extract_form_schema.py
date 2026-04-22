#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
表单框架提取器 — 从当前页面提取所有字段的完整元数据
生成框架定义文件，供脚本/LLM执行器使用
"""
import json, time, requests, websocket, os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schemas")
os.makedirs(SCHEMA_DIR, exist_ok=True)

def get_page_ws():
    for attempt in range(5):
        try:
            pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "") and "chrome-error" not in p.get("url", "")]
            if not page:
                page = [p for p in pages if p.get("type") == "page" and "chrome-error" not in p.get("url", "")]
            if not page: time.sleep(2); continue
            return websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        except: time.sleep(2)
    return None

_mid = 0
def ev(js, timeout=15):
    global _mid; _mid += 1; mid = _mid
    ws = get_page_ws()
    if not ws: return "ERROR:no_page"
    try:
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                            "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
        ws.settimeout(timeout + 2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                ws.close()
                return r.get("result", {}).get("result", {}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

print("=" * 60)
print("表单框架提取器")
print("=" * 60)

# 检查页面
page_info = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
print(f"页面: {page_info}")

if not page_info or 'basic-info' not in (page_info.get('hash') or ''):
    print("ERROR: 不在basic-info页面，请先导航到设立登记表单")
    exit(1)

# ============================================================
# 提取完整表单元数据
# ============================================================
print("\n--- 提取表单字段元数据 ---")

schema = ev("""(function(){
    var FC = 'function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||\"\";if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}';
    var app=document.getElementById('app');var vm=app.__vue__;
    
    // 找flow-control组件
    function findFC(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFC(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var fc=findFC(vm,0);
    if(!fc)return {error:'no_flow_control'};
    
    var bdi=fc.$data.businessDataInfo;
    
    // 找residence-information组件
    var ri=findComp(vm,'residence-information',0);
    // 找businese-info组件
    var bi=findComp(vm,'businese-info',0);
    
    // 收集所有form-item
    var items=document.querySelectorAll('.el-form-item');
    var fields=[];
    
    for(var i=0;i<items.length;i++){
        var labelEl=items[i].querySelector('.el-form-item__label');
        var label=labelEl?.textContent?.trim()||'';
        if(!label)continue;
        
        // 去掉冒号
        label=label.replace(/[：:]$/,'');
        
        // 获取Vue组件信息
        var formItemComp=items[i].__vue__;
        var prop=formItemComp?.prop||formItemComp?.$props?.prop||'';
        
        // 判断组件类型
        var hasCascader=!!items[i].querySelector('.el-cascader,[class*="cascader"]');
        var hasTneCascader=!!items[i].querySelector('[class*="tne-data-cascader"],[class*="tneCascader"]');
        var hasSelect=!!items[i].querySelector('.el-select,[class*="tne-select"]');
        var hasInput=!!items[i].querySelector('input.el-input__inner');
        var hasTextarea=!!items[i].querySelector('textarea');
        var hasRadio=!!items[i].querySelector('.el-radio');
        var hasCheckbox=!!items[i].querySelector('.el-checkbox');
        var hasBtn=!!items[i].querySelector('button');
        var hasDate=!!items[i].querySelector('.el-date-editor,[class*="date"]');
        var hasNumber=!!items[i].querySelector('.el-input-number');
        
        // 获取当前值
        var currentValue='';
        if(hasInput||hasNumber){
            var inp=items[i].querySelector('input.el-input__inner');
            currentValue=inp?.value||'';
        }else if(hasTextarea){
            var ta=items[i].querySelector('textarea');
            currentValue=ta?.value||'';
        }else if(hasCascader||hasTneCascader){
            var casText=items[i].querySelector('.el-input__inner');
            currentValue=casText?.value||'';
        }else if(hasSelect&&!hasCascader){
            var selText=items[i].querySelector('.el-input__inner');
            currentValue=selText?.value||'';
        }else if(hasRadio){
            var checked=items[i].querySelector('.el-radio.is-checked');
            currentValue=checked?.textContent?.trim()||'';
        }else if(hasCheckbox){
            var checked2=items[i].querySelectorAll('.el-checkbox.is-checked');
            var cbs=[];
            for(var j=0;j<checked2.length;j++)cbs.push(checked2[j].textContent?.trim()||'');
            currentValue=cbs.join(',');
        }
        
        // 获取验证错误
        var errorEl=items[i].querySelector('.el-form-item__error');
        var errorMsg=errorEl?.textContent?.trim()||'';
        
        // 获取验证规则
        var rules=[];
        var formComp=formItemComp?.$parent;
        if(formComp&&formComp.rules){
            var fieldRules=formComp.rules[prop];
            if(fieldRules){
                for(var j=0;j<fieldRules.length;j++){
                    rules.push({required:!!fieldRules[j].required,message:fieldRules[j].message||'',trigger:fieldRules[j].trigger||''});
                }
            }
        }
        
        // 确定组件类型
        var compType='unknown';
        if(hasTneCascader) compType='tne-data-cascader';
        else if(hasCascader) compType='el-cascader';
        else if(hasBtn&&hasSelect) compType='select-with-dialog';
        else if(hasBtn) compType='button-dialog';
        else if(hasSelect) compType='el-select';
        else if(hasRadio) compType='el-radio-group';
        else if(hasCheckbox) compType='el-checkbox-group';
        else if(hasDate) compType='el-date-picker';
        else if(hasNumber) compType='el-input-number';
        else if(hasTextarea) compType='el-textarea';
        else if(hasInput) compType='el-input';
        
        // 获取select选项
        var options=[];
        if(compType==='el-select'||compType==='el-radio-group'){
            var opts=items[i].querySelectorAll('.el-select-dropdown__item,.el-radio');
            for(var j=0;j<opts.length;j++){
                var ot=opts[j].textContent?.trim()||'';
                if(ot)options.push(ot);
            }
            // 如果select还没打开，从Vue组件获取
            if(options.length===0){
                var selComp=items[i].querySelector('.el-select')?.__vue__;
                if(selComp&&selComp.options){
                    for(var j=0;j<selComp.options.length;j++){
                        options.push(selComp.options[j].label||selComp.options[j].currentLabel||'');
                    }
                }
            }
        }
        
        // 获取placeholder
        var placeholder='';
        var phEl=items[i].querySelector('input,textarea');
        if(phEl)placeholder=phEl.getAttribute('placeholder')||'';
        
        // 获取所属form
        var formName='';
        if(ri){
            // 检查是否在residence-information内
            var riEl=ri.$el;
            if(riEl&&riEl.contains(items[i]))formName='residenceForm';
        }
        if(bi){
            var biEl=bi.$el;
            if(biEl&&biEl.contains(items[i]))formName='busineseForm';
        }
        if(!formName)formName='businessDataInfo';
        
        fields.push({
            index:i,
            label:label,
            prop:prop,
            compType:compType,
            currentValue:currentValue?.substring(0,80)||'',
            placeholder:placeholder,
            errorMsg:errorMsg,
            required:rules.some(function(r){return r.required}),
            rules:rules.slice(0,5),
            options:options.slice(0,20),
            formName:formName
        });
    }
    
    // 收集bdi所有字段名
    var bdiKeys=Object.keys(bdi||{}).filter(function(k){
        var v=bdi[k];
        return v!==null&&v!==undefined&&v!=='';
    }).sort();
    
    // 收集residenceForm字段
    var riForm=ri?ri.residenceForm||ri.$data?.residenceForm:null;
    var riKeys=riForm?Object.keys(riForm).filter(function(k){
        var v=riForm[k];return v!==null&&v!==undefined&&v!=='';
    }).sort():[];
    
    // 收集busineseForm字段
    var biForm=bi?bi.busineseForm||bi.$data?.busineseForm:null;
    var biKeys=biForm?Object.keys(biForm).filter(function(k){
        var v=biForm[k];return v!==null&&v!==undefined&&v!=='';
    }).sort():[];
    
    return {
        fields:fields,
        bdiKeys:bdiKeys,
        bdiSample:Object.fromEntries(bdiKeys.slice(0,50).map(function(k){return [k,String(bdi[k]).substring(0,60)]})),
        riKeys:riKeys,
        riSample:riForm?Object.fromEntries(riKeys.slice(0,30).map(function(k){return [k,String(riForm[k]).substring(0,60)]})):{},
        biKeys:biKeys,
        biSample:biForm?Object.fromEntries(biKeys.slice(0,30).map(function(k){return [k,String(biForm[k]).substring(0,60)]})):{}
    };
})()""", timeout=20)

if not schema or isinstance(schema, str) and schema.startswith("ERROR"):
    print(f"提取失败: {schema}")
    exit(1)

print(f"  字段数: {len(schema.get('fields', []))}")
print(f"  bdi字段数: {len(schema.get('bdiKeys', []))}")
print(f"  residenceForm字段数: {len(schema.get('riKeys', []))}")
print(f"  busineseForm字段数: {len(schema.get('biKeys', []))}")

# 保存原始提取数据
raw_path = os.path.join(SCHEMA_DIR, "basic_info_raw.json")
with open(raw_path, "w", encoding="utf-8") as f:
    json.dump(schema, f, ensure_ascii=False, indent=2)
print(f"  原始数据已保存: {raw_path}")

# 打印字段清单
print("\n--- 字段清单 ---")
for field in schema.get('fields', []):
    req = "★" if field.get('required') else " "
    ct = field.get('compType', '?')
    err = f" ← {field['errorMsg']}" if field.get('errorMsg') else ""
    val = f" [{field['currentValue'][:30]}]" if field.get('currentValue') else ""
    print(f"  {req} [{field['index']:2d}] {field['label']:20s} {ct:20s} prop={field.get('prop','')}{val}{err}")

# 打印bdi字段
print("\n--- businessDataInfo 字段 ---")
for k, v in schema.get('bdiSample', {}).items():
    print(f"  {k}: {v}")

print("\n--- residenceForm 字段 ---")
for k, v in schema.get('riSample', {}).items():
    print(f"  {k}: {v}")

print("\n--- busineseForm 字段 ---")
for k, v in schema.get('biSample', {}).items():
    print(f"  {k}: {v}")

print("\n✅ 提取完成")
