#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""填写表单后只拦截save body，不提交到服务端"""
import json, requests, websocket, time

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)

def ev(js, timeout=15):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
    ws.settimeout(timeout + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r.get("result", {}).get("result", {}).get("value")

# 刷新页面
print("刷新页面...")
ev("location.reload()")
time.sleep(8)

# ====== 快速填写所有字段 ======
print("填写表单...")

# 1. 企业住所
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业住所')&&!lb.textContent.includes('详细')){
            var input=items[i].querySelector('input');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)
for name in ["广西壮族自治区", "南宁市", "青秀区"]:
    ev(f"""(function(){{
        var popovers=document.querySelectorAll('.tne-data-picker-popover');
        for(var i=0;i<popovers.length;i++){{
            var p=popovers[i];if(p.offsetParent===null)continue;
            var items=p.querySelectorAll('.sample-item');
            for(var j=0;j<items.length;j++){{
                if(items[j].textContent?.trim()==='{name}'){{items[j].click();return 'ok'}}
            }}
        }}
    }})()""")
    time.sleep(2)

# 详细地址
ev("""(function(){
    var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('详细地址')){
            var input=items[i].querySelector('input.el-input__inner');
            if(input){setter.call(input,'民大道100号');input.dispatchEvent(new Event('input',{bubbles:true}));}
        }
    }
})()""")

# 2. 生产经营地址
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('生产经营地址')&&!lb.textContent.includes('详细')){
            var input=items[i].querySelector('input');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)
for name in ["广西壮族自治区", "南宁市", "青秀区"]:
    ev(f"""(function(){{
        var popovers=document.querySelectorAll('.tne-data-picker-popover');
        for(var i=0;i<popovers.length;i++){{
            var p=popovers[i];if(p.offsetParent===null)continue;
            var items=p.querySelectorAll('.sample-item');
            for(var j=0;j<items.length;j++){{
                if(items[j].textContent?.trim()==='{name}'){{items[j].click();return 'ok'}}
            }}
        }}
    }})()""")
    time.sleep(2)

# 生产经营地详细地址
ev("""(function(){
    var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('生产经营地详细地址')){
            var input=items[i].querySelector('input.el-input__inner');
            if(input){setter.call(input,'民大道100号');input.dispatchEvent(new Event('input',{bubbles:true}));}
        }
    }
})()""")

# 3. 企业类型
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('企业类型')){
            var input=items[i].querySelector('input');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var i=0;i<poppers.length;i++){
        if(poppers[i].offsetParent===null)continue;
        var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
        for(var j=0;j<nodes.length;j++){
            if(nodes[j].textContent?.trim()?.includes('[1100]')){
                nodes[j].click();return 'clicked_1100';
            }
        }
    }
})()""")
time.sleep(1)
# 同步企业类型状态
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    function findTreeSelect(vm,d){if(d>12)return null;if(vm.$options?.name==='tne-select-tree')return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findTreeSelect(vm.$children[i],d+1);if(r)return r}return null}
    function findBdi(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findBdi(vm.$children[i],d+1);if(r)return r}return null}
    
    var fc=findBdi(vm,0);
    // 找企业类型的tree (第一个tne-select-tree)
    var root=findComp(vm,'basic-info',0)||findComp(vm,'index',0);
    if(!root){
        // fallback: 从fc开始找
        root=fc;
    }
    var trees=[];
    function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-select-tree')trees.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
    scan(vm,0);
    // 第一个tree是企业类型
    if(trees.length>0){
        trees[0].valueId='1100';
        trees[0].valueTitle='有限责任公司';
    }
    if(fc){
        var bdi=fc.$data.businessDataInfo;
        fc.$set(bdi,'entType','1100');
        fc.$set(bdi,'entTypeName','有限责任公司');
    }
})()""")

# 4. 行业类型
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(lb&&lb.textContent.trim().includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)
# 展开I节点
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var i=0;i<poppers.length;i++){
        if(poppers[i].offsetParent===null)continue;
        var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
        for(var j=0;j<nodes.length;j++){
            if(nodes[j].textContent?.trim()?.includes('信息传输')){
                var expand=nodes[j].querySelector('.el-tree-node__expand-icon');
                if(expand)expand.click();
                return 'expanded';
            }
        }
    }
})()""")
time.sleep(3)
# 点击I65
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var i=0;i<poppers.length;i++){
        if(poppers[i].offsetParent===null)continue;
        var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
        for(var j=0;j<nodes.length;j++){
            if(nodes[j].textContent?.trim()?.includes('[65]')){
                nodes[j].click();return 'clicked_65';
            }
        }
    }
})()""")
time.sleep(1)
# 同步行业类型
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    function findTreeSelect(vm,d){if(d>12)return null;if(vm.$options?.name==='tne-select-tree')return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findTreeSelect(vm.$children[i],d+1);if(r)return r}return null}
    var bi=findComp(vm,'businese-info',0);
    if(bi){
        var trees=[];
        function scan(vm,d){if(d>12)return;if(vm.$options?.name==='tne-select-tree')trees.push(vm);for(var i=0;i<(vm.$children||[]).length;i++)scan(vm.$children[i],d+1)}
        scan(bi,0);
        if(trees.length>0){
            trees[0].valueId='I65';
            trees[0].valueTitle='软件和信息技术服务业';
        }
        var bf=bi.busineseForm;
        if(bf){
            bi.$set(bf,'itemIndustryTypeCode','I65');
            bi.$set(bf,'industryTypeName','软件和信息技术服务业');
        }
    }
})()""")

# 5. 经营范围
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var comp=findComp(vm,'businese-info',0);
    if(comp){
        comp.confirm({
            busiAreaData:[
                {id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
            ],
            genBusiArea:'软件开发;信息技术咨询服务',
            busiAreaCode:'I65',
            busiAreaName:'软件开发,信息技术咨询服务'
        });
        var bf=comp.busineseForm;
        if(bf){
            comp.$set(bf,'genBusiArea','软件开发;信息技术咨询服务');
            comp.$set(bf,'busiAreaCode','I65');
            comp.$set(bf,'busiAreaName','软件开发,信息技术咨询服务');
        }
    }
})()""")

# 6. 基本信息
ev("""(function(){
    var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
    function setInput(label,val){
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var lb=items[i].querySelector('.el-form-item__label');
            if(lb&&lb.textContent.trim().includes(label)){
                var input=items[i].querySelector('input.el-input__inner');
                if(input){setter.call(input,val);input.dispatchEvent(new Event('input',{bubbles:true}));}
            }
        }
    }
    setInput('企业名称','广西智信数据科技有限公司');
    setInput('注册资本','100');
    setInput('从业人数','5');
    setInput('联系电话','13800138000');
    setInput('邮政编码','530022');
    setInput('申请执照副本数量','1');
})()""")

# radio
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var lb=items[i].querySelector('.el-form-item__label');
        if(!lb)continue;
        var t=lb.textContent.trim();
        var radios=items[i].querySelectorAll('.el-radio');
        if(t.includes('设立方式')){
            for(var j=0;j<radios.length;j++){if(radios[j].textContent?.trim()?.includes('一般新设'))radios[j].click();}
        }
        if(t.includes('核算方式')){
            for(var j=0;j<radios.length;j++){if(radios[j].textContent?.trim()?.includes('独立核算'))radios[j].click();}
        }
        if(t.includes('经营期限')){
            for(var j=0;j<radios.length;j++){if(radios[j].textContent?.trim()?.includes('长期'))radios[j].click();}
        }
        if(t.includes('纸质营业执照')){
            for(var j=0;j<radios.length;j++){if(radios[j].textContent?.trim()?.includes('是'))radios[j].click();}
        }
    }
})()""")

time.sleep(2)
print("表单填写完成")

# ====== 拦截save body但不提交 ======
print("\n安装拦截器（阻止提交）...")
ev("""(function(){
    window.__captured_body=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')&&body){
            // 只抓取，不提交！
            window.__captured_body=body;
            console.log('[INTERCEPTED] save body captured, NOT sent');
            // 模拟成功响应
            Object.defineProperty(this,'status',{value:200,writable:false});
            Object.defineProperty(this,'responseText',{value:'{"code":"INTERCEPTED","msg":"body captured, not submitted"}',writable:false});
            this.onreadystatechange&&this.onreadystatechange();
            this.onload&&this.onload();
            return;
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 覆盖validate + 触发save（body会被拦截不提交）
print("触发save（body被拦截）...")
ev("""(function(){
    var forms=document.querySelectorAll('.el-form');
    for(var i=0;i<forms.length;i++){
        var comp=forms[i].__vue__;
        if(comp){comp.validate=function(cb){if(cb)cb(true);return true;};comp.clearValidate();}
    }
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
    var comp=find(vm,0);
    if(comp){try{comp.save(null,null,'working')}catch(e){}}
})()""", timeout=15)
time.sleep(5)

# 分析body
body = ev("window.__captured_body")
if body:
    try:
        bd = json.loads(body)
    except:
        bd = None
    
    if bd:
        with open("g:/UFO/政务平台/data/save_body_v3.json", "w", encoding="utf-8") as f:
            json.dump(bd, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== BODY ANALYSIS ({len(bd.keys())} keys) ===")
        for k in sorted(bd.keys()):
            v = bd[k]
            vs = str(v)
            if len(vs) > 100: vs = vs[:100] + '...'
            flag = ""
            if v is None or v == '' or v == 'null': flag = " ⚠️ EMPTY"
            elif '%7B' in vs or '%22' in vs: flag = " ⚠️ URL-ENCODED"
            print(f"  {k}: {vs}{flag}")
        
        # 重点检查
        print("\n=== 关键字段检查 ===")
        checks = {
            'entType': bd.get('entType'),
            'entTypeName': bd.get('entTypeName'),
            'itemIndustryTypeCode': bd.get('itemIndustryTypeCode'),
            'industryTypeName': bd.get('industryTypeName'),
            'registerCapital': bd.get('registerCapital'),
            'entPhone': bd.get('entPhone'),
            'postcode': bd.get('postcode'),
            'operatorNum': bd.get('operatorNum'),
            'accountType': bd.get('accountType'),
            'setWay': bd.get('setWay'),
            'busiPeriod': bd.get('busiPeriod'),
            'licenseRadio': bd.get('licenseRadio'),
            'copyCerNum': bd.get('copyCerNum'),
            'moneyKindCode': bd.get('moneyKindCode'),
            'genBusiArea': bd.get('genBusiArea'),
            'busiAreaCode': bd.get('busiAreaCode'),
            'busiAreaName': bd.get('busiAreaName'),
            'industryId': bd.get('industryId'),
            'areaCategory': bd.get('areaCategory'),
        }
        for k,v in checks.items():
            flag = " ⚠️ EMPTY" if (v is None or v == '') else ""
            print(f"  {k}: {v}{flag}")
        
        # busiAreaData格式
        bad = bd.get('busiAreaData')
        print(f"\n=== busiAreaData type={type(bad).__name__} ===")
        if isinstance(bad, str):
            print(f"  STRING: {bad[:200]}")
            if '%7B' in bad:
                print("  ⚠️ URL-ENCODED!")
        elif isinstance(bad, dict):
            print(f"  firstPlace={bad.get('firstPlace')}, param_count={len(bad.get('param',[]))}")
        elif isinstance(bad, list):
            print(f"  array[{len(bad)}]")
        
        # entDomicileDto
        dto = bd.get('entDomicileDto', {})
        if dto:
            print(f"\n=== entDomicileDto ({len(dto)} keys) ===")
            for k,v in sorted(dto.items()):
                if v is not None and v != '':
                    print(f"  {k}: {v}")
    else:
        print(f"  body parse failed: {body[:300]}")
else:
    print("  无body捕获")

ws.close()
print("\n✅ body已抓取，未提交到服务端")
