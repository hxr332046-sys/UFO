#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""追踪save事件流: 子组件如何响应flow-save事件返回数据"""
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
# Step 1: 分析regist-info如何响应flow-save事件
# ============================================================
print("Step 1: regist-info的flow-save监听")
ri_save = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return'no_ri';
    // 查找created/mounted中的$on调用
    var created=ri.$options?.created?.toString()||'';
    var mounted=ri.$options?.mounted?.toString()||'';
    // 查找所有事件监听
    var events=ri._events||{{}};
    var eventKeys=Object.keys(events);
    // 找flow-save相关
    var saveEvents=eventKeys.filter(function(k){{return k.includes('save')}});
    return{{
        created:created.substring(0,300),
        mounted:mounted.substring(0,300),
        allEvents:eventKeys.slice(0,30),
        saveEvents:saveEvents
    }};
}})()""")
print(f"  regist-info: {json.dumps(ri_save, ensure_ascii=False)[:400] if isinstance(ri_save,dict) else ri_save}")

# ============================================================
# Step 2: 分析businese-info的flow-save监听
# ============================================================
print("\nStep 2: businese-info的flow-save监听")
bi_save = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    var events=bi._events||{{}};
    var eventKeys=Object.keys(events);
    var saveEvents=eventKeys.filter(function(k){{return k.includes('save')}});
    var created=bi.$options?.created?.toString()?.substring(0,400)||'';
    return{{saveEvents:saveEvents,allEvents:eventKeys.slice(0,20),created:created}};
}})()""")
print(f"  businese-info: {json.dumps(bi_save, ensure_ascii=False)[:400] if isinstance(bi_save,dict) else bi_save}")

# ============================================================
# Step 3: 分析residence-information的flow-save监听
# ============================================================
print("\nStep 3: residence-information的flow-save监听")
resi_save = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return'no_ri';
    var events=ri._events||{{}};
    var eventKeys=Object.keys(events);
    var saveEvents=eventKeys.filter(function(k){{return k.includes('save')}});
    return{{saveEvents:saveEvents,allEvents:eventKeys.slice(0,20)}};
}})()""")
print(f"  residence-info: {json.dumps(resi_save, ensure_ascii=False)[:300] if isinstance(resi_save,dict) else resi_save}")

# ============================================================
# Step 4: 分析basic-info的flow-save监听
# ============================================================
print("\nStep 4: basic-info的flow-save监听")
bi_events = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return'no_bi';
    var events=bi._events||{{}};
    var eventKeys=Object.keys(events);
    var saveEvents=eventKeys.filter(function(k){{return k.includes('save')}});
    // 查看eventBus上的监听
    var ebEvents=bi.eventBus?Object.keys(bi.eventBus._events||{{}}):[];
    var ebSave=ebEvents.filter(function(k){{return k.includes('save')}});
    return{{saveEvents:saveEvents,ebSaveEvents:ebSave,ebAllEvents:ebEvents.slice(0,20)}};
}})()""")
print(f"  basic-info: {json.dumps(bi_events, ensure_ascii=False)[:300] if isinstance(bi_events,dict) else bi_events}")

# ============================================================
# Step 5: 拦截eventBus事件，追踪save数据收集
# ============================================================
print("\nStep 5: 追踪save数据收集")
ev("""(function(){
    window.__save_data_flow=[];
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var eb=fc.eventBus;
    
    // 拦截eventBus.$emit
    var origEmit=eb.$emit.bind(eb);
    eb.$emit=function(name){
        if(name.includes('flow-save')){
            window.__save_data_flow.push({type:'emit',event:name,argsLen:arguments.length});
        }
        return origEmit.apply(eb,arguments);
    };
    
    // 拦截eventBus.$on 来追踪子组件注册的回调
    var origOn=eb.$on.bind(eb);
    eb.$on=function(name,handler){
        if(name.includes('flow-save')){
            // 包装handler来追踪返回值
            var origHandler=handler;
            var wrappedHandler=function(){
                var result=origHandler.apply(this,arguments);
                var dataKeys=[];
                if(result&&typeof result==='object'){
                    if(result.busiData)dataKeys=Object.keys(result.busiData).slice(0,10);
                    else dataKeys=Object.keys(result).slice(0,10);
                }
                window.__save_data_flow.push({type:'handler',event:name,dataKeys:dataKeys,resultType:typeof result});
                return result;
            };
            return origOn.call(eb,name,wrappedHandler);
        }
        return origOn.apply(eb,arguments);
    };
})()""")

# 触发保存
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{}}
}})()""", timeout=15)
time.sleep(3)

flow = ev("window.__save_data_flow")
print(f"  数据流: {json.dumps(flow, ensure_ascii=False)[:500] if isinstance(flow,list) else flow}")

# ============================================================
# Step 6: 直接捕获完整请求body（包括URL编码的busiAreaData）
# ============================================================
print("\nStep 6: 捕获完整请求body")
ev("""(function(){
    window.__full_req=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__full_req={url:url,body:body||'',contentType:this.__contentType||''};
            var self=this;
            self.addEventListener('load',function(){
                window.__full_req.resp=self.responseText?.substring(0,500)||'';
                window.__full_req.status=self.status;
            });
        }
        return origSend.apply(this,arguments);
    };
    var origSetHeader=XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.setRequestHeader=function(k,v){
        if(k.toLowerCase()==='content-type')this.__contentType=v;
        return origSetHeader.apply(this,arguments);
    };
})()""")

ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{}}
}})()""", timeout=15)
time.sleep(5)

req = ev("window.__full_req")
if isinstance(req, dict):
    print(f"  URL: {req.get('url','')[:80]}")
    print(f"  Content-Type: {req.get('contentType','')}")
    body = req.get('body','')
    print(f"  body长度: {len(body)}")
    print(f"  body前300: {body[:300]}")
    resp = req.get('resp','')
    status = req.get('status','')
    print(f"  status={status} resp={resp[:100]}")
    
    # 解析body中的关键字段
    if body.startswith('{'):
        try:
            bobj = json.loads(body)
            print(f"  body keys: {list(bobj.keys())[:20]}")
            for k in ['distCode','businessAddress','operatorNum','busiAreaData','busiAreaCode','itemIndustryTypeCode']:
                v = bobj.get(k, 'MISSING')
                if isinstance(v, str) and len(v) > 60:
                    print(f"    {k}: {v[:60]}...")
                else:
                    print(f"    {k}: {v}")
        except:
            pass

print("\n✅ 完成")
