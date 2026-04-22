#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航回表单 - 处理页面重载"""
import json, time, requests, websocket

def get_page_ws():
    """获取页面WebSocket连接，等待页面就绪"""
    for attempt in range(10):
        try:
            pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "") and "chrome://" not in p.get("url", "")]
            if not page:
                print(f"  等待页面... attempt={attempt+1}")
                time.sleep(2)
                continue
            ws_url = page[0]["webSocketDebuggerUrl"]
            ws = websocket.create_connection(ws_url, timeout=8)
            return ws
        except Exception as e:
            print(f"  连接失败: {e}, attempt={attempt+1}")
            time.sleep(2)
    return None

def ev(js, timeout=10):
    try:
        ws = get_page_ws()
        if not ws:
            return "ERROR:no_page"
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
# Step 1: 检查当前页面
# ============================================================
print("Step 1: 当前页面")
cur = ev("({hash:location.hash,url:location.href.substring(0,80)})")
print(f"  {cur}")

# ============================================================
# Step 2: 导航到core.html表单页
# ============================================================
print("\nStep 2: 导航到core.html")

# 先尝试直接导航（会触发页面重载）
ev("window.location.href='https://zhjg.scjdgjlj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info'")
print("  等待页面加载...")
time.sleep(8)

# 重新连接检查
cur2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  加载后: {cur2}")

if not isinstance(cur2, dict) or cur2.get('formCount', 0) == 0:
    # 可能需要从portal入口进入
    print("  core.html没有表单，尝试portal入口...")
    ev("window.location.href='https://zhjg.scjdgjlj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page?fromProject=name-register&fromPage=%2Fnamenot'")
    time.sleep(8)
    
    cur3 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  portal: {cur3}")
    
    # 找设立登记入口
    if isinstance(cur3, dict) and cur3.get('formCount', 0) == 0:
        links = ev("""(function(){
            var els=document.querySelectorAll('a,button,[class*="item"],[class*="card"],[class*="entry"]');
            var r=[];
            for(var i=0;i<els.length;i++){
                var t=els[i].textContent?.trim()||'';
                if(t.length>2&&t.length<30)r.push({idx:i,text:t,tag:els[i].tagName,href:els[i].href||''});
            }
            return r.slice(0,20);
        })()""")
        print(f"  页面链接: {links}")
        
        # 点击设立登记
        ev("""(function(){
            var els=document.querySelectorAll('a,button,[class*="item"],[class*="card"]');
            for(var i=0;i<els.length;i++){
                var t=els[i].textContent?.trim()||'';
                if(t.includes('设立登记')||t.includes('公司设立')){
                    els[i].click();
                    return t;
                }
            }
        })()""")
        time.sleep(5)
        
        cur4 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  点击后: {cur4}")

# ============================================================
# Step 3: 最终检查
# ============================================================
print("\nStep 3: 最终状态")
final = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,title:document.title})")
print(f"  {final}")

# 检查businessDataInfo
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
    var bdi=comp.$data.businessDataInfo;
    return{found:true,entName:bdi.entName||'',distCode:bdi.distCode||'',itemIndustryTypeCode:bdi.itemIndustryTypeCode||'',businessArea:bdi.businessArea?.substring(0,30)||''};
})()""")
print(f"  businessDataInfo: {bdi}")

print("\n✅ 完成")
