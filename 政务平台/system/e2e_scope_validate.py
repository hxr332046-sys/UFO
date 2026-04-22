#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析validateBusinessArea + 修复经营范围数据结构"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=8)
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
# Step 1: 分析businese-info组件的validateBusinessArea方法
# ============================================================
print("Step 1: validateBusinessArea方法源码")
vba = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var src=comp.$options?.methods?.validateBusinessArea?.toString()||'';
    // 也获取其他关键方法
    var getFreeSrc=comp.$options?.methods?.getFreeBusinessArea?.toString()||'';
    var methodNames=Object.keys(comp.$options?.methods||{});
    return{
        validateSrc:src.substring(0,800),
        getFreeSrc:getFreeSrc.substring(0,500),
        methods:methodNames,
        dataKeys:Object.keys(comp.$data||{}).slice(0,20)
    };
})()""")
print(f"  validateBusinessArea: {vba.get('validateSrc','') if isinstance(vba,dict) else vba}")
print(f"  methods: {vba.get('methods',[]) if isinstance(vba,dict) else ''}")

# ============================================================
# Step 2: 分析businese-info的$data
# ============================================================
print("\nStep 2: businese-info $data")
bi_data = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var d=comp.$data;
    var result={};
    for(var k in d){
        var v=d[k];
        if(v===null||v===undefined)result[k]='null';
        else if(Array.isArray(v)){
            result[k]='Array['+v.length+']';
            if(v.length>0&&v.length<10){
                var sample=JSON.stringify(v[0]).substring(0,100);
                result[k]+=' sample:'+sample;
            }
        }
        else if(typeof v==='object')result[k]='obj:'+Object.keys(v).slice(0,5).join(',');
        else result[k]=String(v).substring(0,50);
    }
    return result;
})()""")
if isinstance(bi_data, dict):
    for k,v in sorted(bi_data.items()):
        if any(w in k.lower() for w in ['scope','area','busi','indus','main','free','select']):
            print(f"  {k}: {v}")

# ============================================================
# Step 3: 拦截保存请求体
# ============================================================
print("\nStep 3: 拦截保存请求")
ev("""(function(){
    window.__api_bodies=[];
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')||url.includes('loadbusiness')){
            window.__api_bodies.push({url:url,body:body||'',method:this.__method||'POST'});
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
})()""")

# 保存
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    try{comp.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
time.sleep(5)

bodies = ev("window.__api_bodies")
if bodies and isinstance(bodies, list):
    for b in bodies:
        url = b.get('url','')
        body = b.get('body','')
        print(f"  {b.get('method','')} {url[:60]}")
        if body:
            try:
                parsed = json.loads(body)
                with open(r'g:\UFO\政务平台\data\save_request_body.json','w',encoding='utf-8') as f:
                    json.dump(parsed,f,ensure_ascii=False,indent=2)
                # 找经营范围字段
                for k,v in parsed.items():
                    if any(w in k.lower() for w in ['scope','area','busi','indus']):
                        if isinstance(v,str):
                            print(f"    {k}: {v[:60]}")
                        elif isinstance(v,list):
                            print(f"    {k}: Array[{len(v)}]")
                            for i,item in enumerate(v[:2]):
                                print(f"      [{i}]: {json.dumps(item,ensure_ascii=False)[:100]}")
                print("    已保存到 save_request_body.json")
            except:
                print(f"    raw: {body[:200]}")

# ============================================================
# Step 4: 检查save_request_body.json
# ============================================================
print("\nStep 4: 检查保存的请求体")
try:
    with open(r'g:\UFO\政务平台\data\save_request_body.json', encoding='utf-8') as f:
        body = json.load(f)
    # 打印所有顶层key
    print(f"  顶层keys: {list(body.keys())[:20]}")
    # 找flowData
    if 'flowData' in body:
        fd = body['flowData']
        print(f"  flowData keys: {list(fd.keys())[:20]}")
        for k,v in fd.items():
            if any(w in k.lower() for w in ['scope','area','busi','indus','name']):
                if isinstance(v,str):
                    print(f"    flowData.{k}: {v[:60]}")
                elif isinstance(v,list):
                    print(f"    flowData.{k}: Array[{len(v)}]")
                    for i,item in enumerate(v[:2]):
                        print(f"      [{i}]: {json.dumps(item,ensure_ascii=False)[:120]}")
except Exception as e:
    print(f"  读取失败: {e}")

print("\n✅ 完成")
