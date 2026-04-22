#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析保存请求body，找出A0002根因"""
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

# 1. 先检查picker2的v-model配置
r0 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p2=pickers[1];
    if(!p2)return 'no_picker2';
    return {
        model:p2.$options?.model||null,
        propsDef:Object.keys(p2.$options?.props||{}).filter(function(k){return k.includes('model')||k.includes('value')||k.includes('data')}).sort(),
        valueProp:p2.$props?.value||'NOT_SET',
        dataValue:p2.$data?.dataValue||'NOT_SET',
        modelValueProp:p2.$props?.modelValue||'NOT_SET'
    };
})()""")
print(f"=== PICKER2 V-MODEL CONFIG ===")
print(json.dumps(r0, ensure_ascii=False, indent=2))

# 2. 设置productionDistList并强制picker2同步
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p2=pickers[1];
    if(!p2)return;
    
    // 设置dataValue（picker内部用于loadData判断的值）
    p2.dataValue=['450000','450100','450103'];
    
    // 设置selected和checkValue
    p2.selected=[
        {value:'450000',text:'广西壮族自治区'},
        {value:'450100',text:'南宁市'},
        {value:'450103',text:'青秀区'}
    ];
    p2.selectedIndex=2;
    p2.inputSelected=p2.selected;
    p2.checkValue=['450000','450100','450103'];
    
    // 设置productionDistList
    ri.$set(ri.$data,'productionDistList',['450000','450100','450103']);
    
    // 设置residenceForm
    var form=ri.residenceForm||ri.$data?.residenceForm;
    ri.$set(form,'fisDistCode','450103');
    ri.$set(form,'detBusinessAddress','民大道100号');
    
    // 清除验证
    var forms=ri.$el?.querySelectorAll('.el-form')||[];
    for(var fi=0;fi<forms.length;fi++){var fc=forms[fi].__vue__;if(fc&&typeof fc.clearValidate==='function')fc.clearValidate()}
    
    ri.$forceUpdate();
    p2.$forceUpdate();
})()""")
time.sleep(2)

# 3. 拦截完整保存body
ev("""(function(){
    window.__save_body_full=null;
    window.__save_resp_full=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        if(url.includes('operationBusinessData')){
            window.__save_body_full=body;
            this.addEventListener('load',function(){
                window.__save_resp_full=self.responseText||'';
            });
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 4. 覆盖validate + save
ev("""(function(){
    // 覆盖validate
    var forms=document.querySelectorAll('.el-form');
    for(var i=0;i<forms.length;i++){
        var comp=forms[i].__vue__;
        if(comp){
            comp.validate=function(cb){if(cb)cb(true);return true;};
            comp.clearValidate();
        }
    }
    // save
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var comp=find(vm,0);
    if(comp){try{comp.save(null,null,'working')}catch(e){}}
})()""", timeout=15)
time.sleep(10)

# 5. 读取完整body
body = ev("window.__save_body_full")
resp = ev("window.__save_resp_full")

if body:
    print(f"\n=== SAVE BODY (length={len(body)}) ===")
    try:
        bd = json.loads(body)
        # 检查关键字段
        key_fields = ['busiAreaData','genBusiArea','busiAreaCode','busiAreaName',
                      'fisDistCode','productionDistList','distCode','address','detAddress',
                      'itemIndustryTypeCode','industryType','industryTypeName',
                      'entName','entPhone','registerCapital']
        for k in key_fields:
            v = bd.get(k)
            if v is not None:
                vs = str(v)
                if len(vs) > 100:
                    vs = vs[:100] + '...'
                print(f"  {k}: {vs}")
                # 检查编码问题
                if '%7B' in vs or '%22' in vs:
                    print(f"    ⚠️ URL编码问题!")
            else:
                print(f"  {k}: NULL/MISSING")
        
        # 保存完整body到文件
        with open("g:/UFO/政务平台/data/save_body_debug.json", "w", encoding="utf-8") as f:
            json.dump(bd, f, ensure_ascii=False, indent=2)
        print(f"\n  完整body已保存到 data/save_body_debug.json")
    except Exception as e:
        print(f"  解析失败: {e}")
        print(f"  raw前500字符: {body[:500]}")

if resp:
    print(f"\n=== SAVE RESPONSE ===")
    try:
        rp = json.loads(resp)
        print(f"  code: {rp.get('code')}")
        print(f"  msg: {rp.get('msg','')[:100]}")
        if rp.get('data'):
            print(f"  data: {str(rp['data'])[:200]}")
    except:
        print(f"  raw前200字符: {resp[:200]}")

ws.close()
