#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到表单页面 - 刷新后恢复"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# 刷新
print("刷新页面")
ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'")
time.sleep(8)

# 恢复Vuex
print("恢复Vuex")
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")
time.sleep(2)

# 导航到企业开办专区
print("导航到企业开办专区")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)

# 点击开始办理
print("点击开始办理")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(3)

# 导航到select-prise
print("导航到select-prise")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/select-prise')})()""")
time.sleep(2)

# 调用getHandleBusiness
print("调用getHandleBusiness")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,d){if(d>10)return null;if(vm.$options?.name==='select-prise')return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],d+1);if(r)return r}return null}
    var sp=findComp(vm,0);if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness();
})()""")
time.sleep(3)

# 导航到表单
print("导航到表单")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base/basic-info')})()""")
time.sleep(5)

# 验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"结果: hash={fc.get('hash')} forms={fc.get('formCount',0)}")

if fc.get('formCount',0) < 10:
    print("等待...")
    time.sleep(5)
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"结果2: hash={fc.get('hash')} forms={fc.get('formCount',0)}")

log("310.导航", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
ws.close()
print("✅ 导航完成")
