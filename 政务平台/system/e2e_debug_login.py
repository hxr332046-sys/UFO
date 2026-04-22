#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试登录：token存在但页面显示登录页"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=15)

def ev(js, mid=1):
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")

# 刷新到门户
ws.send(json.dumps({"id":200,"method":"Page.navigate","params":{"url":"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page"}}))
time.sleep(8)

# 检查状态
info = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app&&app.__vue__;
    var store=vm&&vm.$store;
    var state=store&&store.state;
    var text=document.body.innerText||'';
    return{
        hash:location.hash,
        hasVue:!!vm,
        hasStore:!!store,
        logged:!!(state&&state.user&&state.user.token),
        isLogin:text.includes('扫码登录')||text.includes('密码登录'),
        sidebar:!!document.querySelector('.sidebar,.el-menu,[class*="sidebar"]'),
        formCount:document.querySelectorAll('.el-form-item').length,
        token:localStorage.getItem('Authorization')||'NONE',
        topToken:localStorage.getItem('top-token')||'NONE',
        lsKeys:Object.keys(localStorage)
    };
})()""")
print(json.dumps(info, ensure_ascii=False, indent=2))

# 同步API验证token
api = ev("""(function(){
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/user/info',false);
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||'');
    xhr.setRequestHeader('top-token',localStorage.getItem('top-token')||'');
    try{xhr.send()}catch(e){return{error:e.message}}
    return{status:xhr.status,body:xhr.responseText.substring(0,200)};
})()""")
print("\nAPI check:", json.dumps(api, ensure_ascii=False))

ws.close()
