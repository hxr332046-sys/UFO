#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化表单数据 + 填写"""
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

# ============================================================
# Step 1: 分析flow-control的initData方法
# ============================================================
print("Step 1: 分析initData方法")
init_src = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var src=fc.$options?.methods?.initData?.toString()||'';
    var initBdiSrc=fc.$options?.methods?.initBusinessDataInfo?.toString()||'';
    var initViewSrc=fc.$options?.methods?.initView?.toString()||'';
    var loadSrc=fc.$options?.methods?.load?.toString()||'';
    return{
        initData:initDataSrc.substring(0,400),
        initBdi:initBdiSrc.substring(0,400),
        initView:initViewSrc.substring(0,300),
        load:loadSrc.substring(0,300)
    };
})()""")
if isinstance(init_src, dict):
    for k,v in init_src.items():
        if v: print(f"  {k}: {v[:200]}")

# ============================================================
# Step 2: 检查params和locationInfo
# ============================================================
print("\nStep 2: params和locationInfo")
params = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var p=fc.$data.params||{};
    var li=fc.$data.locationInfo||{};
    var ii=fc.$data.initFlowControl||{};
    return{
        params:JSON.stringify(p).substring(0,200),
        locationInfo:JSON.stringify(li).substring(0,200),
        initFlowControl:JSON.stringify(ii).substring(0,200)
    };
})()""")
print(f"  {params}")

# ============================================================
# Step 3: 尝试调用initData
# ============================================================
print("\nStep 3: 调用initData")
init_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    try{
        if(typeof fc.initData==='function'){
            fc.initData();
            return{called:'initData'};
        }
    }catch(e){return{error:e.message,method:'initData'}}
    try{
        if(typeof fc.initBusinessDataInfo==='function'){
            fc.initBusinessDataInfo();
            return{called:'initBusinessDataInfo'};
        }
    }catch(e){return{error:e.message,method:'initBusinessDataInfo'}}
    return{error:'no_method'};
})()""", timeout=15)
print(f"  init: {init_result}")
time.sleep(3)

# 检查bdi是否初始化
bdi_after = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var bdi=fc.$data.businessDataInfo;
    if(!bdi)return{error:'no_bdi'};
    var keys=Object.keys(bdi);
    var nonNull=0;
    for(var i=0;i<keys.length;i++){
        if(bdi[keys[i]]!==null&&bdi[keys[i]]!==undefined)nonNull++;
    }
    return{totalKeys:keys.length,nonNull:nonNull,entName:bdi.entName||'',entType:bdi.entType||'',distCode:bdi.distCode||'',itemIndustryTypeCode:bdi.itemIndustryTypeCode||''};
})()""")
print(f"  bdi初始化后: {bdi_after}")

# ============================================================
# Step 4: 如果initData失败，尝试通过入口流程
# ============================================================
if not isinstance(bdi_after, dict) or bdi_after.get('nonNull', 0) < 5:
    print("\nStep 4: 通过入口流程初始化")
    
    # 回到portal入口
    ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page?fromProject=name-register&fromPage=%2Fnamenot'")
    time.sleep(8)
    
    # 点击设立登记
    ev("""(function(){
        var els=document.querySelectorAll('[class*="all-services"] [class*="block"]');
        for(var i=0;i<els.length;i++){
            var t=els[i].textContent?.trim()||'';
            if(t.includes('设立登记')){
                els[i].click();
                return{clicked:t.substring(0,20)};
            }
        }
        return 'no_match';
    })()""")
    time.sleep(5)
    
    # 检查是否跳转到core.html
    cur = ev("({hash:location.hash,forms:document.querySelectorAll('.el-form-item').length})")
    print(f"  点击后: {cur}")
    
    if isinstance(cur, dict) and cur.get('forms', 0) > 5:
        # 检查bdi
        bdi2 = ev("""(function(){
            var app=document.getElementById('app');var vm=app.__vue__;
            function find(vm,d){
                if(d>15)return null;
                if(vm.$data&&vm.$data.businessDataInfo)return vm;
                for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
                return null;
            }
            var comp=find(vm,0);
            if(!comp)return{found:false};
            var b=comp.$data.businessDataInfo;
            return{found:true,nonNull:Object.keys(b).filter(function(k){return b[k]!==null&&b[k]!==undefined}).length,entName:b.entName||'',entType:b.entType||''};
        })()""")
        print(f"  bdi: {bdi2}")

# ============================================================
# Step 5: 最终检查
# ============================================================
print("\nStep 5: 最终状态")
final = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=null;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    fc=find(vm,0);
    if(!fc)return{error:'no_fc',hash:location.hash};
    var bdi=fc.$data.businessDataInfo;
    return{
        hash:location.hash,
        entName:bdi.entName||'',
        entType:bdi.entType||'',
        distCode:bdi.distCode||'',
        itemIndustryTypeCode:bdi.itemIndustryTypeCode||'',
        businessArea:bdi.businessArea?.substring(0,30)||''
    };
})()""")
print(f"  {final}")

print("\n✅ 完成")
