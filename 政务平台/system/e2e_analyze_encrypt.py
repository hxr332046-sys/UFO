#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析encryptData配置和API序列化层，找到busiAreaData被URL编码的根因"""
import json, time, requests, websocket

def ev(js, timeout=15):
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
# Step 1: encryptData配置
# ============================================================
print("Step 1: encryptData配置")
enc_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var ed=fc.$data?.encryptData||fc.encryptData||{{}};
    var keys=Object.keys(ed);
    var result={{}};
    for(var i=0;i<keys.length;i++){{
        var k=keys[i];
        var v=ed[k];
        if(Array.isArray(v))result[k]='A['+v.length+']:'+JSON.stringify(v).substring(0,100);
        else if(typeof v==='object'&&v!==null)result[k]=JSON.stringify(v).substring(0,100);
        else result[k]=v;
    }}
    return result;
}})()""")
print(f"  encryptData: {json.dumps(enc_data, ensure_ascii=False)[:500] if isinstance(enc_data,dict) else enc_data}")

# ============================================================
# Step 2: deepClone方法源码
# ============================================================
print("\nStep 2: deepClone方法")
dc_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var util=vm.$util;
    if(!util)return'no_util';
    var fn=util.deepClone;
    if(!fn)return'no_method';
    return fn.toString().substring(0,1500);
})()""", timeout=15)
print(f"  deepClone: {dc_src[:500] if isinstance(dc_src,str) else dc_src}")

# ============================================================
# Step 3: $api.flow.operationBusinessDataInfo 方法
# ============================================================
print("\nStep 3: API方法")
api_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var api=vm.$api;
    if(!api)return'no_api';
    var flow=api.flow;
    if(!flow)return'no_flow';
    var fn=flow.operationBusinessDataInfo;
    if(!fn)return'no_method';
    return fn.toString().substring(0,1500);
})()""", timeout=15)
print(f"  API方法: {api_src[:500] if isinstance(api_src,str) else api_src}")

# ============================================================
# Step 4: axios请求拦截器/序列化器
# ============================================================
print("\nStep 4: axios配置")
axios_cfg = ev("""(function(){
    var axios=window.axios;
    if(!axios)return'no_axios';
    var defaults=axios.defaults;
    var interceptors=axios.interceptors.request;
    var handlerCount=interceptors.handlers?.length||0;
    // 检查transformRequest
    var tr=defaults.transformRequest;
    var trType=Array.isArray(tr)?'array('+tr.length+')':'other';
    // 检查第一个transformRequest
    var trSrc='';
    if(Array.isArray(tr)&&tr.length>0)trSrc=tr[0].toString().substring(0,300);
    return{
        baseURL:defaults.baseURL||'',
        contentType:defaults.headers?.common?.['Content-Type']||'',
        transformRequestType:trType,
        transformRequestSrc:trSrc,
        requestInterceptorCount:handlerCount
    };
})()""")
print(f"  axios: {json.dumps(axios_cfg, ensure_ascii=False)[:400] if isinstance(axios_cfg,dict) else axios_cfg}")

# ============================================================
# Step 5: 检查flow-save-basic-info回调如何收集businese-info数据
# ============================================================
print("\nStep 5: flow-save回调数据收集")
# 找businese-info的flow-save-basic-info回调
bi_cb = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    var eb=bi.eventBus;
    if(!eb)return'no_eb';
    var handlers=eb._events?.['flow-save-basic-info'];
    if(!handlers||!handlers.length)return'no_handler';
    // 尝试获取handler源码
    var src='';
    for(var i=0;i<handlers.length;i++){{
        var h=handlers[i];
        if(typeof h==='function'){{
            src+=i+':'+h.toString().substring(0,300)+'\\n';
        }}
    }}
    return src||'no_src';
}})()""")
print(f"  handlers: {bi_cb[:500] if isinstance(bi_cb,str) else bi_cb}")

# ============================================================
# Step 6: 直接测试: 手动构造保存请求看服务端返回
# ============================================================
print("\nStep 6: 手动构造保存请求")
# 获取当前完整请求数据，但修正busiAreaData格式
test_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bi=findComp(vm,'businese-info',0);
    
    // 获取businese-info的busiAreaData (原始searchList格式)
    var baData=bi?.busineseForm?.busiAreaData||[];
    var genBusiArea=bi?.busineseForm?.genBusiArea||'';
    var busiAreaCode=bi?.busineseForm?.busiAreaCode||'';
    var busiAreaName=bi?.busineseForm?.busiAreaName||'';
    
    // 获取bdi
    var bdi=JSON.parse(JSON.stringify(fc.$data.businessDataInfo));
    
    // 合并regist-info
    var ri=findComp(vm,'regist-info',0);
    if(ri){{var f=ri.registForm||ri.$data?.registForm;Object.keys(f||{{}}).forEach(function(k){{if(f[k]!==null&&f[k]!==undefined&&f[k]!=='')bdi[k]=f[k]}})}}
    
    // 合并businese-info
    if(bi){{var f=bi.busineseForm||{{}};Object.keys(f).forEach(function(k){{if(f[k]!==null&&f[k]!==undefined&&f[k]!=='')bdi[k]=f[k]}})}}
    
    // 合并residence-information
    var resi=findComp(vm,'residence-information',0);
    if(resi){{var f=resi.residenceForm||resi.$data?.residenceForm;Object.keys(f||{{}}).forEach(function(k){{if(f[k]!==null&&f[k]!==undefined&&f[k]!=='')bdi[k]=f[k]}})}}
    
    // 清理
    delete bdi.currentLocationVo;
    delete bdi.busiComp;
    delete bdi.fieldList;
    delete bdi.jurisdiction;
    delete bdi.linkData;
    delete bdi.processVo;
    delete bdi.signInfo;
    
    // 关键: busiAreaData保持为JSON对象
    // genBusiArea保持为纯文本
    bdi.genBusiArea='软件开发;信息技术咨询服务';
    bdi.busiAreaName='软件开发;信息技术咨询服务';
    
    // 构造linkData
    var linkData={{
        compUrl:'BasicInfo',
        opeType:'tempSave',
        compUrlPaths:['BasicInfo'],
        continueFlag:false,
        busiCompUrlPaths:encodeURIComponent(JSON.stringify(fc.$data.busiCompUrlPaths||[]))
    }};
    
    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    var signInfo=fc.$data.signInfoList?.BasicInfo||'';
    var itemId=fc.$data.busiCompUrlPaths?.[0]?.id||'';
    
    var reqBody=Object.assign({{}}, bdi, {{
        linkData:linkData,
        signInfo:signInfo,
        itemId:itemId
    }});
    
    // 用fetch发送JSON
    return fetch('/icpsp-api/v4/pc/register/establish/component/BasicInfo/operationBusinessDataInfo',{{
        method:'POST',
        headers:{{
            'Content-Type':'application/json',
            'Authorization':auth,
            'top-token':token
        }},
        body:JSON.stringify(reqBody)
    }}).then(function(r){{return r.text()}}).then(function(t){{return t.substring(0,500)}}).catch(function(e){{return'ERROR:'+e.message}});
}})()""", timeout=20)
print(f"  fetch结果: {test_result}")

print("\n✅ 完成")
