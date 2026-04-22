#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析tne-data-picker弹出面板的DOM结构"""
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

# 刷新页面
print("刷新页面...")
ev("location.reload()")
time.sleep(8)

# 点击住所/区划相关 input 打开 picker（guide/base 常为“公司在哪里”）
print("点击住所/区划 input...")
ev("""(function(){
    function norm(s){return (s||'').replace(/\\s+/g,' ').trim();}
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        var tx=norm(lb&&lb.textContent||'');
        if(!tx) continue;
        if(tx.indexOf('公司在哪里')>=0 || tx.indexOf('住所')>=0 || tx.indexOf('区划')>=0 || tx.indexOf('省')>=0 || tx.indexOf('市')>=0 || tx.indexOf('县')>=0){
            var input=items[i].querySelector('input.el-input__inner,input');
            if(input){ input.click(); return {clicked:true,label:tx}; }
        }
    }
    // fallback: 任意可见 tne-data-picker 输入
    var inp=[...document.querySelectorAll('.tne-data-picker input,.tne-data-picker .el-input__inner')].find(x=>x&&x.offsetParent!==null&&!x.disabled);
    if(inp){ inp.click(); return {clicked:true,label:'fallback_tne_input'}; }
    return {clicked:false};
})()""")
time.sleep(3)

# 抓取picker弹出面板的完整DOM结构
print("\n=== PICKER POPOVER DOM ===")
r = ev("""(function(){
    var poppers=document.querySelectorAll('.tne-data-picker-popover');
    var result=[];
    for(var i=0;i<poppers.length;i++){
        var p=poppers[i];
        if(p.offsetParent===null)continue;
        // 抓取前3层DOM结构
        function walk(el,d){
            if(d>4)return '';
            var tag=el.tagName||'';
            var cls=el.className||'';
            if(typeof cls!=='string')cls='';
            var text=el.childNodes?.length===1&&el.childNodes[0].nodeType===3?el.textContent?.trim():'';
            var s='<'+tag;
            if(cls)s+=' class="'+cls.substring(0,60)+'"';
            s+='>';
            if(text)s+=text.substring(0,30);
            var children=el.children||[];
            if(children.length>0&&d<4){
                for(var j=0;j<Math.min(children.length,8);j++){
                    s+=walk(children[j],d+1);
                }
            }
            s+='</'+tag+'>';
            return s;
        }
        result.push(walk(p,0));
    }
    return result;
})()""", timeout=10)

for i, html in enumerate(r or []):
    print(f"\n--- Popover {i} ---")
    # 简化输出
    print(html[:2000])

# 也尝试直接找picker内部Vue组件的dataList
print("\n\n=== PICKER DATA LIST ===")
r2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    var p0=pickers[0];
    if(!p0)return 'no_picker';
    
    // dataList内容
    var dl=p0.dataList||[];
    var dlSample=[];
    for(var i=0;i<dl.length;i++){
        var level=dl[i]||[];
        var items=[];
        for(var j=0;j<Math.min(level.length,5);j++){
            items.push({name:level[j]?.name||level[j]?.text||'',value:level[j]?.value||level[j]?.uniqueId||'',isLeaf:!!level[j]?.isLeaf});
        }
        dlSample.push({level:i,count:level.length,items:items});
    }
    
    // treeData内容
    var td=p0.treeData||[];
    var tdSample=[];
    for(var i=0;i<Math.min(td.length,5);i++){
        tdSample.push({name:td[i]?.name||'',value:td[i]?.uniqueId||td[i]?.value||'',childrenCount:td[i]?.children?.length||0});
    }
    
    return {
        dataListLevels:dlSample,
        treeDataRootCount:td.length,
        treeDataSample:tdSample,
        isOpened:p0.isOpened,
        selectedIndex:p0.selectedIndex,
        localdata:p0.$props?.localdata?.length||0
    };
})()""")

print(json.dumps(r2, ensure_ascii=False, indent=2))

ws.close()
