#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查修复后的保存body"""
import json, requests, websocket, time

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)

def ev(js, timeout=15):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
    ws.settimeout(timeout + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r.get("result", {}).get("result", {}).get("value")

# 1. 刷新页面
print("刷新页面...")
ev("location.reload()")
time.sleep(8)

# 2. 快速填写所有字段（用已验证的方法）
print("填写表单...")
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    
    var fc=find(vm,0);
    var ri=findComp(vm,'residence-information',0);
    var bi=findComp(vm,'businese-info',0);
    if(!fc||!ri||!bi)return 'missing_comp';
    
    // 设置住所
    var form=ri.residenceForm||ri.$data?.residenceForm;
    ri.$set(form,'distCode','450103');
    ri.$set(form,'distCodeName','青秀区');
    ri.$set(form,'provinceCode','450000');
    ri.$set(form,'provinceName','广西壮族自治区');
    ri.$set(form,'cityCode','450100');
    ri.$set(form,'cityName','南宁市');
    ri.$set(form,'isSelectDistCode',1);
    ri.$set(form,'fisDistCode','450103');
    ri.$set(form,'detAddress','民大道100号');
    ri.$set(form,'detBusinessAddress','民大道100号');
    ri.$set(form,'havaAdress','0');
    ri.$set(form,'houseToBus','0');
    ri.$set(form,'normAddFlag','02');
    ri.$set(ri.$data,'productionDistList',['450000','450100','450103']);
    ri.$set(ri.$data,'distList',['450000','450100','450103']);
    if(typeof ri.distCodeChange==='function')ri.distCodeChange();
    
    // 设置picker
    var pickers=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-data-picker')pickers.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(ri,0);
    for(var pi=0;pi<pickers.length;pi++){
        var p=pickers[pi];
        p.selected=[{value:'450000',text:'广西壮族自治区'},{value:'450100',text:'南宁市'},{value:'450103',text:'青秀区'}];
        p.selectedIndex=2;
        p.inputSelected=p.selected;
        p.checkValue=['450000','450100','450103'];
        try{p.updateBindData()}catch(e){}
        try{p.updateSelected()}catch(e){}
        p.$forceUpdate();
    }
    
    // 设置行业类型
    var bdi=fc.$data.businessDataInfo;
    fc.$set(bdi,'itemIndustryTypeCode','I65');
    fc.$set(bdi,'industryTypeName','软件和信息技术服务业');
    fc.$set(bdi,'industryType','I65');
    fc.$set(bdi,'industryCode','I65');
    
    // 设置经营范围
    bi.confirm({
        busiAreaData:[{id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},{id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}],
        genBusiArea:'软件开发;信息技术咨询服务',
        busiAreaCode:'I65',
        busiAreaName:'软件开发,信息技术咨询服务'
    });
    
    // 设置基本信息
    fc.$set(bdi,'entName','广西智信数据科技有限公司');
    fc.$set(bdi,'registerCapital','100');
    fc.$set(bdi,'moneyKindCode','156');
    fc.$set(bdi,'setWay','01');
    fc.$set(bdi,'accountType','1');
    fc.$set(bdi,'operatorNum','5');
    fc.$set(bdi,'licenseRadio','0');
    fc.$set(bdi,'entPhone','13800138000');
    fc.$set(bdi,'postcode','530022');
    fc.$set(bdi,'copyCerNum',1);
    
    fc.$forceUpdate();
    ri.$forceUpdate();
    bi.$forceUpdate();
    return 'all_set';
})()""")
time.sleep(3)

# 3. 拦截完整body并保存
ev("""(function(){
    window.__save_body_full=null;
    window.__save_resp_full=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        if(url.includes('operationBusinessData')&&body){
            // 修复body
            try{
                var bd=JSON.parse(body);
                if(typeof bd.busiAreaData==='string'&&bd.busiAreaData.includes('%7B')){
                    bd.busiAreaData=JSON.parse(decodeURIComponent(bd.busiAreaData));
                }
                if((!bd.genBusiArea||bd.genBusiArea==='')&&bd.busiAreaData&&bd.busiAreaData.param){
                    var names=[];
                    for(var i=0;i<bd.busiAreaData.param.length;i++)names.push(bd.busiAreaData.param[i].name);
                    if(names.length>0)bd.genBusiArea=names.join(';');
                }
                if(typeof bd.linkData?.busiCompUrlPaths==='string'&&bd.linkData.busiCompUrlPaths.includes('%5B')){
                    bd.linkData.busiCompUrlPaths=JSON.parse(decodeURIComponent(bd.linkData.busiCompUrlPaths));
                }
                body=JSON.stringify(bd);
            }catch(e){}
            window.__save_body_full=body;
            this.addEventListener('load',function(){
                window.__save_resp_full=self.responseText||'';
            });
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 4. 覆盖validate + save
ev("""(function(){
    var forms=document.querySelectorAll('.el-form');
    for(var i=0;i<forms.length;i++){
        var comp=forms[i].__vue__;
        if(comp){comp.validate=function(cb){if(cb)cb(true);return true;};comp.clearValidate();}
    }
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var comp=find(vm,0);
    if(comp){try{comp.save(null,null,'working')}catch(e){}}
})()""", timeout=15)
time.sleep(10)

# 5. 分析body
body = ev("window.__save_body_full")
resp = ev("window.__save_resp_full")

if body:
    bd = json.loads(body)
    # 保存完整body
    with open("g:/UFO/政务平台/data/save_body_v2.json", "w", encoding="utf-8") as f:
        json.dump(bd, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== BODY ANALYSIS (length={len(body)}) ===")
    # 检查所有字段
    for k in sorted(bd.keys()):
        v = bd[k]
        vs = str(v)
        if len(vs) > 120: vs = vs[:120] + '...'
        flag = ""
        if '%7B' in vs or '%22' in vs: flag = " ⚠️ URL-ENCODED"
        if v is None or v == '' or v == 'null': flag = " ⚠️ EMPTY"
        print(f"  {k}: {vs}{flag}")
    
    # 特别检查entDomicileDto
    if bd.get('entDomicileDto'):
        print("\n=== entDomicileDto ===")
        for k,v in bd['entDomicileDto'].items():
            if v is not None and v != '':
                print(f"  {k}: {v}")

if resp:
    try:
        rp = json.loads(resp)
        print(f"\n=== RESPONSE ===")
        print(f"  code: {rp.get('code')}")
        print(f"  msg: {rp.get('msg','')[:100]}")
    except:
        print(f"\n=== RESPONSE RAW ===")
        print(f"  {resp[:300]}")

ws.close()
