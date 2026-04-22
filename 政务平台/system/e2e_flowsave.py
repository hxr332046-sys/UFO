#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调用flowSave进入flow-control"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
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

# ============================================================
# Step 1: flowSave源码
# ============================================================
print("Step 1: flowSave源码")
flowsave_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var fn=comp.$options?.methods?.flowSave;
    if(!fn)return'no_method';
    return fn.toString().substring(0,1500);
})()""", timeout=15)
print(f"  {flowsave_src[:500]}")

# ============================================================
# Step 2: 查看form数据
# ============================================================
print("\nStep 2: form数据")
form_data = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form||{};
    var keys=Object.keys(form);
    var result={};
    for(var i=0;i<keys.length;i++){
        var v=form[keys[i]];
        if(v===null||v===undefined||v===''||v===false)continue;
        if(Array.isArray(v))result[keys[i]]='A['+v.length+']:'+JSON.stringify(v).substring(0,40);
        else if(typeof v==='object')result[keys[i]]=JSON.stringify(v).substring(0,40);
        else result[keys[i]]=v;
    }
    return {formKeys:keys.length,data:result};
})()""")
print(f"  {json.dumps(form_data, ensure_ascii=False)[:500] if isinstance(form_data,dict) else form_data}")

# ============================================================
# Step 3: 确保form数据完整
# ============================================================
print("\nStep 3: 确保form数据完整")
ensure = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form;
    if(!form)return'no_form';
    
    // 确保关键字段
    if(!form.entTypeCode)comp.$set(form,'entTypeCode','1100');
    if(!form.entType)comp.$set(form,'entType','1100');
    if(!form.busiType)comp.$set(form,'busiType','02_4');
    if(!form.distList||!form.distList.length)comp.$set(form,'distList',['450000','450100','450103']);
    if(!form.nameCode&&form.nameCode!==0)comp.$set(form,'nameCode','0');
    if(!form.registerCapital)comp.$set(form,'registerCapital','100');
    if(!form.moneyKindCode)comp.$set(form,'moneyKindCode','156');
    
    return {formSet:true,entTypeCode:form.entTypeCode,busiType:form.busiType,distList:form.distList,nameCode:form.nameCode};
})()""")
print(f"  {ensure}")

# ============================================================
# Step 4: 调用flowSave
# ============================================================
print("\nStep 4: 调用flowSave")
save_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    try{
        comp.flowSave();
        return {called:true};
    }catch(e){
        return {error:e.message.substring(0,100)};
    }
})()""", timeout=20)
print(f"  {save_result}")
time.sleep(8)

# ============================================================
# Step 5: 检查结果
# ============================================================
print("\nStep 5: 检查结果")
cur = ev("location.hash")
print(f"  路由: {cur}")

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    var est=findComp(vm,'establish',0);
    return {flowControl:!!fc,withoutName:!!wn,establish:!!est,hash:location.hash};
})()""")
print(f"  组件: {comps}")

# 如果有without-name
if isinstance(comps, dict) and comps.get('withoutName'):
    print("  点击toNotName...")
    ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0);
        if(wn)wn.toNotName();
    })()""")
    time.sleep(5)
    comps2 = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        return {flowControl:!!fc,hash:location.hash};
    })()""")
    print(f"  toNotName后: {comps2}")

# 如果到达flow-control，立即填表+保存
if isinstance(comps, dict) and comps.get('flowControl'):
    print("\n  ✅ 到达flow-control！开始填表+保存...")
    
    FC = "function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"
    
    # initData
    ev(f"""(function(){{var vm=document.getElementById('app').__vue__;{FC};var fc=findComp(vm,'flow-control',0);fc.initData()}})()""", timeout=15)
    time.sleep(3)
    
    # regist-info
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;{FC};
        var ri=findComp(vm,'regist-info',0);if(!ri)return;
        var f=ri.registForm||ri.$data?.registForm;if(!f)return;
        ri.$set(f,'registerCapital','100');ri.$set(f,'subCapital','100');
        ri.$set(f,'shouldInvestWay','1');ri.$set(f,'entPhone','13800138000');
        ri.$set(f,'postcode','530000');ri.$set(f,'operatorNum','5');
        ri.$set(f,'empNum','5');ri.$set(f,'namePreFlag','1');
        ri.$set(f,'partnerNum','0');ri.$set(f,'busType','1');
        ri.$set(f,'moneyKindCode','156');ri.$set(f,'moneyKindCodeName','人民币');
        ri.$set(f,'setWay','01');ri.$set(f,'accountType','1');
        ri.$set(f,'licenseRadio','0');ri.$set(f,'copyCerNum','1');
        ri.$set(f,'businessModeGT','10');ri.$set(f,'organize','1');
        ri.$set(f,'investMoney','100');
    }})()""")
    
    # DOM同步
    ev("""(function(){
        var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
        document.querySelectorAll('.el-form-item').forEach(function(item){
            var label=item.querySelector('.el-form-item__label')?.textContent?.trim()||'';
            var input=item.querySelector('input');
            if(!input)return;
            if(label.includes('从业人数')){s.call(input,'5');input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));input.dispatchEvent(new Event('blur',{bubbles:true}));}
            if(label.includes('详细地址')&&!label.includes('生产经营')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}));}
            if(label.includes('生产经营地详细')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}));}
        });
    })()""")
    
    # 行业类型
    ev(f"""(function(){{var vm=document.getElementById('app').__vue__;{FC};var bi=findComp(vm,'businese-info',0);if(bi)bi.treeSelectChange('I65')}})()""")
    time.sleep(3)
    
    # 经营范围
    ev(f"""(function(){{var vm=document.getElementById('app').__vue__;{FC};var br=findComp(vm,'tni-business-range',0);if(br&&typeof br.init==='function')br.init()}})()""", timeout=15)
    time.sleep(2)
    ev(f"""(function(){{var vm=document.getElementById('app').__vue__;{FC};var br=findComp(vm,'tni-business-range',0);if(br)br.search('软件开发')}})()""")
    time.sleep(2)
    confirm = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;{FC};
        var br=findComp(vm,'tni-business-range',0);var bi=findComp(vm,'businese-info',0);
        if(!br||!bi)return'no_comp';
        var sl=br.searchList||[];if(!sl.length)return'empty';
        var items=sl.slice(0,2);var names=items.map(function(x){{return x.name||x.indusTypeName||''}});
        bi.confirm({{busiAreaData:items,genBusiArea:names.join(';'),busiAreaCode:items[0].pid||'65',busiAreaName:names.join(';'),firstPlaceParams:{{firstPlace:'license',param:items}}}});
        return {{ok:true,gen:names.join(';')}};
    }})()""")
    print(f"  confirm: {confirm}")
    
    # 住所
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;{FC};
        var resi=findComp(vm,'residence-information',0);if(!resi)return;
        var f=resi.residenceForm||resi.$data?.residenceForm;if(!f)return;
        resi.$set(f,'distCode','450103');resi.$set(f,'distCodeName','青秀区');
        resi.$set(f,'fisDistCode','450103');resi.$set(f,'address','广西壮族自治区/南宁市/青秀区');
        resi.$set(f,'detAddress','民族大道100号');resi.$set(f,'regionCode','450103');
        resi.$set(f,'regionName','青秀区');resi.$set(f,'businessAddress','广西壮族自治区/南宁市/青秀区');
        resi.$set(f,'detBusinessAddress','民族大道100号');resi.$set(f,'isSelectDistCode','1');
        resi.$set(f,'havaAdress','0');
        var fc=findComp(vm,'flow-control',0);
        if(fc){{var bdi=fc.$data.businessDataInfo;if(bdi){{bdi.distCode='450103';bdi.distCodeName='青秀区';bdi.fisDistCode='450103';bdi.address='广西壮族自治区/南宁市/青秀区';bdi.detAddress='民族大道100号';bdi.regionCode='450103';bdi.regionName='青秀区';bdi.businessAddress='广西壮族自治区/南宁市/青秀区';bdi.detBusinessAddress='民族大道100号';}}}}
    }})()""")
    
    # 拦截请求
    ev("""(function(){
        window.__save_req=null;window.__save_resp=null;
        var origSend=XMLHttpRequest.prototype.send;
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
        XMLHttpRequest.prototype.send=function(body){
            var url=this.__url||'';
            if(url.includes('operationBusinessData')){
                window.__save_req={url:url,body:body||'',bodyLen:(body||'').length};
                var self=this;
                self.addEventListener('load',function(){window.__save_resp={status:self.status,text:self.responseText||''}});
            }
            return origSend.apply(this,arguments);
        };
    })()""")
    
    # 保存并下一步
    click = ev("""(function(){
        var all=document.querySelectorAll('button,.el-button');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.includes('保存并下一步')&&!all[i].disabled){all[i].click();return{clicked:t}}
        }
        return 'no_btn';
    })()""")
    print(f"  保存: {click}")
    time.sleep(10)
    
    # 分析请求
    req = ev("window.__save_req")
    resp = ev("window.__save_resp")
    
    if isinstance(req, dict):
        body = req.get('body','')
        print(f"  请求URL: {req.get('url','')[:80]}")
        print(f"  body长度: {req.get('bodyLen',0)}")
        if body:
            try:
                bobj = json.loads(body)
                ba = bobj.get('busiAreaData')
                if isinstance(ba, str):
                    print(f"  ⚠️ busiAreaData: STRING len={len(ba)}")
                elif isinstance(ba, (list, dict)):
                    print(f"  ✅ busiAreaData: {'ARRAY' if isinstance(ba,list) else 'OBJECT'}")
                gba = bobj.get('genBusiArea','')
                print(f"  genBusiArea: {str(gba)[:50]}")
                with open(r'g:\UFO\政务平台\data\save_body_final.json', 'w', encoding='utf-8') as f:
                    json.dump(bobj, f, ensure_ascii=False, indent=2)
                print(f"  已保存 ({len(bobj)} keys)")
            except:
                print(f"  body非JSON: {body[:200]}")
    
    if isinstance(resp, dict):
        print(f"  API status={resp.get('status')}")
        text = resp.get('text','')
        if text:
            try:
                p = json.loads(text)
                code = p.get('code','')
                msg = p.get('msg','')[:80]
                print(f"  code={code} msg={msg}")
                if str(code) in ['0','0000','200']:
                    print("  ✅✅✅ 保存成功！✅✅✅")
            except:
                print(f"  raw: {text[:200]}")

print("\n✅ 完成")
