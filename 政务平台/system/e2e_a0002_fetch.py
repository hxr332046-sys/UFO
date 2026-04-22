#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002: 直接fetch调API，绕过SPA序列化，测试不同busiAreaData格式"""
import json, time, requests, websocket

def ev(js, timeout=20):
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
# Step 1: 先让SPA正常保存一次，获取flowData（含busiId等）
# ============================================================
print("Step 1: get current bdi from flow-control")
bdi_data = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var bdi=fc.$data?.businessDataInfo;
    if(!bdi)return'no_bdi';
    // 返回完整bdi的JSON
    return JSON.stringify(bdi);
})()""", timeout=15)

if isinstance(bdi_data, str) and bdi_data.startswith('{'):
    bdi = json.loads(bdi_data)
    fd = bdi.get('flowData', {})
    print(f"  busiId={fd.get('busiId')} nameId={fd.get('nameId')} busiType={fd.get('busiType')}")
    with open(r'g:\UFO\政务平台\data\bdi_full.json', 'w', encoding='utf-8') as f:
        json.dump(bdi, f, ensure_ascii=False, indent=2)
    print(f"  bdi saved ({len(bdi)} keys)")
else:
    print(f"  ERROR: {bdi_data}")
    bdi = {}

# ============================================================
# Step 2: 构造正确的请求body，直接fetch调API
# ============================================================
print("\nStep 2: direct fetch API call")

# 先获取保存API的URL
api_url = ev("""(function(){
    // 找operationBusinessDataInfo调用的URL
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    // 查看save方法源码找URL
    var saveFn=fc.$options?.methods?.save;
    if(!saveFn)return'no_save';
    var src=saveFn.toString();
    // 找URL模式
    var idx=src.indexOf('operationBusinessData');
    if(idx>=0)return src.substring(Math.max(0,idx-80),idx+80);
    idx=src.indexOf('BasicInfo');
    if(idx>=0)return src.substring(Math.max(0,idx-80),idx+80);
    return 'no_url_found:src_len='+src.length;
})()""", timeout=15)
print(f"  save URL hint: {api_url}")

# 直接用fetch调API
fetch_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var bdi=fc.$data?.businessDataInfo;
    if(!bdi)return'no_bdi';

    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';

    // 构造请求body - 从bdi提取所有字段
    var body = {
        namePreFlag: bdi.namePreFlag || '1',
        investMoney: bdi.investMoney || '100',
        moneyKindCode: bdi.moneyKindCode || '156',
        registerCapital: bdi.registerCapital || '100',
        moneyKindCodeName: bdi.moneyKindCodeName || '人民币',
        busType: bdi.busType || '1',
        shouldInvestWay: bdi.shouldInvestWay || '1',
        partnerNum: bdi.partnerNum || '0',
        entPhone: bdi.entPhone || '13800138000',
        postcode: bdi.postcode || '530000',
        subCapital: bdi.subCapital || '100',
        entType: bdi.entType || '1100',
        setWay: bdi.setWay || '01',
        accountType: bdi.accountType || '1',
        operatorNum: bdi.operatorNum || '5',
        licenseRadio: bdi.licenseRadio || '0',
        copyCerNum: bdi.copyCerNum || 1,
        name: bdi.name || bdi.entName || '广西智信数据科技有限公司',
        businessModeGT: bdi.businessModeGT || '10',
        organize: bdi.organize || '1',
        empNum: bdi.empNum || '5',
        fisDistCode: bdi.fisDistCode || '450103',
        distCodeName: bdi.distCodeName || '青秀区',
        provinceCode: bdi.provinceCode || '450000',
        provinceName: bdi.provinceName || '广西壮族自治区',
        cityCode: bdi.cityCode || '450100',
        cityName: bdi.cityName || '南宁市',
        businessArea: bdi.businessArea || '',
        secretaryServiceEnt: bdi.secretaryServiceEnt || '0',
        // 关键：busiAreaData直接用数组，不用{firstPlace,param}包装
        busiAreaData: [
            {id:'I3006',stateCo:'1',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'0',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
            {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
        ],
        busiAreaCode: bdi.busiAreaCode || 'I65',
        busiAreaName: bdi.busiAreaName || '软件开发,信息技术咨询服务',
        areaCategory: bdi.areaCategory || 'I',
        genBusiArea: '软件开发;信息技术咨询服务',
        itemIndustryTypeCode: bdi.itemIndustryTypeCode || 'I65',
        industryTypeName: bdi.industryTypeName || '软件和信息技术服务业',
        xfz: bdi.xfz || 'close',
        industryType: bdi.industryType || 'I65',
        industryCode: bdi.industryCode || 'I65',
        entryCode: bdi.entryCode || '',
        entDomicileDto: bdi.entDomicileDto || {},
        flowData: bdi.flowData || {},
        linkData: bdi.linkData || {compUrl:'BasicInfo',opeType:'save',compUrlPaths:['BasicInfo'],busiCompUrlPaths:[],token:''},
        signInfo: bdi.signInfo || '',
        itemId: bdi.itemId || ''
    };

    // 修复flowData
    if(body.flowData.vipChannel==='null')body.flowData.vipChannel=null;

    return fetch('/icpsp-api/v4/pc/register/flow/operationBusinessDataInfo',{
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
        body:JSON.stringify(body)
    }).then(function(r){return r.json()}).then(function(d){
        return {code:d.code,msg:d.msg?.substring(0,80),dataKeys:d.data?Object.keys(d.data).slice(0,10):[]};
    }).catch(function(e){return 'err:'+e.message});
})()""", timeout=20)
print(f"  fetch array: {fetch_result}")

# ============================================================
# Step 3: 如果数组格式不行，试{firstPlace,param}格式
# ============================================================
if isinstance(fetch_result, dict) and str(fetch_result.get('code','')) not in ['0','0000','200']:
    print("\nStep 3: try {firstPlace,param} format")
    fetch_result2 = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        var bdi=fc?.$data?.businessDataInfo||{};
        var token=localStorage.getItem('top-token')||'';
        var auth=localStorage.getItem('Authorization')||'';

        var body = {
            namePreFlag:'1',investMoney:'100',moneyKindCode:'156',registerCapital:'100',
            moneyKindCodeName:'人民币',busType:'1',shouldInvestWay:'1',partnerNum:'0',
            entPhone:bdi.entPhone||'13800138000',postcode:'530000',subCapital:'100',
            entType:'1100',setWay:'01',accountType:'1',operatorNum:'5',licenseRadio:'0',
            copyCerNum:1,name:'广西智信数据科技有限公司',businessModeGT:'10',organize:'1',
            empNum:'5',fisDistCode:'450103',distCodeName:'青秀区',
            provinceCode:'450000',provinceName:'广西壮族自治区',
            cityCode:'450100',cityName:'南宁市',
            businessArea:'一般经营项目：软件开发；信息技术咨询服务（除依法须经批准的项目外，凭营业执照依法自主开展经营活动）',
            secretaryServiceEnt:'0',
            busiAreaData:{firstPlace:'license',param:[
                {id:'I3006',stateCo:'1',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'0',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
            ]},
            busiAreaCode:'I65',busiAreaName:'软件开发,信息技术咨询服务',
            areaCategory:'I',genBusiArea:'软件开发;信息技术咨询服务',
            itemIndustryTypeCode:'I65',industryTypeName:'软件和信息技术服务业',
            xfz:'close',industryType:'I65',industryCode:'I65',entryCode:'',
            entDomicileDto:bdi.entDomicileDto||{},
            flowData:bdi.flowData||{},
            linkData:bdi.linkData||{compUrl:'BasicInfo',opeType:'save',compUrlPaths:['BasicInfo'],busiCompUrlPaths:[],token:''},
            signInfo:bdi.signInfo||'',itemId:bdi.itemId||''
        };
        if(body.flowData.vipChannel==='null')body.flowData.vipChannel=null;

        return fetch('/icpsp-api/v4/pc/register/flow/operationBusinessDataInfo',{
            method:'POST',
            headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
            body:JSON.stringify(body)
        }).then(function(r){return r.json()}).then(function(d){
            return {code:d.code,msg:d.msg?.substring(0,80)};
        }).catch(function(e){return 'err:'+e.message});
    })()""", timeout=20)
    print(f"  fetch object: {fetch_result2}")

    # ============================================================
    # Step 4: 如果仍失败，试不带busiAreaData的请求（最小化排查）
    # ============================================================
    if isinstance(fetch_result2, dict) and str(fetch_result2.get('code','')) not in ['0','0000','200']:
        print("\nStep 4: minimal request - no busiAreaData")
        fetch_result3 = ev("""(function(){
            var vm=document.getElementById('app').__vue__;
            function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var fc=findComp(vm,'flow-control',0);
            var bdi=fc?.$data?.businessDataInfo||{};
            var token=localStorage.getItem('top-token')||'';
            var auth=localStorage.getItem('Authorization')||'';

            // 最小请求：只有flowData+linkData
            var body = {
                flowData: bdi.flowData || {},
                linkData: {compUrl:'BasicInfo',opeType:'save',compUrlPaths:['BasicInfo'],busiCompUrlPaths:[],token:''},
                signInfo: bdi.signInfo || '',
                itemId: bdi.itemId || ''
            };
            if(body.flowData.vipChannel==='null')body.flowData.vipChannel=null;

            return fetch('/icpsp-api/v4/pc/register/flow/operationBusinessDataInfo',{
                method:'POST',
                headers:{'Content-Type':'application/json','Authorization':auth,'top-token':token},
                body:JSON.stringify(body)
            }).then(function(r){return r.json()}).then(function(d){
                return {code:d.code,msg:d.msg?.substring(0,80)};
            }).catch(function(e){return 'err:'+e.message});
        })()""", timeout=20)
        print(f"  minimal: {fetch_result3}")

print("\nDONE")
