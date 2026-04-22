#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""攻克establish页面：企业类型+名称申请+地址选择 → 进入flow-control"""
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
# Step 1: 找到establish组件并分析
# ============================================================
print("Step 1: establish组件分析")
est_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    var methods=Object.keys(est.$options?.methods||{{}});
    var data=est.$data||{{}};
    var dataKeys=Object.keys(data);
    return {{
        methods:methods,
        dataKeys:dataKeys.slice(0,30),
        radioGroup:data.radioGroup,
        nameApply:data.nameApply||data.nameFlag||data.isNameApply||'',
        currentStep:data.currentStep||data.step||data.activeStep||'',
        entTypeList:(data.entTypeList||data.typeList||[]).length,
        address:data.address||data.areaCode||data.distCode||''
    }};
}})()""")
print(f"  {json.dumps(est_info, ensure_ascii=False)[:400] if isinstance(est_info,dict) else est_info}")

# ============================================================
# Step 2: 查看establish完整data
# ============================================================
print("\nStep 2: establish data详情")
est_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    var d=est.$data||{{}};
    // 列出所有非空值
    var result={{}};
    var keys=Object.keys(d);
    for(var i=0;i<keys.length;i++){{
        var v=d[keys[i]];
        if(v===null||v===undefined||v===''||v===false)continue;
        if(Array.isArray(v))result[keys[i]]='A['+v.length+']';
        else if(typeof v==='object')result[keys[i]]=JSON.stringify(v).substring(0,80);
        else result[keys[i]]=v;
    }}
    return result;
}})()""")
print(f"  {json.dumps(est_data, ensure_ascii=False)[:500] if isinstance(est_data,dict) else est_data}")

# ============================================================
# Step 3: 查看关键方法源码
# ============================================================
print("\nStep 3: 关键方法源码")
for method_name in ['nextBtn', 'checkchange', 'handleNext', 'handleSelect', 'selectType', 'toNotName', 'handleNameApply', 'handleAddress']:
    src = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var est=findComp(vm,'establish',0);
        if(!est)return'no_est';
        var fn=est.$options?.methods?.{method_name};
        if(!fn)return'';
        return fn.toString().substring(0,300);
    }})()""")
    if isinstance(src, str) and len(src) > 10:
        print(f"  {method_name}: {src[:200]}")

# ============================================================
# Step 4: 选择企业类型 - 内资有限公司
# ============================================================
print("\nStep 4: 选择企业类型(内资有限公司=1100)")
type_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    // 查看radioGroup和entTypeList
    var rg=est.$data?.radioGroup;
    var tl=est.$data?.entTypeList||[];
    // 找1100类型
    var target=tl.find(function(t){{return t.code==='1100'||t.entType==='1100'||t.value==='1100'}});
    
    // 设置radioGroup
    est.$set(est.$data,'radioGroup','1100');
    // 调用checkchange
    if(typeof est.checkchange==='function'){{
        est.checkchange('1100',true);
    }}
    return {{radioGroup:est.$data?.radioGroup,hasTarget:!!target,targetCode:target?.code||target?.entType||target?.value||''}};
}})()""")
print(f"  {type_result}")
time.sleep(1)

# ============================================================
# Step 5: 名称申请 - 选择"未申请"
# ============================================================
print("\nStep 5: 名称申请(未申请)")
name_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    // 查看名称申请相关字段
    var d=est.$data;
    var nameKeys=Object.keys(d).filter(function(k){{return k.includes('name')||k.includes('Name')}});
    var nameVals={{}};
    for(var i=0;i<nameKeys.length;i++)nameVals[nameKeys[i]]=d[nameKeys[i]];
    
    // 查找"未申请"按钮/选项
    var btns=document.querySelectorAll('button,.el-button,.el-radio,.radio-item,.step-item');
    var nameBtns=[];
    for(var i=0;i<btns.length;i++){{
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('未申请')||t.includes('已办理'))nameBtns.push(t.substring(0,20));
    }}
    return {{nameKeys:nameKeys,nameVals:nameVals,nameBtns:nameBtns}};
}})()""")
print(f"  {json.dumps(name_result, ensure_ascii=False)[:400] if isinstance(name_result,dict) else name_result}")

# 点击"未申请"
ev("""(function(){
    var all=document.querySelectorAll('*');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        var rect=all[i].getBoundingClientRect();
        if(t==='未申请'&&rect.width>0&&rect.height>0){
            all[i].click();
            return {clicked:'未申请'};
        }
    }
    return 'no_btn';
})()""")
time.sleep(1)

# ============================================================
# Step 6: 地址选择 - 广西/南宁/青秀区
# ============================================================
print("\nStep 6: 地址选择")
addr_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    var d=est.$data;
    // 地址相关字段
    var addrKeys=Object.keys(d).filter(function(k){{return k.includes('addr')||k.includes('Addr')||k.includes('dist')||k.includes('area')||k.includes('region')}});
    var addrVals={{}};
    for(var i=0;i<addrKeys.length;i++)addrVals[addrKeys[i]]=d[addrKeys[i]];
    
    // 查找cascader组件
    var cascaders=est.$refs?.cascader||est.$refs?.addressCascader||est.$refs?.areaCascader;
    
    return {{addrKeys:addrKeys,addrVals:addrVals,hasCascader:!!cascaders}};
}})()""")
print(f"  {json.dumps(addr_info, ensure_ascii=False)[:400] if isinstance(addr_info,dict) else addr_info}")

# 设置地址
addr_set = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    var d=est.$data;
    
    // 尝试直接设置地址字段
    var addrFields=['address','areaCode','distCode','regionCode','provinceCode','cityCode'];
    for(var i=0;i<addrFields.length;i++){{
        if(d[addrFields[i]]!==undefined){{
            est.$set(d,addrFields[i],'450103');
        }}
    }}
    // 也设置完整地址
    if(d.address!==undefined)est.$set(d,'address','广西壮族自治区/南宁市/青秀区');
    if(d.areaCode!==undefined)est.$set(d,'areaCode','450103');
    if(d.distCode!==undefined)est.$set(d,'distCode','450103');
    
    // 查找cascader并设置值
    var casComps=[];
    function findCascader(vm,d){{
        if(d>15)return;
        if(vm.$options?.name==='ElCascader'||vm.$options?.name==='tne-data-picker'){{
            casComps.push({{name:vm.$options?.name,value:vm.value||vm.$data?.value}});
        }}
        for(var i=0;i<(vm.$children||[]).length;i++)findCascader(vm.$children[i],d+1);
    }}
    findCascader(est,0);
    
    // 设置cascader值
    for(var i=0;i<casComps.length;i++){{
        var c=casComps[i];
        // 找到cascader组件实例
        var comp=null;
        function findComp2(vm,name,d){{
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){{
                var r=findComp2(vm.$children[i],name,d+1);
                if(r)return r;
            }}
            return null;
        }}
        comp=findComp2(est,c.name,0);
        if(comp){{
            comp.$emit('input',['450000','450100','450103']);
            comp.$emit('change',['450000','450100','450103']);
        }}
    }}
    
    return {{addrSet:true,cascaders:casComps.length}};
}})()""")
print(f"  地址设置: {addr_set}")

# ============================================================
# Step 7: 点击下一步/确定按钮
# ============================================================
print("\nStep 7: 点击下一步")
next_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    if(!est)return'no_est';
    // 查找下一步按钮
    var btns=document.querySelectorAll('button,.el-button');
    var nextBtns=[];
    for(var i=0;i<btns.length;i++){{
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('下一步')||t.includes('确定')||t.includes('提交'))&&btns[i].offsetParent!==null){{
            nextBtns.push(t);
        }}
    }}
    
    // 调用nextBtn方法
    if(typeof est.nextBtn==='function'){{
        est.nextBtn();
        return {{called:'nextBtn',visibleBtns:nextBtns}};
    }}
    return {{noMethod:true,visibleBtns:nextBtns}};
}})()""")
print(f"  {next_result}")
time.sleep(5)

# ============================================================
# Step 8: 检查是否进入flow-control
# ============================================================
print("\nStep 8: 检查组件")
comps = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    var est=findComp(vm,'establish',0);
    var nn=findComp(vm,'namenotice',0);
    return {{flowControl:!!fc,withoutName:!!wn,establish:!!est,namenotice:!!nn,hash:location.hash}};
}})()""")
print(f"  {comps}")

# 如果有namenotice或without-name
if isinstance(comps, dict):
    if comps.get('withoutName'):
        print("  点击toNotName...")
        ev(f"""(function(){{
            var vm=document.getElementById('app').__vue__;
            {FC}
            var wn=findComp(vm,'without-name',0);
            if(wn)wn.toNotName();
        }})()""")
        time.sleep(3)
    elif comps.get('namenotice'):
        print("  namenotice页面，查找下一步...")
        ev(f"""(function(){{
            var vm=document.getElementById('app').__vue__;
            {FC}
            var nn=findComp(vm,'namenotice',0);
            if(nn){{
                var methods=Object.keys(nn.$options?.methods||{{}});
                // 调用next/confirm方法
                if(nn.next)nn.next();
                else if(nn.handleNext)nn.handleNext();
                else if(nn.confirm)nn.confirm();
            }}
        }})()""")
        time.sleep(3)
    
    # 再检查
    comps2 = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        var est=findComp(vm,'establish',0);
        return {{flowControl:!!fc,establish:!!est,hash:location.hash}};
    }})()""")
    print(f"  最终: {comps2}")

print("\n✅ 完成")
