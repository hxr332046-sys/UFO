#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复: businessAddress/distCode缺失 + busiAreaCode格式 + operatorNum"""
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
# Step 1: 分析save方法如何组装请求数据
# ============================================================
print("Step 1: save方法源码")
save_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var src=fc.$options?.methods?.save?.toString()||'';
    return src.substring(0,600);
}})()""")
print(f"  save: {save_src}")

# ============================================================
# Step 2: 分析operationBusinessDataInfo方法
# ============================================================
print("\nStep 2: operationBusinessDataInfo方法")
op_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var src=fc.$options?.methods?.operationBusinessDataInfo?.toString()||'';
    return src.substring(0,600);
}})()""")
print(f"  opBdi: {op_src}")

# ============================================================
# Step 3: 分析businessDataInfo中residence相关字段
# ============================================================
print("\nStep 3: businessDataInfo住所字段")
bdi_res = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=fc.$data.businessDataInfo;
    var keys=['distCode','distCodeName','address','detAddress','regionCode','regionName',
        'businessAddress','detBusinessAddress','isSelectDistCode','havaAdress',
        'fisDistCode','provinceCode','streetCode','streetName',
        'regionStreetCode','regionStreetName'];
    var result={{}};
    for(var i=0;i<keys.length;i++){{
        var k=keys[i];
        result[k]=bdi[k]===null||bdi[k]===undefined?'null':String(bdi[k]).substring(0,40);
    }}
    return result;
}})()""")
print(f"  bdi住所: {bdi_res}")

# ============================================================
# Step 4: 设置bdi中的住所字段
# ============================================================
print("\nStep 4: 设置bdi住所字段")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=fc.$data.businessDataInfo;
    fc.$set(bdi,'distCode','450103');
    fc.$set(bdi,'distCodeName','青秀区');
    fc.$set(bdi,'fisDistCode','450103');
    fc.$set(bdi,'address','广西壮族自治区/南宁市/青秀区');
    fc.$set(bdi,'detAddress','民族大道100号');
    fc.$set(bdi,'isSelectDistCode','1');
    fc.$set(bdi,'havaAdress','0');
    fc.$set(bdi,'regionCode','450103');
    fc.$set(bdi,'regionName','青秀区');
    fc.$set(bdi,'businessAddress','广西壮族自治区/南宁市/青秀区');
    fc.$set(bdi,'detBusinessAddress','民族大道100号');
    fc.$set(bdi,'provinceCode','450000');
    fc.$forceUpdate();
}})()""")

# ============================================================
# Step 5: 修复operatorNum - 通过regist-info的form
# ============================================================
print("\nStep 5: operatorNum")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return;
    var form=ri.registForm||ri.$data?.registForm;
    if(!form)return;
    ri.$set(form,'operatorNum','5');
    ri.$set(form,'empNum','5');
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
            // 触发blur
            input.dispatchEvent(new Event('blur',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 6: 修复busiAreaCode格式（可能是"I3006|I3010"而不是"I65"）
# ============================================================
print("\nStep 6: busiAreaCode格式")
# 检查原始格式
ba_code = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return{{error:'no_bi'}};
    var form=bi.busineseForm;
    return{{
        busiAreaCode:form.busiAreaCode||'',
        busiAreaDataLen:(form.busiAreaData||[]).length,
        items:(form.busiAreaData||[]).map(function(it){{return it.id||''}})
    }};
}})()""")
print(f"  busiAreaCode: {ba_code}")

# ============================================================
# Step 7: 拦截保存请求 + 保存
# ============================================================
print("\nStep 7: 保存")

ev("""(function(){
    window.__full_body=null;
    window.__save_result=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__full_body=body||'';
            var self=this;
            self.addEventListener('load',function(){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            });
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

# 解析请求body
full_body = ev("window.__full_body")
if full_body:
    # URL decode
    from urllib.parse import unquote
    decoded = unquote(full_body)
    # 找关键字段
    for field in ['distCode','businessAddress','detBusinessAddress','operatorNum','empNum','busiAreaCode']:
        import re
        m = re.search(field + '=([^&]*)', decoded)
        if m:
            val = m.group(1)[:50]
            print(f"  {field}: {val}")
        else:
            print(f"  {field}: MISSING")

# API响应
resp = ev("window.__save_result")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            code = p.get('code','')
            msg = p.get('msg','')[:60]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000']:
                print("  ✅ 保存成功！")
        except:
            print(f"  raw: {r[:150]}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
