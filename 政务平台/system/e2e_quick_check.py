#!/usr/bin/env python
import json, time, requests, websocket

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

# 检查当前页面状态
cur = ev("({hash:location.hash,url:location.href.substring(0,100),forms:document.querySelectorAll('.el-form-item').length})")
print(f"当前: {cur}")

# 检查是否有businessDataInfo
bdi = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return{found:false};
    var b=comp.$data.businessDataInfo;
    return{found:true,entName:b.entName||'',distCode:b.distCode||'',itemIndustryTypeCode:b.itemIndustryTypeCode||'',businessArea:b.businessArea?.substring(0,30)||''};
})()""")
print(f"businessDataInfo: {bdi}")
