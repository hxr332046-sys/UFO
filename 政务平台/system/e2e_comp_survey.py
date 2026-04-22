#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""survey flow-control子组件结构"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "core.html" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
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

FC = "function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"

# ============================================================
# Step 1: basic-info组件完整data
# ============================================================
print("Step 1: basic-info data")
bi_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return'no_bi';
    var d=bi.$data||{{}};
    var result={{}};
    Object.keys(d).forEach(function(k){{
        var v=d[k];
        if(v===null||v===undefined||v===''||v===false)return;
        if(Array.isArray(v))result[k]='A['+v.length+']';
        else if(typeof v==='object')result[k]='O:'+Object.keys(v).length+':'+JSON.stringify(v).substring(0,60);
        else result[k]=v;
    }});
    // 也看$refs
    var refs=Object.keys(bi.$refs||{{}});
    return {{data:result,refs:refs,methods:Object.keys(bi.$options?.methods||{{}}).slice(0,15)}};
}})()""")
print(f"  {json.dumps(bi_data, ensure_ascii=False)[:500] if isinstance(bi_data,dict) else bi_data}")

# ============================================================
# Step 2: businese-info组件完整data
# ============================================================
print("\nStep 2: businese-info data")
busi_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var d=busi.$data||{{}};
    var result={{}};
    Object.keys(d).forEach(function(k){{
        var v=d[k];
        if(v===null||v===undefined||v===''||v===false)return;
        if(Array.isArray(v))result[k]='A['+v.length+']';
        else if(typeof v==='object')result[k]='O:'+Object.keys(v).length+':'+JSON.stringify(v).substring(0,60);
        else result[k]=v;
    }});
    return {{data:result,methods:Object.keys(busi.$options?.methods||{{}}).slice(0,15)}};
}})()""")
print(f"  {json.dumps(busi_data, ensure_ascii=False)[:500] if isinstance(busi_data,dict) else busi_data}")

# ============================================================
# Step 3: 查找所有tree组件
# ============================================================
print("\nStep 3: tree组件")
tree_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    var trees=[];
    function walk(vm,d){{
        if(d>15)return;
        var n=vm.$options?.name||'';
        if(n.includes('Tree')||n.includes('tree')||n==='el-tree'||n==='ElTree'){{
            trees.push({{name:n,d:d,dataLen:(vm.$data?.data||[]).length,storeRoots:(vm.store?.roots||[]).length}});
        }}
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }}
    walk(vm,0);
    return trees;
}})()""")
print(f"  {tree_info}")

# ============================================================
# Step 4: 查找行业类型select组件
# ============================================================
print("\nStep 4: 行业类型select")
select_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    // 查找所有子组件
    var children=[];
    function walk(vm,d){{
        if(d>8)return;
        var n=vm.$options?.name||'';
        if(n&&n!=='ElRow'&&n!=='ElCol')children.push({{name:n,d:d}});
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }}
    walk(busi,0);
    // 也查看DOM中的select/cascader
    var domSelects=document.querySelectorAll('.el-select,.el-cascader,.tne-data-picker');
    var domInfo=[];
    for(var i=0;i<domSelects.length;i++){{
        var vm2=domSelects[i].__vue__;
        domInfo.push({{name:vm2?vm2.$options?.name:'',placeholder:vm2?.placeholder||vm2?.$props?.placeholder||''}});
    }}
    return {{children:children.slice(0,20),domSelects:domInfo}};
}})()""")
print(f"  {json.dumps(select_info, ensure_ascii=False)[:500] if isinstance(select_info,dict) else select_info}")

# ============================================================
# Step 5: 查看businese-info的busineseForm
# ============================================================
print("\nStep 5: busineseForm")
form_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var f=busi.busineseForm||busi.$data?.busineseForm;
    if(!f)return'no_form';
    var result={{}};
    Object.keys(f).forEach(function(k){{
        var v=f[k];
        if(v===null||v===undefined||v===''||v===false)return;
        if(Array.isArray(v))result[k]='A['+v.length+']:'+JSON.stringify(v).substring(0,40);
        else if(typeof v==='object')result[k]=JSON.stringify(v).substring(0,40);
        else result[k]=v;
    }});
    return result;
}})()""")
print(f"  {json.dumps(form_info, ensure_ascii=False)[:500] if isinstance(form_info,dict) else form_info}")

# ============================================================
# Step 6: 查看flow-control的bdi关键字段
# ============================================================
print("\nStep 6: bdi关键字段")
bdi_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var bdi=fc.$data?.businessDataInfo||{{}};
    return {{
        entName:bdi.entName||'',
        industryType:bdi.industryType||'',
        busiAreaData:bdi.busiAreaData||'null',
        genBusiArea:bdi.genBusiArea||'',
        operatorNum:bdi.operatorNum||'',
        distCode:bdi.distCode||'',
        entPhone:bdi.entPhone||''
    }};
}})()""")
print(f"  {json.dumps(bdi_info, ensure_ascii=False)[:300] if isinstance(bdi_info,dict) else bdi_info}")

# ============================================================
# Step 7: 查看DOM上的行业类型和名称输入框
# ============================================================
print("\nStep 7: DOM输入框")
dom_inputs = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        var select=items[i].querySelector('select');
        var cascader=items[i].querySelector('.el-cascader,.el-select,.tne-data-picker');
        var error=items[i].querySelector('.el-form-item__error')?.textContent?.trim()||'';
        if(label){
            result.push({
                label:label.substring(0,20),
                hasInput:!!input,
                hasSelect:!!select,
                hasCascader:!!cascader,
                error:error.substring(0,30)
            });
        }
    }
    return result.slice(0,20);
})()""")
if isinstance(dom_inputs, list):
    for d in dom_inputs:
        if d.get('error'):
            print(f"  ⚠️ {d.get('label','')}: {d.get('error','')}")

print("\n✅ 完成")
