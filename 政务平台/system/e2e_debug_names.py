#!/usr/bin/env python
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

# 验证fc/3/0/0/0/1的实际组件名
result = ev("""(function(){
    var fc=document.getElementById('app').__vue__.$children[0].$children[0].$children[1].$children[0];
    // 逐层检查
    var c3=fc.$children[3];
    var c30=c3.$children[0];
    var c300=c30.$children[0];
    var c3000=c300.$children;
    var names=[];
    for(var i=0;i<c3000.length;i++){
        names.push({idx:i,name:c3000[i].$options?.name||'(anon)',dataKeys:Object.keys(c3000[i].$data||{}).slice(0,5)});
    }
    return{
        fc3_name:c3.$options?.name||'',
        fc30_name:c30.$options?.name||'',
        fc300_name:c300.$options?.name||'',
        children:names
    };
})()""")
print(f"fc/3/0/0/0 children: {json.dumps(result, ensure_ascii=False)[:500]}")

# 也检查findComp为什么找不到
result2 = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(v,name,d){
        if(d>15)return null;
        var n=v.$options?.name||'';
        if(n===name)return v;
        for(var i=0;i<(v.$children||[]).length;i++){
            var r=findComp(v.$children[i],name,d+1);
            if(r)return r;
        }
        return null;
    }
    var bi=findComp(vm,'businese-info',0);
    if(!bi){
        // 遍历找包含'businese'或'business'的
        function findPartial(v,d){
            if(d>15)return[];
            var n=v.$options?.name||'';
            var r=[];
            if(n.toLowerCase().includes('busines')||n.toLowerCase().includes('range'))r.push({name:n,d:d});
            for(var i=0;i<(v.$children||[]).length;i++){
                r=r.concat(findPartial(v.$children[i],d+1));
            }
            return r;
        }
        return{findComp:null,partial:findPartial(vm,0)};
    }
    return{findComp:'found'};
})()""")
print(f"\nfindComp结果: {json.dumps(result2, ensure_ascii=False)[:300]}")
