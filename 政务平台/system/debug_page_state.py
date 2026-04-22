#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""快速检查页面状态和所有form-item"""
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

# 1. 页面URL
r0 = ev("({hash:location.hash, url:location.href})")
print(f"页面: {r0}")

# 2. 所有form-item标签
r1 = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var result=[];
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(!lb)continue;
        var text=lb.textContent.trim();
        var input=items[i].querySelector('input');
        var sel=items[i].querySelector('.el-select');
        var radio=items[i].querySelector('.el-radio-group');
        var val='';
        if(input)val=input.value||'';
        if(sel)val='[select]';
        if(radio)val='[radio]';
        result.push(text+': '+val);
    }
    return result;
})()""")
print(f"\n所有字段 ({len(r1 or [])}个):")
for item in (r1 or []):
    print(f"  {item}")

# 3. bdi关键字段
r2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var fc=find(vm,0);
    if(!fc)return 'no_fc';
    var bdi=fc.$data.businessDataInfo;
    return {
        entType:bdi.entType,
        entTypeName:bdi.entTypeName,
        accountType:bdi.accountType,
        setWay:bdi.setWay,
        busiPeriod:bdi.busiPeriod,
        licenseRadio:bdi.licenseRadio,
        copyCerNum:bdi.copyCerNum,
        organize:bdi.organize,
        businessModeGT:bdi.businessModeGT,
        moneyKindCode:bdi.moneyKindCode,
        subCapital:bdi.subCapital,
        namePreFlag:bdi.namePreFlag,
        secretaryServiceEnt:bdi.secretaryServiceEnt
    };
})()""")
print(f"\nbdi字段: {json.dumps(r2, ensure_ascii=False, indent=2)}")

ws.close()
