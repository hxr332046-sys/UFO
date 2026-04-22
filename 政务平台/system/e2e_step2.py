#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step2: 等待填表完成 + CDP探查政务平台设立登记页面"""
import sys, os, time, json, requests, websocket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

CDP_PORT = 9225

# 读取 task_id
with open(os.path.join(os.path.dirname(__file__), "..", "data", "e2e_task_id.txt"), "r") as f:
    task_id = f.read().strip()

# 等待填表完成
print("等待自动填表完成...")
for _ in range(30):
    time.sleep(2)
    t = requests.get(f"http://localhost:9090/api/tasks/{task_id}", timeout=10).json()
    if t["status"] not in ("filling", "reviewing", "approved"):
        break

log("3.填表完成状态", {
    "status": t["status"],
    "label": t.get("status_label",""),
    "form_fields_count": len(t.get("form_data",{}).get("fields",{})),
    "fill_result": t.get("form_data",{}).get("fill_result"),
    "navigation": t.get("form_data",{}).get("navigation"),
    "needs_action": t.get("needs_client_action"),
    "action_msg": t.get("client_action_message",""),
})

# === CDP 连接 ===
pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
ws_url = None
for p in pages:
    if p.get("type") == "page":
        ws_url = p["webSocketDebuggerUrl"]
        break

if not ws_url:
    log("4.CDP连接", {"error": "无法获取CDP"}, issues=["CDP浏览器未启动"])
    sys.exit(1)

ws = websocket.create_connection(ws_url, timeout=15)
log("4.CDP连接", {"connected": True})

def cdp_eval(js, mid=1):
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == mid:
            return r.get("result",{}).get("result",{}).get("value")

# 检查登录态
token = cdp_eval("""(function(){return{Auth:localStorage.getItem('Authorization')||'NONE',top:localStorage.getItem('top-token')||'NONE',has:!!localStorage.getItem('Authorization')}})()""")
log("4a.登录态", token, issues=["未登录！需先手动登录政务平台"] if not token or not token.get("has") else [])

# 导航到设立登记
cdp_eval("""(function(){var a=document.getElementById('app');if(a&&a.__vue__){a.__vue__.$router.push('/index/enterprise/establish');return 'ok'}return 'no_vue'})()""")
time.sleep(6)

# 探查页面结构
page_info = cdp_eval("""(function(){
    var r={hash:location.hash,steps:[],tabs:[],formItems:[],buttons:[],iframes:[]};
    var steps=document.querySelectorAll('.el-steps .el-step');
    for(var i=0;i<steps.length;i++){r.steps.push({i:i,title:steps[i].querySelector('.el-step__title')?.textContent?.trim()||'',active:steps[i].className.includes('is-active'),done:steps[i].className.includes('is-finish')})}
    var tabs=document.querySelectorAll('.el-tabs__item');
    for(var i=0;i<tabs.length;i++){r.tabs.push({i:i,label:tabs[i].textContent?.trim()||'',active:tabs[i].className.includes('is-active')})}
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var item=fi[i],label=item.querySelector('.el-form-item__label');
        var input=item.querySelector('.el-input__inner,.el-textarea__inner');
        var sel=item.querySelector('.el-select');
        var radio=item.querySelector('.el-radio-group');
        var upload=item.querySelector('.el-upload');
        var date=item.querySelector('.el-date-editor');
        var tp='unknown';
        if(input)tp=input.tagName==='TEXTAREA'?'textarea':'input';
        if(sel)tp='select';if(radio)tp='radio';if(upload)tp='upload';if(date)tp='date';
        var info={i:i,label:label?.textContent?.trim()||'',type:tp,required:item.className.includes('is-required')};
        if(input)info.ph=input.placeholder||'';
        if(input)info.val=(input.value||'').substring(0,50);
        if(input)info.disabled=input.disabled;
        r.formItems.push(info);
    }
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){var t=btns[i].textContent?.trim();if(t&&t.length<20)r.buttons.push({text:t,disabled:btns[i].disabled})}
    var ifs=document.querySelectorAll('iframe');
    for(var i=0;i<ifs.length;i++){r.iframes.push({src:(ifs[i].src||'').substring(0,80),id:ifs[i].id||'',vis:ifs[i].offsetParent!==null})}
    return r;
})()""")

if page_info:
    log("5.设立登记页面结构", {
        "hash": page_info.get("hash"),
        "steps": page_info.get("steps",[]),
        "tabs": page_info.get("tabs",[]),
        "form_count": len(page_info.get("formItems",[])),
        "button_count": len(page_info.get("buttons",[])),
        "iframe_count": len(page_info.get("iframes",[])),
    })

    # 分类字段
    items = page_info.get("formItems",[])
    fillable = [f for f in items if f.get("type") in ("input","textarea") and not f.get("disabled")]
    selects = [f for f in items if f.get("type") == "select"]
    uploads = [f for f in items if f.get("type") == "upload"]
    required = [f for f in items if f.get("required")]

    log("5a.字段分类", {
        "可填input": len(fillable),
        "select下拉": len(selects),
        "upload上传": len(uploads),
        "必填required": len(required),
    })

    # 详细记录所有字段
    log("5b.全部字段详情", {"fields": items[:40]})

    # 记录按钮
    log("5c.页面按钮", {"buttons": page_info.get("buttons",[])[:20]})

    # iframe检查
    if page_info.get("iframes"):
        log("5d.iframe发现", {"iframes": page_info["iframes"]},
            issues=["发现iframe，可能包含认证/第三方组件"])
        for ifr in page_info["iframes"]:
            if "auth" in (ifr.get("src","") or "").lower() or "face" in (ifr.get("src","") or "").lower():
                add_auth_finding(f"iframe中发现认证组件: {ifr.get('src','')}")

    # 检查名称预核准
    name_check = cdp_eval("""(function(){
        var bt=document.body.innerText||'';
        var r={hasNameCheck:bt.includes('名称预先核准')||bt.includes('名称查重')||bt.includes('名称申报'),nameCheckBtn:''};
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){var t=btns[i].textContent?.trim()||'';if(t.includes('查重')||t.includes('核准')||t.includes('名称检查'))r.nameCheckBtn=t}
        return r;
    })()""")
    log("5e.名称预核准检查", name_check)
    if name_check and name_check.get("hasNameCheck"):
        add_auth_finding("设立登记需要先完成名称预先核准/查重")

# 检查认证相关元素
auth_check = cdp_eval("""(function(){
    var bt=document.body.innerText||'';
    var r={faceAuth:bt.includes('人脸')||bt.includes('面部识别'),smsAuth:bt.includes('短信验证')||bt.includes('验证码'),bankAuth:bt.includes('银行卡')||bt.includes('银行认证'),realName:bt.includes('实名认证')||bt.includes('身份认证')};
    var dialogs=document.querySelectorAll('.el-dialog,.el-message-box');
    for(var i=0;i<dialogs.length;i++){if(dialogs[i].style.display!=='none'&&!dialogs[i].className.includes('hidden')){var t=dialogs[i].textContent||'';if(t.includes('认证')||t.includes('人脸')||t.includes('验证'))r.activeDialog=t.substring(0,100)}}
    return r;
})()""")
log("5f.认证元素检测", auth_check)
if auth_check:
    for k,v in auth_check.items():
        if v and k not in ("activeDialog",):
            add_auth_finding(f"页面检测到{k}: {v}")

ws.close()
print("\n✅ Step2 完成。继续运行 e2e_step3.py 进行表单填写测试")
