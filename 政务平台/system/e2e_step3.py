#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step3: 验证token + 尝试恢复会话 + 记录登录问题"""
import json, time, requests, websocket
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=15)

def ev(js, mid=1):
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")

# 1. 通过API网关验证token
print("=== 1. API验证token有效性 ===")
token = ev("localStorage.getItem('Authorization')") or ""
top_token = ev("localStorage.getItem('top-token')") or ""
print(f"  Authorization: {token[:20]}...")
print(f"  top-token: {top_token[:20]}...")

# 直接调政务平台API验证
api_check = ev("""(function(){
    var xhr=new XMLHttpRequest();
    xhr.open('POST','/icpsp-api/v4/pc/login/checkToken',false);
    xhr.setRequestHeader('Content-Type','application/json');
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||'');
    xhr.setRequestHeader('top-token',localStorage.getItem('top-token')||'');
    try{xhr.send('{}')}catch(e){return{error:e.message}}
    return{status:xhr.status,body:xhr.responseText.substring(0,300)};
})()""")
print(f"  checkToken API: status={api_check.get('status')} body={api_check.get('body','')[:150]}")

# 尝试获取用户信息
user_api = ev("""(function(){
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/user/getUserInfo',false);
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||'');
    xhr.setRequestHeader('top-token',localStorage.getItem('top-token')||'');
    try{xhr.send()}catch(e){return{error:e.message}}
    return{status:xhr.status,body:xhr.responseText.substring(0,300)};
})()""")
print(f"  getUserInfo API: status={user_api.get('status')} body={user_api.get('body','')[:150]}")

# 判断token是否有效
token_valid = api_check.get('status') == 200 or user_api.get('status') == 200
log("6.Token验证", {
    "token": (token or "")[:20] + "...",
    "checkToken_status": api_check.get('status'),
    "getUserInfo_status": user_api.get('status'),
    "token_valid": token_valid,
}, issues=["Token已过期！需要重新登录"] if not token_valid else [])

# 2. 如果token无效，记录需要手动登录
if not token_valid:
    add_auth_finding("Token已过期，政务平台API返回非200。需要用户手动登录（可能需要滑块验证+短信验证）")
    log("6a.登录要求", {
        "action": "需要用户在CDP浏览器中手动登录",
        "reason": "Token过期，API返回非200",
        "login_page": "当前页面就是登录页",
        "methods": ["账号密码+滑块验证", "个人扫码", "法人扫码"],
    })
    add_auth_finding("登录页有3种方式：账号密码（需滑块验证）、个人扫码、法人扫码")
    add_auth_finding("滑块验证是反自动化机制，无法通过CDP直接绕过，需手动完成")

    # 3. 探查登录页结构
    login_structure = ev("""(function(){
        var r={tabs:[],formItems:[],buttons:[],slider:false,qrcode:false};
        var tabs=document.querySelectorAll('.el-tabs__item,[class*="tab"]');
        for(var i=0;i<tabs.length;i++){var t=tabs[i].textContent?.trim();if(t)r.tabs.push(t)}
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){
            var label=fi[i].querySelector('.el-form-item__label');
            var input=fi[i].querySelector('.el-input__inner');
            r.formItems.push({label:label?.textContent?.trim()||'',type:input?'input':'other',ph:input?.placeholder||''});
        }
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){var t=btns[i].textContent?.trim();if(t&&t.length<20)r.buttons.push(t)}
        r.slider=!!document.querySelector('.slider,[class*="slider"],[class*="slide-verify"]');
        r.qrcode=!!document.querySelector('[class*="qr"],[class*="qrcode"],canvas');
        return r;
    })()""")
    log("6b.登录页结构", login_structure)

    # 4. 检查滑块验证机制
    slider_info = ev("""(function(){
        var slider=document.querySelector('.slider,[class*="slider"],[class*="slide-verify"],[class*="drag"]');
        if(!slider)return{hasSlider:false};
        return{
            hasSlider:true,
            tag:slider.tagName,
            cls:slider.className.substring(0,50),
            text:slider.textContent?.trim()?.substring(0,50)||'',
            hasCanvas:!!document.querySelector('canvas'),
            canvasCount:document.querySelectorAll('canvas').length
        };
    })()""")
    log("6c.滑块验证机制", slider_info)
    if slider_info and slider_info.get('hasSlider'):
        add_auth_finding(f"登录页有滑块验证: {slider_info.get('text','')}，canvas数量={slider_info.get('canvasCount',0)}")

    # 5. 检查扫码登录
    qr_info = ev("""(function(){
        var imgs=document.querySelectorAll('img[src*="qr"],img[src*="code"]');
        var canvases=document.querySelectorAll('canvas');
        var qrDivs=document.querySelectorAll('[class*="qr"],[class*="qrcode"],[class*="scan"]');
        var result=[];
        for(var i=0;i<qrDivs.length;i++){
            result.push({cls:qrDivs[i].className.substring(0,30),text:qrDivs[i].textContent?.trim()?.substring(0,30)||'',visible:qrDivs[i].offsetParent!==null});
        }
        return{qrImages:imgs.length,canvasCount:canvases.length,qrDivs:result};
    })()""")
    log("6d.扫码登录机制", qr_info)

    print("\n" + "="*60)
    print("  ⚠️ 需要手动操作：请在CDP浏览器中完成登录")
    print("  登录后，运行 e2e_step4.py 继续测试")
    print("="*60)
else:
    # token有效，尝试恢复Vuex状态
    print("=== Token有效，尝试恢复Vuex ===")
    restore = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app&&app.__vue__;
        var store=vm&&vm.$store;
        if(!store)return{error:'no_store'};
        // 设置 common.token
        if(store.state.common){
            store.state.common.token=localStorage.getItem('Authorization');
        }
        // 设置 user.token
        try{store.commit('user/SET_TOKEN',localStorage.getItem('Authorization'))}catch(e){}
        try{store.commit('SET_TOKEN',localStorage.getItem('Authorization'))}catch(e){}
        // 刷新页面
        location.reload();
        return{restored:true};
    })()""")
    print(f"  restore: {restore}")

ws.close()
