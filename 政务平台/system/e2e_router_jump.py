#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""直接调用$router.jump跨项目导航到flow/base"""
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

# ============================================================
# Step 1: 检查$router.jump方法
# ============================================================
print("Step 1: $router.jump")
jump_info = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router||vm.$root?.$router;
    if(!router)return'no_router';
    return {
        hasJump:typeof router.jump==='function',
        jumpSrc:router.jump?router.jump.toString().substring(0,300):'no_method',
        hasPush:typeof router.push==='function',
        routerKeys:Object.keys(router).filter(function(k){return typeof router[k]==='function'}).slice(0,10)
    };
})()""")
print(f"  {json.dumps(jump_info, ensure_ascii=False)[:400] if isinstance(jump_info,dict) else jump_info}")

# ============================================================
# Step 2: 查看flowSave中jump的参数构造
# ============================================================
print("\nStep 2: flowSave jump参数")
# 从源码分析：e.$router.jump({project:"core",path:"/flow/base",target:"_self",params:t})
# t包含：busiType, entType, extra, vipChannel, ywlbSign, busiId, 以及form数据
jump_params = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form;
    var route=comp.$route||comp.$root?.$route;
    var query=route?.query||{};
    
    // 构造flowSave中的参数
    var u=JSON.parse(JSON.stringify(form));
    var l=query.busiType||'02_4';
    var o=query.vipChannel||null;
    var d=query.ywlbSign||'';
    var c=query.busiId||'';
    
    var t={
        busiType:l,
        entType:u.entType||'1100',
        extra:JSON.stringify({extraDto:u}),
        vipChannel:o,
        ywlbSign:d,
        busiId:c,
        guideData:u
    };
    
    return {params:t,formKeys:Object.keys(u).length};
})()""")
print(f"  {json.dumps(jump_params, ensure_ascii=False)[:500] if isinstance(jump_params,dict) else jump_params}")

# ============================================================
# Step 3: 先保存guideData到服务端
# ============================================================
print("\nStep 3: 保存guideData")
save_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form;
    var u=JSON.parse(JSON.stringify(form));
    u.fzSign='N';
    u.entType='1100';
    u.distList=['450000','450100','450103'];
    u.distCode='450103';
    u.nameCode='0';
    u.registerCapital='100';
    u.moneyKindCode='156';
    u.havaAdress='0';
    u.address='广西壮族自治区/南宁市/青秀区';
    u.detAddress='民族大道100号';
    
    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    
    return fetch('/icpsp-api/v4/pc/register/guide/saveGuideData',{
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
        body:JSON.stringify({busiType:'02_4',entType:'1100',extra:JSON.stringify({extraDto:u}),guideData:u})
    }).then(function(r){return r.json()}).then(function(d){
        return {code:d.code,msg:d.msg?.substring(0,60),hasData:!!d.data};
    }).catch(function(e){return 'err:'+e.message});
})()""", timeout=15)
print(f"  saveGuideData: {save_result}")

# ============================================================
# Step 4: 直接调用$router.jump
# ============================================================
print("\nStep 4: $router.jump")
jump_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router||vm.$root?.$router;
    if(!router)return'no_router';
    if(!router.jump)return'no_jump_method';
    
    var comp=null;
    function findGuideComp(vm,d){
        if(d>12)return null;
        if(vm.$data?.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findGuideComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    comp=findGuideComp(vm,0);
    var form=comp?comp.form||comp.$data?.form:{};
    var u=JSON.parse(JSON.stringify(form));
    u.fzSign='N';u.entType='1100';u.distList=['450000','450100','450103'];
    u.distCode='450103';u.nameCode='0';u.registerCapital='100';u.moneyKindCode='156';
    u.havaAdress='0';u.address='广西壮族自治区/南宁市/青秀区';u.detAddress='民族大道100号';
    
    var t={
        busiType:'02_4',
        entType:'1100',
        extra:JSON.stringify({extraDto:u}),
        vipChannel:null,
        ywlbSign:'',
        busiId:'',
        guideData:u
    };
    
    try{
        router.jump({project:'core',path:'/flow/base',target:'_self',params:t});
        return {jumped:true};
    }catch(e){
        return {error:e.message.substring(0,100)};
    }
})()""", timeout=20)
print(f"  jump: {jump_result}")
time.sleep(8)

# ============================================================
# Step 5: 检查结果
# ============================================================
print("\nStep 5: 检查结果")
cur = ev("location.href")
print(f"  URL: {cur[:100] if isinstance(cur,str) else cur}")

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    return {flowControl:!!findComp(vm,'flow-control',0),withoutName:!!findComp(vm,'without-name',0)};
})()""")
print(f"  组件: {comps}")

# 如果jump导致页面跳转到core项目，CDP连接可能断开
# 检查是否还在同一页面
pages = None
try:
    import requests as rq
    pages = rq.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page":
            print(f"  page: {p.get('url','')[:80]}")
except:
    print("  CDP连接断开")

print("\n✅ 完成")
