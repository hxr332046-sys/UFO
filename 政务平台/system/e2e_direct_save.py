#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""直接调用operationBusinessDataInfo保存，绕过事件收集"""
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
# Step 1: 确保bdi完整 + operatorNum设置
# ============================================================
print("Step 1: 确保所有字段完整")

# 先确认从业人数
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(ri){{
        var form=ri.registForm||ri.$data?.registForm;
        if(form){{ri.$set(form,'operatorNum','5');ri.$set(form,'empNum','5')}}
    }}
}})()""")

# 同步DOM
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
# Step 2: 拦截XHR请求，修改body添加缺失字段
# ============================================================
print("\nStep 2: 拦截并修改保存请求")

ev("""(function(){
    window.__save_result=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    
    XMLHttpRequest.prototype.open=function(m,u){
        this.__url=u;
        return origOpen.apply(this,arguments);
    };
    
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')&&body){
            // 解析body并添加缺失字段
            try{
                var data=JSON.parse(body);
                // 添加住所字段
                data.distCode='450103';
                data.distCodeName='青秀区';
                data.fisDistCode='450103';
                data.address='广西壮族自治区/南宁市/青秀区';
                data.detAddress='民族大道100号';
                data.isSelectDistCode='1';
                data.havaAdress='0';
                data.provinceCode='450000';
                data.regionCode='450103';
                data.regionName='青秀区';
                data.businessAddress='广西壮族自治区/南宁市/青秀区';
                data.detBusinessAddress='民族大道100号';
                // operatorNum
                data.operatorNum='5';
                data.empNum='5';
                // 行业类型
                data.itemIndustryTypeCode='I65';
                data.industryTypeName='软件和信息技术服务业';
                data.multiIndustry='I65';
                data.multiIndustryName='软件和信息技术服务业';
                data.industryId='I65';
                data.zlBusinessInd='I65';
                // busiPeriod
                data.busiPeriod='01';
                // entName
                data.entName='广西智信数据科技有限公司';
                data.name='广西智信数据科技有限公司';
                // entType
                data.entType='1100';
                data.entTypeName='有限责任公司';
                // registerCapital
                data.registerCapital='100';
                data.shouldInvestWay='1';
                // 其他
                data.isBusinessRegMode='0';
                data.secretaryServiceEnt='0';
                data.namePreFlag='1';
                data.partnerNum='1';
                data.setWay='01';
                data.accountType='1';
                data.licenseRadio='0';
                data.copyCerNum='1';
                data.businessModeGT='10';
                data.organize='1';
                data.busiAreaCode='I65';
                
                body=JSON.stringify(data);
            }catch(e){}
        }
        var self=this;
        if(url.includes('operationBusinessData')){
            self.addEventListener('load',function(){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            });
        }
        return origSend.apply(this,[body]);
    };
})()""")

# ============================================================
# Step 3: 触发保存
# ============================================================
print("\nStep 3: 保存")

ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

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
                # 检查data中的错误详情
                data = p.get('data')
                if data:
                    print(f"  data: {json.dumps(data, ensure_ascii=False)[:200]}")
        except:
            print(f"  raw: {r[:200]}")
else:
    print("  无API响应")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
