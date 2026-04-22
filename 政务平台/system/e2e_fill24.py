#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复剩余验证错误: 从业人数+住所cascader+详细地址"""
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
# Step 1: 检查当前验证错误
# ============================================================
print("Step 1: 当前验证错误")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  {errors}")

# ============================================================
# Step 2: 分析regist-info组件（从业人数等字段）
# ============================================================
print("\nStep 2: regist-info组件")
ri = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return{{error:'no_ri'}};
    var form=ri.registForm||ri.$data?.registForm||{{}};
    var keys=Object.keys(form);
    var result={{}};
    for(var i=0;i<keys.length;i++){{
        var k=keys[i];var v=form[k];
        if(v===null||v===undefined)result[k]='null';
        else if(Array.isArray(v))result[k]='A['+v.length+']';
        else result[k]=String(v).substring(0,30);
    }}
    return result;
}})()""")
print(f"  registForm: {ri}")

# ============================================================
# Step 3: 填写regist-info缺失字段
# ============================================================
print("\nStep 3: 填写regist-info")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return;
    var form=ri.registForm||ri.$data?.registForm;
    if(!form)return;
    // 从业人数
    ri.$set(form,'empNum','5');
    // 注册资本
    ri.$set(form,'registerCapital','100');
    ri.$set(form,'shouldInvestWay','1');
    // 联系电话
    ri.$set(form,'entPhone','13800138000');
    // 邮政编码
    ri.$set(form,'postcode','530000');
    ri.$forceUpdate();
}})()""")

# 同步DOM - 从业人数
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('从业人数')){s.call(input,'5');input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# ============================================================
# Step 4: 住所cascader - 通过residence-information
# ============================================================
print("\nStep 4: 住所cascader")

# 分析residence-information
ri_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return{{error:'no_ri'}};
    var form=ri.residenceForm||ri.$data?.residenceForm||{{}};
    var keys=Object.keys(form);
    var result={{}};
    for(var i=0;i<keys.length;i++){{
        var k=keys[i];var v=form[k];
        if(v===null||v===undefined)result[k]='null';
        else if(Array.isArray(v))result[k]='A['+v.length+']';
        else result[k]=String(v).substring(0,30);
    }}
    return result;
}})()""")
print(f"  residenceForm: {ri_info}")

# 设置住所
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return;
    var form=ri.residenceForm||ri.$data?.residenceForm;
    if(!form)return;
    ri.$set(form,'distCode','450103');
    ri.$set(form,'distCodeName','青秀区');
    ri.$set(form,'address','广西壮族自治区/南宁市/青秀区');
    ri.$set(form,'detAddress','民族大道100号');
    ri.$set(form,'isSelectDistCode','1');
    ri.$set(form,'havaAdress','0');
    ri.$set(form,'regionCode','450103');
    ri.$set(form,'regionName','青秀区');
    ri.$set(form,'businessAddress','广西壮族自治区/南宁市/青秀区');
    ri.$set(form,'detBusinessAddress','民族大道100号');
    ri.$forceUpdate();
}})()""")

# 设置cascader DOM组件值
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var cascader=items[i].querySelector('.tne-data-picker');
        if(!cascader)continue;
        var comp=cascader.__vue__;
        if(label.includes('企业住所')&&!label.includes('详细')){
            comp.$emit('input',['450000','450100','450103']);
            comp.$set(comp.$data,'selected',[
                {allName:'广西壮族自治区',id:'450000',isStreet:'N',value:'450000',text:'广西壮族自治区'},
                {allName:'南宁市',id:'450100',parentId:'450000',isStreet:'N',value:'450100',text:'南宁市'},
                {allName:'南宁市青秀区',id:'450103',parentId:'450100',isStreet:'N',value:'450103',text:'青秀区'}
            ]);
            comp.$set(comp.$data,'inputSelected',comp.$data.selected);
        }
        if(label.includes('生产经营地址')&&!label.includes('详细')){
            comp.$emit('input',['450000','450100','450103']);
            comp.$set(comp.$data,'selected',[
                {allName:'广西壮族自治区',id:'450000',isStreet:'N',value:'450000',text:'广西壮族自治区'},
                {allName:'南宁市',id:'450100',parentId:'450000',isStreet:'N',value:'450100',text:'南宁市'},
                {allName:'南宁市青秀区',id:'450103',parentId:'450100',isStreet:'N',value:'450103',text:'青秀区'}
            ]);
            comp.$set(comp.$data,'inputSelected',comp.$data.selected);
        }
    }
})()""")

# 同步详细地址DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('详细地址')&&label.includes('住所')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}))}
        if(label.includes('详细地址')&&label.includes('经营')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# ============================================================
# Step 5: 验证
# ============================================================
print("\nStep 5: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 6: 保存草稿
# ============================================================
print("\nStep 6: 保存草稿")

ev("""(function(){
    window.__save_result=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            }
        });
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
else:
    print("  无API响应")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
