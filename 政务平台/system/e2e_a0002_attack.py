#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""flow-control填表+XHR拦截+保存并下一步+分析A0002"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        # 优先找core.html页面
        page = [p for p in pages if p.get("type")=="page" and "core.html" in p.get("url","")]
        if not page:
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

FC = "function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"

# ============================================================
# Step 1: 确认flow-control存在
# ============================================================
print("Step 1: 确认flow-control")
fc_check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    return {{
        hasFc:true,
        busiCompUrlPaths:(fc.$data?.busiCompUrlPaths||[]).length,
        currentComp:fc.$data?.curCompUrlPath||'',
        paramsKeys:Object.keys(fc.$data?.params||{{}}).slice(0,10),
        bdiKeys:Object.keys(fc.$data?.businessDataInfo||{{}}).slice(0,15)
    }};
}})()""")
print(f"  {fc_check}")

if fc_check == 'no_fc' or (isinstance(fc_check, str) and 'no_fc' in fc_check):
    print("  ❌ 没有flow-control，退出")
    exit(1)

# ============================================================
# Step 2: initData
# ============================================================
print("\nStep 2: initData")
init_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    fc.initData();
    return {{called:true}};
}})()""", timeout=20)
print(f"  {init_result}")
time.sleep(5)

# ============================================================
# Step 3: 填regist-info
# ============================================================
print("\nStep 3: 填regist-info")
ri_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return'no_ri';
    var f=ri.registForm||ri.$data?.registForm;
    if(!f)return'no_form';
    ri.$set(f,'registerCapital','100');
    ri.$set(f,'subCapital','100');
    ri.$set(f,'shouldInvestWay','1');
    ri.$set(f,'entPhone','13800138000');
    ri.$set(f,'postcode','530000');
    ri.$set(f,'operatorNum','5');
    ri.$set(f,'empNum','5');
    ri.$set(f,'namePreFlag','1');
    ri.$set(f,'partnerNum','0');
    ri.$set(f,'busType','1');
    ri.$set(f,'moneyKindCode','156');
    ri.$set(f,'moneyKindCodeName','人民币');
    ri.$set(f,'setWay','01');
    ri.$set(f,'accountType','1');
    ri.$set(f,'licenseRadio','0');
    ri.$set(f,'copyCerNum','1');
    ri.$set(f,'businessModeGT','10');
    ri.$set(f,'organize','1');
    ri.$set(f,'investMoney','100');
    ri.$set(f,'fisDistCode','450103');
    ri.$set(f,'distCodeName','青秀区');
    ri.$set(f,'provinceCode','450000');
    ri.$set(f,'provinceName','广西壮族自治区');
    ri.$set(f,'cityCode','450100');
    ri.$set(f,'cityName','南宁市');
    return {{set:true,keys:Object.keys(f).length}};
}})()""")
print(f"  {ri_result}")

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

# ============================================================
# Step 4: 行业类型I65
# ============================================================
print("\nStep 4: 行业类型I65")
industry_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    bi.treeSelectChange('I65');
    return {{called:true}};
}})()""")
print(f"  {industry_result}")
time.sleep(3)

# ============================================================
# Step 5: 经营范围confirm
# ============================================================
print("\nStep 5: 经营范围confirm")
confirm_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    var bi=findComp(vm,'businese-info',0);
    if(!br||!bi)return'no_comp';
    // 初始化searchList
    if(typeof br.init==='function')br.init();
    return {{brFound:true,biFound:true,searchListLen:(br.searchList||[]).length}};
}})()""", timeout=15)
print(f"  init: {confirm_result}")
time.sleep(3)

# 搜索经营范围
search_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    br.search('软件开发');
    return {{searched:true,searchListLen:(br.searchList||[]).length}};
}})()""")
print(f"  search: {search_result}")
time.sleep(2)

# confirm
confirm = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    var bi=findComp(vm,'businese-info',0);
    if(!br||!bi)return'no_comp';
    var sl=br.searchList||[];
    if(!sl.length)return'empty_searchList';
    var items=sl.slice(0,2);
    var names=items.map(function(x){{return x.name||x.indusTypeName||''}});
    bi.confirm({{
        busiAreaData:items,
        genBusiArea:names.join(';'),
        busiAreaCode:items[0].pid||'65',
        busiAreaName:names.join(';'),
        firstPlaceParams:{{firstPlace:'license',param:items}}
    }});
    return {{ok:true,gen:names.join(';'),itemsLen:items.length}};
}})()""")
print(f"  confirm: {confirm}")

# ============================================================
# Step 6: 住所信息
# ============================================================
print("\nStep 6: 住所信息")
resi_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var resi=findComp(vm,'residence-information',0);
    if(!resi)return'no_resi';
    var f=resi.residenceForm||resi.$data?.residenceForm;
    if(!f)return'no_form';
    resi.$set(f,'distCode','450103');
    resi.$set(f,'distCodeName','青秀区');
    resi.$set(f,'fisDistCode','450103');
    resi.$set(f,'address','广西壮族自治区/南宁市/青秀区');
    resi.$set(f,'detAddress','民族大道100号');
    resi.$set(f,'regionCode','450103');
    resi.$set(f,'regionName','青秀区');
    resi.$set(f,'businessAddress','广西壮族自治区/南宁市/青秀区');
    resi.$set(f,'detBusinessAddress','民族大道100号');
    resi.$set(f,'isSelectDistCode','1');
    resi.$set(f,'havaAdress','0');
    // 同步到bdi
    var fc=findComp(vm,'flow-control',0);
    if(fc){{
        var bdi=fc.$data?.businessDataInfo;
        if(bdi){{
            bdi.distCode='450103';bdi.distCodeName='青秀区';bdi.fisDistCode='450103';
            bdi.address='广西壮族自治区/南宁市/青秀区';bdi.detAddress='民族大道100号';
            bdi.regionCode='450103';bdi.regionName='青秀区';
            bdi.businessAddress='广西壮族自治区/南宁市/青秀区';bdi.detBusinessAddress='民族大道100号';
        }}
    }}
    return {{set:true}};
}})()""")
print(f"  {resi_result}")

# ============================================================
# Step 7: 拦截XHR
# ============================================================
print("\nStep 7: 拦截XHR")
ev("""(function(){
    window.__save_req=null;
    window.__save_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')||url.includes('BasicInfo')){
            window.__save_req={url:url,body:body||'',bodyLen:(body||'').length};
            var self=this;
            self.addEventListener('load',function(){
                window.__save_resp={status:self.status,text:self.responseText||''};
            });
        }
        return origSend.apply(this,arguments);
    };
    return 'intercepted';
})()""")

# ============================================================
# Step 8: 保存并下一步
# ============================================================
print("\nStep 8: 保存并下一步")
# 先检查前端验证
errors_before = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误(前): {errors_before}")

# 点击保存并下一步
click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('保存并下一步')||t.includes('下一步'))&&!all[i].disabled&&all[i].offsetParent!==null){
            all[i].click();
            return {clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  点击: {click}")
time.sleep(12)

# ============================================================
# Step 9: 分析请求和响应
# ============================================================
print("\nStep 9: 分析请求和响应")
req = ev("window.__save_req")
resp = ev("window.__save_resp")

if isinstance(req, dict):
    body = req.get('body','')
    print(f"  请求URL: {req.get('url','')[:80]}")
    print(f"  body长度: {req.get('bodyLen',0)}")
    if body:
        try:
            bobj = json.loads(body)
            # 分析关键字段
            ba = bobj.get('busiAreaData')
            gba = bobj.get('genBusiArea')
            opn = bobj.get('operatorNum')
            dc = bobj.get('distCode')
            
            print(f"\n  === 关键字段分析 ===")
            if isinstance(ba, str):
                print(f"  ⚠️ busiAreaData: STRING len={len(ba)}")
                print(f"     前50字符: {ba[:50]}")
                # 尝试decode
                try:
                    decoded = json.loads(ba)
                    print(f"     decode后: {type(decoded).__name__} len={len(decoded) if isinstance(decoded,(list,dict)) else 'N/A'}")
                except:
                    try:
                        import urllib.parse
                        decoded = urllib.parse.unquote(ba)
                        print(f"     URL decode后: {decoded[:50]}")
                    except:
                        pass
            elif isinstance(ba, list):
                print(f"  ✅ busiAreaData: ARRAY len={len(ba)}")
                if ba:
                    print(f"     第一项keys: {list(ba[0].keys())[:8] if isinstance(ba[0],dict) else ba[0]}")
            elif isinstance(ba, dict):
                print(f"  ✅ busiAreaData: OBJECT keys={list(ba.keys())[:5]}")
            else:
                print(f"  busiAreaData: {type(ba).__name__} = {str(ba)[:50]}")
            
            print(f"  genBusiArea: {type(gba).__name__} = {str(gba)[:50]}")
            print(f"  operatorNum: {opn}")
            print(f"  distCode: {dc}")
            
            # 保存完整body
            with open(r'g:\UFO\政务平台\data\save_body_a0002.json', 'w', encoding='utf-8') as f:
                json.dump(bobj, f, ensure_ascii=False, indent=2)
            print(f"  已保存 ({len(bobj)} keys)")
            
        except json.JSONDecodeError:
            # 可能是URL-encoded
            print(f"  body非JSON, 前200字符: {body[:200]}")
else:
    print(f"  无请求捕获: {req}")

if isinstance(resp, dict):
    print(f"\n  === API响应 ===")
    print(f"  status: {resp.get('status')}")
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            code = p.get('code','')
            msg = p.get('msg','')[:100]
            data = p.get('data','')
            print(f"  code: {code}")
            print(f"  msg: {msg}")
            if str(code) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！✅✅✅")
            else:
                print(f"  ❌ A0002错误！" if 'A0002' in str(code) or 'A0002' in msg else f"  ❌ 错误!")
                # 保存响应
                with open(r'g:\UFO\政务平台\data\save_resp_a0002.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  无响应: {resp}")

# ============================================================
# Step 10: 验证错误检查
# ============================================================
print("\nStep 10: 验证错误")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  {errors}")

print("\n✅ 完成")
