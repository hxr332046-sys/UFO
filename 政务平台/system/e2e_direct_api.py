#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""直接调用operationBusinessDataInfo + 用完整bdi数据"""
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: 确保bdi数据完整
# ============================================================
print("Step 1: 确保bdi完整")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=fc.$data.businessDataInfo;
    // 补充缺失字段
    fc.$set(bdi,'operatorNum','5');
    fc.$set(bdi,'empNum','5');
    fc.$set(bdi,'busiPeriod','01');
    fc.$set(bdi,'setWay','01');
    fc.$set(bdi,'accountType','1');
    fc.$set(bdi,'licenseRadio','0');
    fc.$set(bdi,'copyCerNum','1');
    fc.$set(bdi,'businessModeGT','10');
    fc.$set(bdi,'organize','1');
    fc.$set(bdi,'provinceCode','450000');
    fc.$forceUpdate();
}})()""")

# ============================================================
# Step 2: 直接调用operationBusinessDataInfo
# ============================================================
print("\nStep 2: 直接调用operationBusinessDataInfo")

# 先获取完整bdi
bdi_json = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=fc.$data.businessDataInfo;
    return JSON.stringify(bdi);
}})()""", timeout=15)

if isinstance(bdi_json, str) and bdi_json.startswith('{'):
    bdi_obj = json.loads(bdi_json)
    print(f"  bdi keys: {len(bdi_obj.keys())}")
    # 检查关键字段
    for k in ['distCode','businessAddress','operatorNum','empNum','busiAreaData','busiAreaCode','itemIndustryTypeCode']:
        v = bdi_obj.get(k)
        if v is None:
            print(f"  ⚠️ {k}: null")
        elif isinstance(v, list):
            print(f"  {k}: Array[{len(v)}]")
        elif isinstance(v, dict):
            print(f"  {k}: obj({len(v.keys())} keys)")
        else:
            print(f"  {k}: {str(v)[:40]}")

# ============================================================
# Step 3: 用fetch直接调API
# ============================================================
print("\nStep 3: 直接fetch调API")

# 获取token
token_info = ev("""(function(){
    var token=localStorage.getItem('top-token')||localStorage.getItem('token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    return{token:token.substring(0,20),auth:auth.substring(0,20)};
})()""")
print(f"  token: {token_info}")

# 通过fetch发送保存请求
save_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=JSON.parse(JSON.stringify(fc.$data.businessDataInfo));
    
    // 删除不需要的字段
    delete bdi.currentLocationVo;
    delete bdi.busiComp;
    delete bdi.fieldList;
    delete bdi.flowData;
    delete bdi.jurisdiction;
    delete bdi.linkData;
    delete bdi.processVo;
    delete bdi.signInfo;
    
    // 确保关键字段
    bdi.operatorNum='5';
    bdi.empNum='5';
    bdi.distCode='450103';
    bdi.businessAddress='广西壮族自治区/南宁市/青秀区';
    bdi.detBusinessAddress='民族大道100号';
    bdi.itemIndustryTypeCode='I65';
    bdi.busiAreaCode='I65';
    
    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    
    var url='/icpsp-api/v4/pc/register/establish/component/BasicInfo/operationBusinessData';
    
    return fetch(url,{{
        method:'POST',
        headers:{{
            'Content-Type':'application/json',
            'Authorization':auth,
            'top-token':token
        }},
        body:JSON.stringify({{
            operationType:'tempSave',
            componentUrl:'BasicInfo',
            busiData:bdi
        }})
    }}).then(function(r){{return r.text()}}).then(function(t){{return t.substring(0,500)}}).catch(function(e){{return'ERROR:'+e.message}});
}})()""", timeout=20)
print(f"  保存结果: {save_result}")

# ============================================================
# Step 4: 如果fetch失败，尝试用operationBusinessDataInfo
# ============================================================
if not isinstance(save_result, str) or 'A0002' in str(save_result) or 'ERROR' in str(save_result):
    print("\nStep 4: 用operationBusinessDataInfo方法")
    
    # 先确保regist-info和residence-information的form数据正确
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var ri=findComp(vm,'regist-info',0);
        if(ri){{
            var form=ri.registForm||ri.$data?.registForm;
            if(form){{
                ri.$set(form,'operatorNum','5');
                ri.$set(form,'empNum','5');
                ri.$set(form,'distCode','450103');
                ri.$set(form,'businessAddress','广西壮族自治区/南宁市/青秀区');
                ri.$set(form,'detBusinessAddress','民族大道100号');
                ri.$set(form,'regionCode','450103');
                ri.$set(form,'regionName','青秀区');
                ri.$set(form,'detAddress','民族大道100号');
                ri.$set(form,'address','广西壮族自治区/南宁市/青秀区');
            }}
        }}
        var resi=findComp(vm,'residence-information',0);
        if(resi){{
            var form2=resi.residenceForm||resi.$data?.residenceForm;
            if(form2){{
                resi.$set(form2,'distCode','450103');
                resi.$set(form2,'businessAddress','广西壮族自治区/南宁市/青秀区');
                resi.$set(form2,'detBusinessAddress','民族大道100号');
                resi.$set(form2,'regionCode','450103');
                resi.$set(form2,'regionName','青秀区');
            }}
        }}
    }})()""")
    
    # 拦截URL-encoded body
    ev("""(function(){
        window.__save_result=null;
        window.__req_body_raw=null;
        var origSend=XMLHttpRequest.prototype.send;
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
        XMLHttpRequest.prototype.send=function(body){
            var url=this.__url||'';
            if(url.includes('operationBusinessData')){
                window.__req_body_raw=body?.substring(0,500)||'';
                // URL decode to check
                try{
                    var decoded=decodeURIComponent(body||'');
                    window.__req_body_decoded=decoded.substring(0,500);
                }catch(e){}
                var self=this;
                self.addEventListener('load',function(){
                    window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
                });
            }
            return origSend.apply(this,arguments);
        };
    })()""")
    
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
    }})()""", timeout=15)
    time.sleep(5)
    
    # 检查请求body
    raw_body = ev("window.__req_body_raw")
    decoded_body = ev("window.__req_body_decoded")
    print(f"  raw body前200: {raw_body[:200] if isinstance(raw_body,str) else raw_body}")
    
    # 检查响应
    resp = ev("window.__save_result")
    if resp:
        print(f"  API status={resp.get('status')}")
        r = resp.get('resp','')
        if r:
            try:
                p = json.loads(r)
                print(f"  code={p.get('code','')} msg={p.get('msg','')[:60]}")
            except:
                print(f"  raw: {r[:100]}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"\n  验证错误: {errors}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
