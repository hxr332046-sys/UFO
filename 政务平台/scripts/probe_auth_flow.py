#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探查政务平台的实名认证、人脸认证、材料上传机制"""

import json
import time
import requests
import websocket

CDP_PORT = 9225

def get_ws():
    pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    return None

def cdp_eval(ws, js, msg_id=1, timeout=15):
    ws.send(json.dumps({
        "id": msg_id, "method": "Runtime.evaluate",
        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}
    }))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == msg_id:
            return r.get("result", {}).get("result", {}).get("value")

ws_url = get_ws()
ws = websocket.create_connection(ws_url, timeout=15)

# 1. 用户认证状态
auth_status = cdp_eval(ws, """
(function() {
    var app = document.getElementById('app');
    if (!app || !app.__vue__) return {error: 'No Vue'};
    var userInfo = app.__vue__.$store.state.common.userInfo || {};
    return {
        authflag: userInfo.authflag,
        faceFlag: userInfo.faceFlag,
        telFlag: userInfo.telFlag,
        pwdFlag: userInfo.pwdFlag,
        mailFlag: userInfo.mailFlag,
        usertype: userInfo.usertype,
        isEntUser: userInfo.isEntUser,
        username: userInfo.username,
        elename: userInfo.elename,
        source: userInfo.source
    };
})()
""", msg_id=1)
print("=== 用户认证状态 ===")
print(json.dumps(auth_status, ensure_ascii=False, indent=2))

# 2. 去实名认证页面
ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {
    "url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/realname-authentication"
}}))
_ = json.loads(ws.recv())
time.sleep(4)

realname_info = cdp_eval(ws, """
(function() {
    var iframes = document.querySelectorAll('iframe');
    var iframeInfo = [];
    for (var i = 0; i < iframes.length; i++) {
        iframeInfo.push({id: iframes[i].id, src: iframes[i].src || '', cls: iframes[i].className});
    }
    var buttons = document.querySelectorAll('button, .el-button');
    var btnTexts = [];
    for (var i = 0; i < buttons.length; i++) {
        var t = (buttons[i].textContent || '').trim();
        if (t) btnTexts.push(t);
    }
    var links = document.querySelectorAll('a');
    var linkInfo = [];
    for (var i = 0; i < links.length; i++) {
        var href = links[i].getAttribute('href') || '';
        var text = (links[i].textContent || '').trim();
        if (text && text.length > 1) linkInfo.push({text: text.substring(0,40), href: href.substring(0,100)});
    }
    var bodyText = (document.body.innerText || '').substring(0, 2000);
    return {iframes: iframeInfo, buttons: btnTexts, links: linkInfo.slice(0,20), bodyText: bodyText};
})()
""", msg_id=3)
print("\n=== 实名认证页面 ===")
print(json.dumps(realname_info, ensure_ascii=False, indent=2))

# 3. 去情景导办页面看材料上传
ws.send(json.dumps({"id": 4, "method": "Page.navigate", "params": {
    "url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/establish"
}}))
_ = json.loads(ws.recv())
time.sleep(5)

upload_info = cdp_eval(ws, """
(function() {
    var result = {uploadElements: [], fileInputs: [], iframes: [], bodyText: ''};
    
    // 文件上传元素
    var uploads = document.querySelectorAll('[class*="upload"], [class*="file"], input[type="file"]');
    for (var i = 0; i < uploads.length; i++) {
        var el = uploads[i];
        result.uploadElements.push({
            tag: el.tagName,
            cls: (el.className || '').substring(0, 80),
            id: el.id || '',
            type: el.type || '',
            accept: el.accept || ''
        });
    }
    
    // iframe
    var iframes = document.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        result.iframes.push({id: iframes[i].id, src: (iframes[i].src || '').substring(0, 150)});
    }
    
    result.bodyText = (document.body.innerText || '').substring(0, 3000);
    return result;
})()
""", msg_id=5)
print("\n=== 情景导办/材料上传页面 ===")
print(json.dumps(upload_info, ensure_ascii=False, indent=2))

# 4. 检查 API 端点中是否有文件上传和人脸认证相关接口
# 启用网络监听，点击一些按钮触发请求
ws.send(json.dumps({"id": 6, "method": "Network.enable", "params": {}}))
_ = json.loads(ws.recv())

# 回到首页触发一些API
ws.send(json.dumps({"id": 7, "method": "Page.navigate", "params": {
    "url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page"
}}))
_ = json.loads(ws.recv())
time.sleep(3)

api_urls = set()
ws.settimeout(1)
deadline = time.time() + 5
while time.time() < deadline:
    try:
        msg = json.loads(ws.recv())
        if msg.get("method") == "Network.requestWillBeSent":
            url = msg.get("params", {}).get("request", {}).get("url", "")
            if "icpsp-api" in url:
                api_urls.add(url.split("?")[0])
    except:
        continue

print(f"\n=== 已发现的 API 端点 ({len(api_urls)}) ===")
for u in sorted(api_urls):
    print(f"  {u}")

ws.close()
