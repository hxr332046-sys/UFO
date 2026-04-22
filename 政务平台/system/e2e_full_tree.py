#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完整组件树 - 找businese-info"""
import json, requests, websocket

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

# 完整树 - 只列出非El/transition组件
comps = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    function walk(vm,d,path){
        if(d>12)return[];
        var name=vm.$options?.name||'';
        var r=[];
        if(name&&!name.startsWith('El')&&name!=='transition'&&name!=='Transition'&&!name.startsWith('form-item')){
            r.push({name:name,path:path,d:d});
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            r=r.concat(walk(vm.$children[i],d+1,path+'/'+i));
        }
        return r;
    }
    return walk(fc,0,'fc');
})()""")
if isinstance(comps, list):
    for c in comps:
        indent = "  " * c['d']
        print(f"{indent}{c['name']} [{c['path']}]")
