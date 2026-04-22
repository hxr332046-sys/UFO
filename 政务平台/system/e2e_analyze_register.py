#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析registerComponent + 子组件如何响应flow-save事件"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: registerComponent和registerAllComponent源码
# ============================================================
print("Step 1: registerComponent源码")
reg_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return'no_bi';
    var rc=bi.$options?.methods?.registerComponent?.toString()||'';
    var rac=bi.$options?.methods?.registerAllComponent?.toString()||'';
    return{{registerComponent:rc.substring(0,400),registerAllComponent:rac.substring(0,400)}};
}})()""")
print(f"  registerComponent: {reg_src.get('registerComponent','') if isinstance(reg_src,dict) else reg_src}")
print(f"  registerAllComponent: {reg_src.get('registerAllComponent','') if isinstance(reg_src,dict) else ''}")

# ============================================================
# Step 2: regist-info如何注册到basic-info
# ============================================================
print("\nStep 2: regist-info注册方式")
ri_created = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return'no_ri';
    var created=ri.$options?.created?.toString()?.substring(0,500)||'';
    var mounted=ri.$options?.mounted?.toString()?.substring(0,500)||'';
    var inject=ri.$options?.inject||[];
    return{{created:created,mounted:mounted,inject:Array.isArray(inject)?inject:Object.keys(inject||{{}})}};
}})()""")
print(f"  regist-info: created={ri_created.get('created','')[:300] if isinstance(ri_created,dict) else ri_created}")

# ============================================================
# Step 3: 检查basic-info的busiCompUrlPaths和componentMap
# ============================================================
print("\nStep 3: basic-info组件映射")
bi_map = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return'no_bi';
    var data=bi.$data||{{}};
    var keys=Object.keys(data);
    // 找包含comp/component/url/path的key
    var compKeys=keys.filter(function(k){{return k.toLowerCase().includes('comp')||k.toLowerCase().includes('url')||k.toLowerCase().includes('component')}});
    var result={{}};
    for(var i=0;i<compKeys.length;i++){{
        var k=compKeys[i];var v=data[k];
        result[k]=typeof v==='string'?v.substring(0,50):JSON.stringify(v)?.substring(0,100)||'';
    }}
    return result;
}})()""")
print(f"  组件映射: {bi_map}")

# ============================================================
# Step 4: 分析flow-control的busiCompUrlPaths
# ============================================================
print("\nStep 4: flow-control的busiCompUrlPaths")
fc_paths = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var paths=fc.$data?.busiCompUrlPaths||[];
    var curCompUrl=fc.$data?.curCompUrl||'';
    var curCompName=fc.$data?.curCompName||'';
    return{{paths:paths,curCompUrl:curCompUrl,curCompName:curCompName}};
}})()""")
print(f"  paths: {fc_paths}")

# ============================================================
# Step 5: 拦截子组件的flow-save响应
# ============================================================
print("\nStep 5: 拦截flow-save-basic-info响应")
ev("""(function(){
    window.__save_responses=[];
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    // 拦截eventBus.$emit来看子组件如何响应
    var origOn=fc.eventBus.$on;
    fc.eventBus.$on=function(name,handler){
        if(name.includes('flow-save')){
            var origHandler=handler;
            var wrappedHandler=function(){
                var result=origHandler.apply(this,arguments);
                window.__save_responses.push({event:name,result:JSON.stringify(result).substring(0,200)});
                return result;
            };
            return origOn.call(fc.eventBus,name,wrappedHandler);
        }
        return origOn.apply(this,arguments);
    };
})()""")

# ============================================================
# Step 6: 直接查看businessDataInfo的完整内容
# ============================================================
print("\nStep 6: businessDataInfo完整内容")
bdi_full = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=fc.$data.businessDataInfo;
    // 找所有非null字段
    var keys=Object.keys(bdi);
    var nonNull={{}};
    for(var i=0;i<keys.length;i++){{
        var k=keys[i];var v=bdi[k];
        if(v!==null&&v!==undefined&&v!==''){{
            if(Array.isArray(v))nonNull[k]='A['+v.length+']';
            else if(typeof v==='object')nonNull[k]='obj';
            else nonNull[k]=String(v).substring(0,30);
        }}
    }}
    return nonNull;
}})()""")
print(f"  bdi非null字段({len(bdi_full) if isinstance(bdi_full,dict) else '?'}):")
if isinstance(bdi_full, dict):
    for k,v in sorted(bdi_full.items()):
        print(f"    {k}: {v}")

print("\n✅ 完成")
