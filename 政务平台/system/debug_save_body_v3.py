#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在已填写页面上抓取save body分析A0002"""
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

# 安装XHR拦截器（不修复，抓原始body）
print("安装XHR拦截器...")
ev("""(function(){
    window.__save_body_raw=null;
    window.__save_resp_raw=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        if(url.includes('operationBusinessData')&&body){
            window.__save_body_raw=body;
            this.addEventListener('load',function(){
                window.__save_resp_raw={status:self.status,text:self.responseText||''};
            });
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 覆盖validate + save
print("覆盖validate + save...")
ev("""(function(){
    var forms=document.querySelectorAll('.el-form');
    for(var i=0;i<forms.length;i++){
        var comp=forms[i].__vue__;
        if(comp){comp.validate=function(cb){if(cb)cb(true);return true;};comp.clearValidate();}
    }
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var comp=find(vm,0);
    if(comp){try{comp.save(null,null,'working')}catch(e){}}
})()""", timeout=15)
time.sleep(10)

# 分析body
body = ev("window.__save_body_raw")
resp = ev("window.__save_resp_raw")

if body:
    try:
        bd = json.loads(body)
    except:
        bd = None
    
    if bd:
        # 保存完整body
        with open("g:/UFO/政务平台/data/save_body_v3.json", "w", encoding="utf-8") as f:
            json.dump(bd, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== BODY ANALYSIS ({len(bd.keys())} keys) ===")
        # 检查关键字段
        critical = ['entType','entTypeName','itemIndustryTypeCode','industryTypeName',
                     'busiAreaData','genBusiArea','busiAreaCode','busiAreaName',
                     'registerCapital','entPhone','postcode','operatorNum',
                     'accountType','setWay','busiPeriod','licenseRadio','copyCerNum',
                     'moneyKindCode','organize','businessModeGT','secretaryServiceEnt',
                     'industryId','multiIndustry','multiIndustryName','areaCategory',
                     'busiDateStart','busiDateEnd','businessUuid','entryCode','itemId',
                     'zlBusinessInd']
        for k in critical:
            v = bd.get(k, '<MISSING>')
            flag = ""
            if v is None or v == '' or v == 'null': flag = " ⚠️ EMPTY"
            elif isinstance(v, str) and ('%7B' in v or '%22' in v): flag = " ⚠️ URL-ENCODED"
            print(f"  {k}: {str(v)[:80]}{flag}")
        
        # 检查entDomicileDto
        dto = bd.get('entDomicileDto', {})
        if dto:
            print("\n=== entDomicileDto ===")
            for k,v in dto.items():
                if v is not None and v != '':
                    print(f"  {k}: {v}")
        
        # 检查busiAreaData格式
        bad = bd.get('busiAreaData')
        print(f"\n=== busiAreaData type: {type(bad).__name__} ===")
        if isinstance(bad, str):
            print(f"  RAW: {bad[:200]}")
            if '%7B' in bad:
                print("  ⚠️ URL-ENCODED! 解码后:")
                try:
                    decoded = json.loads(decodeURIComponent(bad))
                    print(f"  firstPlace: {decoded.get('firstPlace')}")
                    print(f"  param count: {len(decoded.get('param',[]))}")
                except: pass
        elif isinstance(bad, dict):
            print(f"  firstPlace: {bad.get('firstPlace')}")
            params = bad.get('param', [])
            print(f"  param count: {len(params)}")
            if params:
                print(f"  param[0]: {json.dumps(params[0], ensure_ascii=False)[:150]}")
        elif isinstance(bad, list):
            print(f"  array len: {len(bad)}")

if resp:
    try:
        rp = json.loads(resp.get('text',''))
        print(f"\n=== RESPONSE ===")
        print(f"  code: {rp.get('code')}")
        print(f"  msg: {rp.get('msg','')[:200]}")
        # 检查是否有更详细的错误信息
        data = rp.get('data')
        if data:
            print(f"  data: {str(data)[:300]}")
    except:
        print(f"\n=== RESPONSE RAW ===")
        print(f"  {resp.get('text','')[:300]}")

ws.close()
