#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深度调试: busiAreaData为何为None + operatorNum为何不生效"""
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
# Step 1: businese-info组件详细分析
# ============================================================
print("Step 1: businese-info详细分析")
bi_detail = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return{{error:'no_bi'}};
    var form=bi.busineseForm||{{}};
    var dataKeys=Object.keys(bi.$data||{{}});
    var formKeys=Object.keys(form);
    var busiAreaData=form.busiAreaData;
    var result={{}};
    for(var i=0;i<formKeys.length;i++){{
        var k=formKeys[i];var v=form[k];
        if(k==='busiAreaData')result[k]='Array['+(v?v.length:0)+']';
        else if(v===null||v===undefined)result[k]='null';
        else result[k]=String(v).substring(0,30);
    }}
    return{{dataKeys:dataKeys,formFields:result}};
}})()""")
print(f"  busineseForm: {json.dumps(bi_detail, ensure_ascii=False)[:500] if isinstance(bi_detail,dict) else bi_detail}")

# ============================================================
# Step 2: 直接设置busiAreaData（不用confirm）
# ============================================================
print("\nStep 2: 直接设置busiAreaData")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return;
    var form=bi.busineseForm;
    // 直接设置busiAreaData
    bi.$set(form,'busiAreaData',[
        {{id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'}},
        {{id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}}
    ]);
    bi.$set(form,'genBusiArea','软件开发;信息技术咨询服务');
    bi.$set(form,'busiAreaCode','I65');
    bi.$set(form,'busiAreaName','软件开发;信息技术咨询服务');
    bi.$forceUpdate();
    return{{busiAreaDataLen:form.busiAreaData.length,genBusiArea:form.genBusiArea}};
}})()""")

# 验证
ba_check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return{{error:'no_bi'}};
    var form=bi.busineseForm;
    return{{
        busiAreaDataLen:(form.busiAreaData||[]).length,
        sample:(form.busiAreaData||[]).length>0?JSON.stringify(form.busiAreaData[0]).substring(0,150):'empty',
        genBusiArea:form.genBusiArea?.substring(0,30)||'',
        busiAreaCode:form.busiAreaCode||''
    }};
}})()""")
print(f"  设置后: {ba_check}")

# ============================================================
# Step 3: 从业人数 - 检查regist-info验证逻辑
# ============================================================
print("\nStep 3: 从业人数")
# 检查operatorNum字段
op_check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return{{error:'no_ri'}};
    var form=ri.registForm||ri.$data?.registForm;
    return{{
        operatorNum:form?.operatorNum||'',
        empNum:form?.empNum||'',
        rules:ri.$options?.methods?.hasOwnProperty('validate')
    }};
}})()""")
print(f"  从业人数: {op_check}")

# 直接设置operatorNum
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return;
    var form=ri.registForm||ri.$data?.registForm;
    ri.$set(form,'operatorNum','5');
    ri.$forceUpdate();
}})()""")

# 同步DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('从业人数')){
            s.call(input,'5');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 4: 拦截保存请求body（完整）
# ============================================================
print("\nStep 4: 拦截保存请求")
ev("""(function(){
    window.__full_body=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__full_body=body||'';
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# ============================================================
# Step 5: 保存
# ============================================================
print("\nStep 5: 保存")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

# 获取完整请求body
full_body = ev("window.__full_body")
if full_body:
    try:
        body_obj = json.loads(full_body)
        # 检查关键字段
        print(f"  body keys: {list(body_obj.keys())[:20]}")
        ba = body_obj.get('busiAreaData') or body_obj.get('businessArea')
        print(f"  busiAreaData: {json.dumps(ba, ensure_ascii=False)[:200] if ba else 'missing'}")
        op = body_obj.get('operatorNum') or body_obj.get('empNum')
        print(f"  operatorNum/empNum: {op}")
        addr = body_obj.get('businessAddress') or body_obj.get('detBusinessAddress')
        print(f"  businessAddress: {addr}")
        dist = body_obj.get('distCode')
        print(f"  distCode: {dist}")
        ind = body_obj.get('itemIndustryTypeCode')
        print(f"  itemIndustryTypeCode: {ind}")
    except:
        print(f"  raw: {full_body[:200]}")

# API响应
resp = ev("""(function(){
    var r=null;
    // 从最近请求获取
    return window.__save_result||null;
})()""")
print(f"  API响应: {resp}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
