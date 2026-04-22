#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""拦截保存请求body，修正busiAreaData格式+添加缺失字段"""
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
# Step 1: 确保所有子组件form数据正确
# ============================================================
print("Step 1: 设置子组件form数据")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    // regist-info
    var ri=findComp(vm,'regist-info',0);
    if(ri){{
        var form=ri.registForm||ri.$data?.registForm;
        if(form){{
            ri.$set(form,'operatorNum','5');
            ri.$set(form,'empNum','5');
        }}
    }}
    // businese-info - 确保busiAreaData正确
    var bi=findComp(vm,'businese-info',0);
    if(bi){{
        var bform=bi.busineseForm;
        if(bform){{
            bi.$set(bform,'busiAreaData',[
                {{id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'}},
                {{id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}}
            ]);
            bi.$set(bform,'genBusiArea','软件开发;信息技术咨询服务');
            bi.$set(bform,'busiAreaCode','I65');
            bi.$set(bform,'busiAreaName','软件开发;信息技术咨询服务');
        }}
    }}
    // residence-information
    var resi=findComp(vm,'residence-information',0);
    if(resi){{
        var rform=resi.residenceForm||resi.$data?.residenceForm;
        if(rform){{
            resi.$set(rform,'distCode','450103');
            resi.$set(rform,'distCodeName','青秀区');
            resi.$set(rform,'address','广西壮族自治区/南宁市/青秀区');
            resi.$set(rform,'detAddress','民族大道100号');
            resi.$set(rform,'businessAddress','广西壮族自治区/南宁市/青秀区');
            resi.$set(rform,'detBusinessAddress','民族大道100号');
            resi.$set(rform,'regionCode','450103');
            resi.$set(rform,'regionName','青秀区');
        }}
    }}
}})()""")

# 同步从业人数DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('从业人数')){s.call(input,'5');input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}))}
    }
})()""")

# ============================================================
# Step 2: 拦截XHR - 修正body
# ============================================================
print("\nStep 2: 拦截+修正保存请求")
ev("""(function(){
    window.__save_result=null;
    window.__patched_body=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')&&body){
            try{
                var data=JSON.parse(body);
                // 修正busiAreaData - 如果是字符串则解析
                if(typeof data.busiAreaData==='string'){
                    try{data.busiAreaData=JSON.parse(decodeURIComponent(data.busiAreaData))}catch(e){
                        try{data.busiAreaData=JSON.parse(data.busiAreaData)}catch(e2){}
                    }
                }
                // 确保busiAreaData是正确数组
                if(!Array.isArray(data.busiAreaData)){
                    data.busiAreaData={firstPlace:'license',param:[
                        {id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                        {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
                    ]};
                }
                // 添加缺失的住所字段
                if(!data.distCode)data.distCode='450103';
                if(!data.distCodeName)data.distCodeName='青秀区';
                if(!data.fisDistCode)data.fisDistCode='450103';
                if(!data.address)data.address='广西壮族自治区/南宁市/青秀区';
                if(!data.detAddress)data.detAddress='民族大道100号';
                if(!data.businessAddress)data.businessAddress='广西壮族自治区/南宁市/青秀区';
                if(!data.detBusinessAddress)data.detBusinessAddress='民族大道100号';
                if(!data.regionCode)data.regionCode='450103';
                if(!data.regionName)data.regionName='青秀区';
                if(!data.provinceCode)data.provinceCode='450000';
                if(!data.isSelectDistCode)data.isSelectDistCode='1';
                if(!data.havaAdress)data.havaAdress='0';
                // operatorNum
                if(!data.operatorNum)data.operatorNum='5';
                if(!data.empNum)data.empNum='5';
                // 行业类型
                if(!data.itemIndustryTypeCode)data.itemIndustryTypeCode='I65';
                if(!data.industryTypeName)data.industryTypeName='软件和信息技术服务业';
                if(!data.busiAreaCode)data.busiAreaCode='I65';
                
                body=JSON.stringify(data);
                window.__patched_body=body.substring(0,500);
            }catch(e){window.__patch_error=e.message}
            var self=this;
            self.addEventListener('load',function(){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            });
        }
        return origSend.apply(this,[body]);
    };
})()""")

# ============================================================
# Step 3: 保存
# ============================================================
print("\nStep 3: 保存")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

# 检查结果
patched = ev("window.__patched_body")
if patched:
    print(f"  patched body前200: {patched[:200]}")

patch_err = ev("window.__patch_error")
if patch_err:
    print(f"  patch error: {patch_err}")

resp = ev("window.__save_result")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            code = p.get('code','')
            msg = p.get('msg','')[:80]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000']:
                print("  ✅ 保存成功！")
            else:
                # 检查data
                d = p.get('data')
                if d and isinstance(d, dict):
                    print(f"  data: {json.dumps(d, ensure_ascii=False)[:200]}")
                elif d and isinstance(d, str):
                    print(f"  data: {d[:100]}")
        except:
            print(f"  raw: {r[:200]}")
else:
    print("  无API响应")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
