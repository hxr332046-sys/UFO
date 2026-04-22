#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完整流程：填表→拦截请求→点击保存→分析body→攻克A0002"""
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 0: 检查页面状态
# ============================================================
print("Step 0: 页面状态")
hash_val = ev("location.hash")
print(f"  路由: {hash_val}")

# 检查是否在表单页面
if not hash_val or 'namenot' not in str(hash_val):
    print("  需要先导航到表单页面...")
    # 检查当前URL
    cur_url = ev("location.href")
    print(f"  当前URL: {cur_url[:80] if isinstance(cur_url,str) else cur_url}")

# ============================================================
# Step 1: 初始化表单
# ============================================================
print("\nStep 1: 初始化表单")
init_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    fc.initData();
    return 'init_done';
}})()""", timeout=15)
print(f"  initData: {init_result}")
time.sleep(3)

# ============================================================
# Step 2: 填写regist-info字段
# ============================================================
print("\nStep 2: 填写regist-info")
fill_ri = ev(f"""(function(){{
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
    return 'ri_filled';
}})()""")
print(f"  regist-info: {fill_ri}")

# DOM同步从业人数
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
            input.dispatchEvent(new Event('blur',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 3: 设置行业类型
# ============================================================
print("\nStep 3: 行业类型I65")
industry_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    bi.treeSelectChange('I65');
    return 'industry_set';
}})()""", timeout=10)
print(f"  行业类型: {industry_result}")
time.sleep(3)

# ============================================================
# Step 4: 设置经营范围
# ============================================================
print("\nStep 4: 经营范围confirm")
confirm_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    // 初始化
    if(typeof br.init==='function')br.init();
    return 'br_init:'+JSON.stringify({{searchListLen:(br.searchList||[]).length,allListLen:(br.allBusinessList||[]).length}});
}})()""", timeout=15)
print(f"  business-range: {confirm_result}")
time.sleep(2)

# 搜索经营范围
search_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    br.search('软件开发');
    return 'search_done:listLen='+(br.searchList||[]).length;
}})()""", timeout=10)
print(f"  搜索: {search_result}")
time.sleep(2)

# 获取searchList并confirm
confirm_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    var sl=br.searchList||[];
    if(!sl.length)return'empty_searchList';
    // 取前2项
    var items=sl.slice(0,2);
    var names=items.map(function(x){{return x.name||x.indusTypeName||''}});
    var genBusiArea=names.join(';');
    var busiAreaCode=items[0].pid||'65';
    var busiAreaName=genBusiArea;
    var firstPlaceParams={{firstPlace:'license',param:items}};
    var confirmData={{busiAreaData:items,genBusiArea:genBusiArea,busiAreaCode:busiAreaCode,busiAreaName:busiAreaName,firstPlaceParams:firstPlaceParams}};
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    bi.confirm(confirmData);
    return {{confirmed:true,items:items.length,genBusiArea:genBusiArea,busiAreaCode:busiAreaCode}};
}})()""", timeout=10)
print(f"  confirm: {confirm_data}")
time.sleep(1)

# ============================================================
# Step 5: 设置住所
# ============================================================
print("\nStep 5: 住所信息")
residence_result = ev(f"""(function(){{
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
        var bdi=fc.$data.businessDataInfo;
        if(bdi){{
            bdi.distCode='450103';bdi.distCodeName='青秀区';bdi.fisDistCode='450103';
            bdi.address='广西壮族自治区/南宁市/青秀区';bdi.detAddress='民族大道100号';
            bdi.regionCode='450103';bdi.regionName='青秀区';
            bdi.businessAddress='广西壮族自治区/南宁市/青秀区';bdi.detBusinessAddress='民族大道100号';
        }}
    }}
    return 'resi_set';
}})()""")
print(f"  住所: {residence_result}")

# DOM同步详细地址
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('详细地址')&&!label.includes('生产经营')){
            s.call(input,'民族大道100号');
            input.dispatchEvent(new Event('input',{bubbles:true}));
        }
        if(label.includes('生产经营地详细')){
            s.call(input,'民族大道100号');
            input.dispatchEvent(new Event('input',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 6: 验证
# ============================================================
print("\nStep 6: 前端验证")
errors = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var errs=[];
    // 检查各组件验证
    var comps=['regist-info','businese-info','residence-information'];
    for(var i=0;i<comps.length;i++){{
        var c=findComp(vm,comps[i],0);
        if(c){{
            var formRef=c.$refs?.registFormRef||c.$refs?.busineseFormRef||c.$refs?.residenceFormRef||c.$refs?.elForm;
            if(formRef){{
                try{{
                    var valid=formRef.validate();
                    // 同步验证
                }}catch(e){{}}
            }}
        }}
    }}
    // 收集DOM错误
    var domErrs=document.querySelectorAll('.el-form-item__error');
    for(var j=0;j<domErrs.length;j++){{
        var t=domErrs[j].textContent?.trim()||'';
        if(t)errs.push(t.substring(0,40));
    }}
    return errs;
}})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 7: 拦截请求 + 点击保存
# ============================================================
print("\nStep 7: 拦截请求并保存")
ev("""(function(){
    window.__save_req=null;
    window.__save_resp=null;
    window.__all_xhr=[];
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){
        this.__url=u;this.__method=m;
        return origOpen.apply(this,arguments);
    };
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__save_req={url:url,method:this.__method,body:body||'',bodyLen:(body||'').length,
                contentType:this.getRequestHeader?.('Content-Type')||''};
            var self=this;
            self.addEventListener('load',function(){
                window.__save_resp={status:self.status,text:self.responseText||''};
            });
        }
        window.__all_xhr.push({url:url,method:this.__method,bodyLen:(body||'').length});
        return origSend.apply(this,arguments);
    };
})()""")

# 点击保存并下一步
click_result = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('保存并下一步')){
            all[i].click();
            return {clicked:t};
        }
    }
    // 备选: fc.save()
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(fc){
        try{fc.save(null,null,'working');return{clicked:'fc.save(working)'};}catch(e){return{error:e.message};}
    }
    return 'no_btn';
})()""")
print(f"  点击: {click_result}")
time.sleep(8)

# ============================================================
# Step 8: 分析请求
# ============================================================
print("\nStep 8: 请求分析")
req = ev("window.__save_req")
resp = ev("window.__save_resp")
all_xhr = ev("window.__all_xhr")

print(f"  所有XHR: {all_xhr}")

if isinstance(req, dict):
    body = req.get('body','')
    print(f"  URL: {req.get('url','')[:80]}")
    print(f"  Method: {req.get('method','')}")
    print(f"  Content-Type: {req.get('contentType','')}")
    print(f"  body长度: {req.get('bodyLen',0)}")
    
    if body:
        # 先看body是JSON还是URL-encoded
        if body.startswith('{') or body.startswith('['):
            try:
                bobj = json.loads(body)
                print(f"  ✅ body是JSON ({len(bobj)} keys)")
            except:
                print(f"  ⚠️ body看起来像JSON但解析失败")
                bobj = None
        else:
            # URL-encoded
            print(f"  ⚠️ body是URL-encoded, first200: {body[:200]}")
            # 尝试解析
            try:
                from urllib.parse import parse_qs
                # 可能是单个key的JSON
                bobj = json.loads(body) if body.startswith('{') else None
                if bobj is None:
                    # 可能是 form-encoded
                    print(f"  尝试URL decode...")
                    # 找busiAreaData
                    ba_idx = body.find('busiAreaData')
                    if ba_idx >= 0:
                        print(f"  busiAreaData at pos {ba_idx}: ...{body[ba_idx:ba_idx+100]}...")
                    bobj = None
            except:
                bobj = None
        
        if bobj:
            ba = bobj.get('busiAreaData')
            if ba is None:
                print("  ⚠️ busiAreaData: null/missing")
            elif isinstance(ba, str):
                print(f"  ⚠️ busiAreaData: STRING len={len(ba)}")
                try:
                    d = json.loads(ba)
                    print(f"    → parsed: {type(d).__name__}")
                    if isinstance(d, dict):
                        print(f"    → keys: {list(d.keys())}")
                    elif isinstance(d, list):
                        print(f"    → array len={len(d)}")
                except:
                    print(f"    → first80: {ba[:80]}")
            elif isinstance(ba, (list, dict)):
                typ = 'ARRAY' if isinstance(ba,list) else 'OBJECT'
                print(f"  ✅ busiAreaData: {typ}")
                if isinstance(ba, dict):
                    print(f"    keys: {list(ba.keys())}")
                    if 'param' in ba:
                        print(f"    param.len={len(ba['param'])}, firstPlace={ba.get('firstPlace')}")
                elif isinstance(ba, list) and ba:
                    print(f"    len={len(ba)}, first: {json.dumps(ba[0], ensure_ascii=False)[:80]}")
            
            gba = bobj.get('genBusiArea','')
            if isinstance(gba, str) and '%' in gba:
                print(f"  ⚠️ genBusiArea: URL-encoded: {gba[:60]}")
            else:
                print(f"  genBusiArea: {str(gba)[:50]}")
            
            print(f"  operatorNum: {bobj.get('operatorNum')}")
            print(f"  distCode: {bobj.get('distCode')}")
            print(f"  businessAddress: {str(bobj.get('businessAddress',''))[:30]}")
            print(f"  detBusinessAddress: {str(bobj.get('detBusinessAddress',''))[:30]}")
            
            # 保存完整body
            with open(r'g:\UFO\政务平台\data\save_body_final.json', 'w', encoding='utf-8') as f:
                json.dump(bobj, f, ensure_ascii=False, indent=2)
            print(f"  完整body已保存 ({len(bobj)} keys)")
else:
    print(f"  无请求: {req}")

if isinstance(resp, dict):
    print(f"\n  API status={resp.get('status')}")
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
else:
    print(f"  无响应: {resp}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

print("\n✅ 完成")
