#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002修复：先调guide API创建busiId，再在flow-control保存"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type") == "page" and "core.html" in p.get("url", "")]
        if not page:
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")]
        if not page:
            return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
        ws.settimeout(timeout + 2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result", {}).get("result", {}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 查看flow-control的params和flowData
# ============================================================
print("Step 1: flow-control params")
params = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var p=fc.$data?.params||{};
    var fd=fc.$data?.businessDataInfo?.flowData||{};
    return {
        paramsKeys:Object.keys(p),
        flowData:fd,
        busiId:fd.busiId||'null',
        nameId:fd.nameId||'null',
        busiType:fd.busiType||'null',
        ywlbSign:fd.ywlbSign||'null',
        entType:fd.entType||'null'
    };
})()""")
print(f"  {json.dumps(params, ensure_ascii=False)[:300] if isinstance(params,dict) else params}")

# ============================================================
# Step 2: 查看flowSave中jump前的API调用
# ============================================================
print("\nStep 2: flowSave API calls")
# 重新读取flowSave源码找API调用
src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    // 找portal页面的guide组件
    var pages=document.querySelectorAll('iframe');
    // 直接看flowSave源码中的API调用
    // 从保存的文件读取
    return 'need_to_check_file';
})()""")

# 读取之前保存的flowSave源码
try:
    with open(r'g:\UFO\政务平台\data\flowSave_src.js', 'r', encoding='utf-8') as f:
        flowsave_src = f.read()
    # 找API调用
    api_idx = flowsave_src.find('saveGuideData')
    if api_idx < 0:
        api_idx = flowsave_src.find('operationBusiness')
    if api_idx < 0:
        api_idx = flowsave_src.find('fetch')
    if api_idx < 0:
        api_idx = flowsave_src.find('axios')
    if api_idx < 0:
        api_idx = flowsave_src.find('request')
    if api_idx >= 0:
        print(f"  API at pos {api_idx}:")
        print(f"  {flowsave_src[max(0,api_idx-100):api_idx+200]}")
    else:
        # 找jump前的所有case
        jump_idx = flowsave_src.find('jump')
        if jump_idx >= 0:
            print(f"  jump at pos {jump_idx}:")
            print(f"  {flowsave_src[max(0,jump_idx-300):jump_idx+100]}")
        else:
            print(f"  no jump found, src len={len(flowsave_src)}")
except:
    print("  no flowSave_src.js")

# ============================================================
# Step 3: 直接调guide save API创建busiId
# ============================================================
print("\nStep 3: guide save API")
save_api = ev("""(function(){
    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    
    var guideData={
        entType:'1100',
        nameCode:'0',
        havaAdress:'0',
        distCode:'450103',
        streetCode:'',
        streetName:'',
        detAddress:'民族大道100号',
        address:'广西壮族自治区/南宁市/青秀区',
        distList:['450000','450100','450103'],
        parentEntRegno:'',
        parentEntName:'',
        entTypeCode:'1100',
        busiType:'02_4',
        registerCapital:'100',
        moneyKindCode:'156',
        fzSign:'N'
    };
    
    return fetch('/icpsp-api/v4/pc/register/guide/saveGuideData',{
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
        body:JSON.stringify({
            busiType:'02_4',
            entType:'1100',
            extra:JSON.stringify({extraDto:guideData}),
            guideData:guideData,
            ywlbSign:'4'
        })
    }).then(function(r){return r.json()}).then(function(d){
        return {code:d.code,msg:d.msg?.substring(0,60),busiId:d.data?.busiId||d.data?.flowData?.busiId||'no_id',dataKeys:d.data?Object.keys(d.data).slice(0,10):[]};
    }).catch(function(e){return 'err:'+e.message});
})()""", timeout=20)
print(f"  saveGuideData: {save_api}")

# ============================================================
# Step 4: 如果获得了busiId，设置到flowData中
# ============================================================
if isinstance(save_api, dict) and save_api.get('busiId') and save_api.get('busiId') != 'no_id':
    busi_id = save_api.get('busiId')
    print(f"\nStep 4: set busiId={busi_id}")
    set_result = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){{if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
        var fc=findComp(vm,'flow-control',0);
        if(!fc)return'no_fc';
        var bdi=fc.$data?.businessDataInfo;
        if(!bdi)return'no_bdi';
        var fd=bdi.flowData||{{}};
        fc.$set(fd,'busiId','{busi_id}');
        return {{set:true,busiId:fd.busiId}};
    }})()""")
    print(f"  {set_result}")
else:
    print(f"\n  no busiId from API, trying alternative...")
    # 尝试其他API
    alt_api = ev("""(function(){
        var token=localStorage.getItem('top-token')||'';
        var auth=localStorage.getItem('Authorization')||'';
        // 尝试创建业务
        return fetch('/icpsp-api/v4/pc/register/flow/createFlow',{
            method:'POST',
            headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
            body:JSON.stringify({busiType:'02_4',entType:'1100',ywlbSign:'4'})
        }).then(function(r){return r.json()}).then(function(d){
            return {code:d.code,msg:d.msg?.substring(0,60),data:d.data?JSON.stringify(d.data).substring(0,200):'null'};
        }).catch(function(e){return 'err:'+e.message});
    })()""", timeout=15)
    print(f"  createFlow: {alt_api}")

# ============================================================
# Step 5: 安装修复拦截器+保存
# ============================================================
print("\nStep 5: fix interceptor + save")
ev("""(function(){
    window.__cfix_resp = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u) {this.__url = u;return origOpen.apply(this, arguments)};
    XMLHttpRequest.prototype.send = function(body) {
        var url = this.__url || '';
        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
            try {
                var bobj = JSON.parse(body);
                // 修复URL编码字段
                function fixV(v) {
                    if (typeof v !== 'string') return v;
                    if (v.indexOf('%') === 0) { try { v = decodeURIComponent(v) } catch(e) {} }
                    try { var p = JSON.parse(v); if (typeof p === 'object') return p; if (typeof p === 'string') return p; return p } catch(e) { if (v.charAt(0)==='"'&&v.charAt(v.length-1)==='"') return v.substring(1,v.length-1); return v }
                }
                Object.keys(bobj).forEach(function(k) { if (typeof bobj[k]==='string') bobj[k]=fixV(bobj[k]) });
                if (bobj.linkData) Object.keys(bobj.linkData).forEach(function(k) { if (typeof bobj.linkData[k]==='string') bobj.linkData[k]=fixV(bobj.linkData[k]) });
                // busiAreaData: 保留{firstPlace,param}，改firstPlace为license
                if (bobj.busiAreaData && typeof bobj.busiAreaData === 'object' && !Array.isArray(bobj.busiAreaData) && bobj.busiAreaData.firstPlace === 'general') {
                    bobj.busiAreaData.firstPlace = 'license';
                }
                if (bobj.flowData && bobj.flowData.vipChannel === 'null') bobj.flowData.vipChannel = null;
                body = JSON.stringify(bobj);
            } catch(e) {}
            var self = this;
            self.addEventListener('load', function() { window.__cfix_resp = {status: self.status, text: self.responseText || ''} });
            return origSend.apply(this, [body]);
        }
        return origSend.apply(this, arguments);
    };
})()""")

click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('保存并下一步')||t.includes('下一步'))&&!all[i].disabled&&all[i].offsetParent!==null){
            all[i].click();return{clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  click: {click}")
time.sleep(12)

resp = ev("window.__cfix_resp")
if isinstance(resp, dict):
    text = resp.get('text', '')
    print(f"  status: {resp.get('status')}")
    if text:
        try:
            p = json.loads(text)
            print(f"  code={p.get('code','')} msg={str(p.get('msg',''))[:80]}")
            if str(p.get('code','')) in ['0','0000','200']:
                print("  >>> SUCCESS <<<")
            else:
                print("  >>> STILL ERROR <<<")
        except:
            print(f"  raw: {text[:200]}")

print("\nDONE")
