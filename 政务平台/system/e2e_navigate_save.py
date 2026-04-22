#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到设立登记表单 → 填表 → 保存 → 分析A0002"""
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
# Step 1: 导航到设立登记
# ============================================================
print("Step 1: 导航到设立登记")
nav = ev("""(function(){
    var router=window.VueRouter||document.getElementById('app').__vue__?.$router||document.getElementById('app').__vue__?.$root?.$router;
    if(!router)return'no_router';
    // 导航到名称登记入口
    router.push('/index/page?fromProject=name-register&fromPage=%2Fnamenot');
    return 'navigating';
})()""", timeout=10)
print(f"  导航: {nav}")
time.sleep(3)

# 检查当前路由
cur = ev("location.hash")
print(f"  当前路由: {cur}")

# ============================================================
# Step 2: 找到without-name或establish组件
# ============================================================
print("\nStep 2: 查找入口组件")
comps = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var wn=findComp(vm,'without-name',0);
    var est=findComp(vm,'establish',0);
    var fc=findComp(vm,'flow-control',0);
    return {{withoutName:!!wn,establish:!!est,flowControl:!!fc,hash:location.hash}};
}})()""")
print(f"  组件: {comps}")

# 如果在without-name页面，点击跳过
if isinstance(comps, dict) and comps.get('withoutName'):
    print("  点击跳过名称选择...")
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var wn=findComp(vm,'without-name',0);
        if(wn)wn.toNotName();
        return 'clicked_toNotName';
    }})()""")
    time.sleep(3)

# 检查establish
comps2 = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var est=findComp(vm,'establish',0);
    var fc=findComp(vm,'flow-control',0);
    return {{establish:!!est,flowControl:!!fc,hash:location.hash}};
}})()""")
print(f"  组件2: {comps2}")

# 如果在establish页面，选择企业类型并跳转
if isinstance(comps2, dict) and comps2.get('establish') and not comps2.get('flowControl'):
    print("  选择企业类型(1100=有限责任公司)...")
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var est=findComp(vm,'establish',0);
        if(!est)return'no_est';
        // 设置企业类型
        est.$set(est.$data,'radioGroup','1100');
        est.checkchange('1100',true);
        // 点击下一步
        setTimeout(function(){{est.nextBtn()}},1000);
        return 'est_next';
    }})()""", timeout=10)
    time.sleep(5)

# ============================================================
# Step 3: 检查是否到达flow-control
# ============================================================
print("\nStep 3: 检查flow-control")
fc_check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    return {{found:true,hash:location.hash,hasBdi:!!fc.$data?.businessDataInfo}};
}})()""")
print(f"  flow-control: {fc_check}")

# 如果还没到flow-control，可能需要namenotice步骤
if not isinstance(fc_check, dict) or not fc_check.get('found'):
    print("  尝试直接导航到namenot...")
    ev("""(function(){
        var router=document.getElementById('app').__vue__.$router;
        router.push('/name/namenotice?fromProject=name-register');
    })()""")
    time.sleep(3)
    
    # 再检查
    fc_check2 = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        return {{found:!!fc,hash:location.hash}};
    }})()""")
    print(f"  重试: {fc_check2}")

# ============================================================
# Step 4: 如果flow-control存在，初始化+填表+保存
# ============================================================
print("\nStep 4: 初始化+填表")
init_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    fc.initData();
    return 'init_done';
}})()""", timeout=15)
print(f"  initData: {init_result}")

if 'init_done' in str(init_result):
    time.sleep(3)
    
    # 填regist-info
    ev(f"""(function(){{
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
        return 'ri_ok';
    }})()""")
    
    # DOM同步
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
    
    # 行业类型
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var bi=findComp(vm,'businese-info',0);
        if(bi)bi.treeSelectChange('I65');
    }})()""")
    time.sleep(3)
    
    # 经营范围
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var br=findComp(vm,'tni-business-range',0);
        if(!br)return'no_br';
        if(typeof br.init==='function')br.init();
    }})()""", timeout=15)
    time.sleep(2)
    
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var br=findComp(vm,'tni-business-range',0);
        if(!br)return'no_br';
        br.search('软件开发');
    }})()""")
    time.sleep(2)
    
    confirm_result = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var br=findComp(vm,'tni-business-range',0);
        var bi=findComp(vm,'businese-info',0);
        if(!br||!bi)return'no_comp';
        var sl=br.searchList||[];
        if(!sl.length)return'empty_search';
        var items=sl.slice(0,2);
        var names=items.map(function(x){{return x.name||x.indusTypeName||''}});
        var confirmData={{busiAreaData:items,genBusiArea:names.join(';'),busiAreaCode:items[0].pid||'65',busiAreaName:names.join(';'),firstPlaceParams:{{firstPlace:'license',param:items}}}};
        bi.confirm(confirmData);
        return {{ok:true,items:items.length,gen:names.join(';')}};
    }})()""")
    print(f"  confirm: {confirm_result}")
    
    # 住所
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var resi=findComp(vm,'residence-information',0);
        if(!resi)return'no_resi';
        var f=resi.residenceForm||resi.$data?.residenceForm;
        if(!f)return'no_form';
        resi.$set(f,'distCode','450103');resi.$set(f,'distCodeName','青秀区');
        resi.$set(f,'fisDistCode','450103');resi.$set(f,'address','广西壮族自治区/南宁市/青秀区');
        resi.$set(f,'detAddress','民族大道100号');resi.$set(f,'regionCode','450103');
        resi.$set(f,'regionName','青秀区');resi.$set(f,'businessAddress','广西壮族自治区/南宁市/青秀区');
        resi.$set(f,'detBusinessAddress','民族大道100号');resi.$set(f,'isSelectDistCode','1');
        resi.$set(f,'havaAdress','0');
        var fc=findComp(vm,'flow-control',0);
        if(fc){{
            var bdi=fc.$data.businessDataInfo;
            if(bdi){{bdi.distCode='450103';bdi.distCodeName='青秀区';bdi.fisDistCode='450103';
            bdi.address='广西壮族自治区/南宁市/青秀区';bdi.detAddress='民族大道100号';
            bdi.regionCode='450103';bdi.regionName='青秀区';
            bdi.businessAddress='广西壮族自治区/南宁市/青秀区';bdi.detBusinessAddress='民族大道100号';}}
        }}
    }})()""")
    
    # ============================================================
    # Step 5: 拦截 + 保存
    # ============================================================
    print("\nStep 5: 拦截请求并保存")
    ev("""(function(){
        window.__save_req=null;
        window.__save_resp=null;
        var origSend=XMLHttpRequest.prototype.send;
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
        XMLHttpRequest.prototype.send=function(body){
            var url=this.__url||'';
            if(url.includes('operationBusinessData')){
                window.__save_req={url:url,body:body||'',bodyLen:(body||'').length};
                var self=this;
                self.addEventListener('load',function(){
                    window.__save_resp={status:self.status,text:self.responseText||''};
                });
            }
            return origSend.apply(this,arguments);
        };
    })()""")
    
    # 点击保存并下一步
    click = ev("""(function(){
        var all=document.querySelectorAll('button,.el-button');
        for(var i=0;i<all.length;i++){
            var t=all[i].textContent?.trim()||'';
            if(t.includes('保存并下一步')){
                all[i].click();
                return {clicked:t};
            }
        }
        return 'no_btn';
    })()""")
    print(f"  点击: {click}")
    time.sleep(8)
    
    # ============================================================
    # Step 6: 分析请求
    # ============================================================
    print("\nStep 6: 分析请求")
    req = ev("window.__save_req")
    resp = ev("window.__save_resp")
    
    if isinstance(req, dict):
        body = req.get('body','')
        print(f"  URL: {req.get('url','')[:80]}")
        print(f"  body长度: {req.get('bodyLen',0)}")
        
        if body:
            is_json = body.startswith('{') or body.startswith('[')
            if is_json:
                try:
                    bobj = json.loads(body)
                    print(f"  body是JSON ({len(bobj)} keys)")
                    
                    ba = bobj.get('busiAreaData')
                    if ba is None:
                        print("  ⚠️ busiAreaData: null/missing")
                    elif isinstance(ba, str):
                        print(f"  ⚠️ busiAreaData: STRING len={len(ba)}")
                        try:
                            d = json.loads(ba)
                            print(f"    → parsed: {type(d).__name__}")
                        except:
                            print(f"    → first80: {ba[:80]}")
                    elif isinstance(ba, (list, dict)):
                        typ = 'ARRAY' if isinstance(ba,list) else 'OBJECT'
                        print(f"  ✅ busiAreaData: {typ}")
                        if isinstance(ba, dict):
                            print(f"    keys: {list(ba.keys())}")
                        elif isinstance(ba, list) and ba:
                            print(f"    len={len(ba)}, first: {json.dumps(ba[0], ensure_ascii=False)[:80]}")
                    
                    gba = bobj.get('genBusiArea','')
                    print(f"  genBusiArea: {str(gba)[:50]}")
                    print(f"  operatorNum: {bobj.get('operatorNum')}")
                    print(f"  distCode: {bobj.get('distCode')}")
                    
                    with open(r'g:\UFO\政务平台\data\save_body_final.json', 'w', encoding='utf-8') as f:
                        json.dump(bobj, f, ensure_ascii=False, indent=2)
                    print(f"  已保存 ({len(bobj)} keys)")
                except Exception as e:
                    print(f"  parse error: {e}")
            else:
                print(f"  ⚠️ body非JSON, first300: {body[:300]}")
                # 保存raw
                with open(r'g:\UFO\政务平台\data\save_body_raw.txt', 'w', encoding='utf-8') as f:
                    f.write(body)
                print(f"  raw已保存")
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
