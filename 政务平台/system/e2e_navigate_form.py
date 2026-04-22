#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到设立登记表单"""
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

# ============================================================
# Step 1: 查找页面入口
# ============================================================
print("Step 1: 查找设立登记入口")
links = ev("""(function(){
    var els=document.querySelectorAll('a,button,[class*="item"],[class*="card"],[class*="entry"],[class*="btn"],div[class*="service"]');
    var r=[];
    for(var i=0;i<els.length;i++){
        var t=els[i].textContent?.trim()||'';
        if(t.length>1&&t.length<50)r.push({idx:i,text:t.substring(0,30),tag:els[i].tagName,cls:els[i].className?.substring(0,30)||''});
    }
    return r.slice(0,30);
})()""")
print(f"  页面元素: {links}")

# ============================================================
# Step 2: 尝试直接导航到core.html
# ============================================================
print("\nStep 2: 导航到core.html")
ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info'")
print("  等待加载...")
time.sleep(10)

cur = ev("({hash:location.hash,forms:document.querySelectorAll('.el-form-item').length})")
print(f"  结果: {cur}")

if isinstance(cur, dict) and cur.get('forms', 0) > 5:
    print("  ✅ 表单已加载!")
else:
    # 尝试点击设立登记入口
    print("  core.html没有表单，回到portal找入口...")
    ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page?fromProject=name-register&fromPage=%2Fnamenot'")
    time.sleep(8)
    
    # 点击设立登记相关元素
    click_result = ev("""(function(){
        var els=document.querySelectorAll('a,button,[class*="item"],[class*="card"],div');
        for(var i=0;i<els.length;i++){
            var t=els[i].textContent?.trim()||'';
            if(t.includes('设立登记')||t.includes('公司设立')||t.includes('内资公司设立')){
                els[i].click();
                return{clicked:t.substring(0,30),idx:i};
            }
        }
        // 也找"名称预先核准"后的下一步
        for(var i=0;i<els.length;i++){
            var t=els[i].textContent?.trim()||'';
            if(t.includes('名称')||t.includes('登记')||t.includes('申报')){
                els[i].click();
                return{clicked:t.substring(0,30),idx:i};
            }
        }
        return 'no_match';
    })()""")
    print(f"  点击: {click_result}")
    time.sleep(5)
    
    cur2 = ev("({hash:location.hash,forms:document.querySelectorAll('.el-form-item').length})")
    print(f"  点击后: {cur2}")
    
    if isinstance(cur2, dict) and cur2.get('forms', 0) > 5:
        print("  ✅ 表单已加载!")
    else:
        # 检查是否跳转到了core.html
        url = ev("location.href")
        print(f"  当前URL: {url}")
        
        # 尝试在当前页面找更多入口
        more = ev("""(function(){
            var all=document.querySelectorAll('*');
            var clickable=[];
            for(var i=0;i<all.length;i++){
                var el=all[i];
                var t=el.textContent?.trim()||'';
                var style=getComputedStyle(el);
                if(style.cursor==='pointer'&&t.length>2&&t.length<30&&el.offsetParent!==null){
                    clickable.push({tag:el.tagName,text:t.substring(0,25),cls:el.className?.substring(0,20)||''});
                }
            }
            return clickable.slice(0,20);
        })()""")
        print(f"  可点击元素: {more}")

print("\n✅ 完成")
