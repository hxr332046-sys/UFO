#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""精确处理行业类型[I]选项 + 经营范围iframe + 填写所有字段"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# Step 1: 获取行业类型tne-select组件的完整选项列表
print("\nStep 1: 获取行业类型完整选项")
industry_opts = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            var opts=comp.options||[];
            var result=[];
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                var item={idx:j,label:o.label?.substring(0,60)||'',value:o.value||'',hasChildren:!!o.children};
                if(o.children){
                    item.childCount=o.children.length;
                    item.childSample=o.children.slice(0,5).map(function(c){return{label:c.label?.substring(0,40)||'',value:c.value||''}});
                }
                result.push(item);
            }
            return{total:opts.length,options:result};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  total: {industry_opts.get('total',0) if industry_opts else 0}")
for opt in (industry_opts.get('options',[]) or []):
    has_i = '[I]' in opt.get('label','')
    marker = ' ✅' if has_i else ''
    print(f"  [{opt.get('idx')}] val={opt.get('value','')} children={opt.get('hasChildren',False)}({opt.get('childCount',0)}) label={opt.get('label','')[:50]}{marker}")
    if has_i or opt.get('hasChildren'):
        for child in opt.get('childSample',[]):
            c_marker = ' ✅' if '软件' in child.get('label','') or '信息' in child.get('label','') else ''
            print(f"    child: val={child.get('value','')} label={child.get('label','')[:40]}{c_marker}")

# Step 2: 选择[I]信息传输选项
print("\nStep 2: 选择行业类型[I]选项")
# 找到包含[I]的选项，通过Vue组件方法选择
industry_result = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            var opts=comp.options||[];
            
            // 找包含[I]的选项
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                if(o.label&&o.label.includes('[I]')){
                    // 如果有子选项，找软件相关的
                    if(o.children&&o.children.length>0){
                        for(var k=0;k<o.children.length;k++){
                            var c=o.children[k];
                            if(c.label&&(c.label.includes('软件')||c.label.includes('信息技术'))){
                                // 选择子选项
                                comp.handleOptionSelect(c);
                                return{selected:'child:'+c.label?.substring(0,40),value:c.value||''};
                            }
                        }
                        // 没有匹配的子选项，选第一个
                        comp.handleOptionSelect(o.children[0]);
                        return{selected:'child:first',value:o.children[0].value||'',label:o.children[0].label?.substring(0,40)||''};
                    }
                    // 没有子选项，直接选择
                    comp.handleOptionSelect(o);
                    return{selected:'parent:'+o.label?.substring(0,40),value:o.value||''};
                }
            }
            
            // 如果没找到[I]，遍历所有选项找信息传输
            for(var j=0;j<opts.length;j++){
                var o=opts[j];
                if(o.children){
                    for(var k=0;k<o.children.length;k++){
                        var c=o.children[k];
                        if(c.label&&(c.label.includes('信息传输')||c.label.includes('软件'))){
                            comp.handleOptionSelect(c);
                            return{selected:'deep:'+c.label?.substring(0,40),value:c.value||''};
                        }
                    }
                }
            }
            return{error:'no_I_option'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  industry_result: {industry_result}")
time.sleep(2)

# Step 3: 填写businessDataInfo字段
print("\nStep 3: 填写businessDataInfo")
fill = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var bdi=vm.$data.businessDataInfo;
            var inst=vm;
            // 基本字段
            inst.$set(bdi,'name','广西智信数据科技有限公司');
            inst.$set(bdi,'telephone','13800138000');
            inst.$set(bdi,'postcode','530022');
            inst.$set(bdi,'email','test@example.com');
            inst.$set(bdi,'registerCapital','100');
            inst.$set(bdi,'detailAddr','民族大道100号');
            inst.$set(bdi,'proDetailAddr','民族大道100号');
            inst.$set(bdi,'bpBusinessAddress','民族大道100号');
            inst.$set(bdi,'shouldInvestWay','1');
            inst.$set(bdi,'investMoney','100');
            inst.$set(bdi,'conGroUSD','0');
            inst.$set(bdi,'regCapRMB','100');
            inst.$set(bdi,'subCapital','0');
            inst.$set(bdi,'fisRegionCode','450103');
            inst.$set(bdi,'businessPremises','自有');
            
            // flowData中的字段
            if(bdi.flowData){
                inst.$set(bdi.flowData,'entName','广西智信数据科技有限公司');
                inst.$set(bdi.flowData,'regCap','100');
                inst.$set(bdi.flowData,'empNum','5');
                inst.$set(bdi.flowData,'licCopyNum','1');
                inst.$set(bdi.flowData,'tel','13800138000');
                inst.$set(bdi.flowData,'postalCode','530022');
                inst.$set(bdi.flowData,'detailAddr','民族大道100号');
                inst.$set(bdi.flowData,'proDetailAddr','民族大道100号');
                inst.$set(bdi.flowData,'setUpMode','1');
                inst.$set(bdi.flowData,'accountMethod','1');
                inst.$set(bdi.flowData,'operTermType','1');
                inst.$set(bdi.flowData,'isNeedPaperLic','0');
                inst.$set(bdi.flowData,'isFreeTrade','0');
            }
            
            inst.$forceUpdate();
            return{filled:true,flowDataKeys:bdi.flowData?Object.keys(bdi.flowData).slice(0,20):[]};
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  fill: {fill}")

# 同步DOM输入
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input.el-input__inner');
        if(!input||!input.offsetParent||input.disabled)continue;
        var val='';
        if(label.includes('注册资本'))val='100';
        else if(label.includes('从业人数'))val='5';
        else if(label.includes('执照副本'))val='1';
        else if(label.includes('联系电话'))val='13800138000';
        else if(label.includes('邮政编码'))val='530022';
        else if(label.includes('详细地址')&&!label.includes('生产经营'))val='民族大道100号';
        else if(label.includes('生产经营地详细'))val='民族大道100号';
        if(val){s.call(input,val);input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")
time.sleep(1)

# 勾选radio
ev("""(function(){
    var radios=document.querySelectorAll('.el-radio__input:not(.is-checked)');
    var groups={};
    for(var i=0;i<radios.length;i++){
        var parent=radios[i].closest('.el-form-item');
        var label=parent?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(!groups[label]){groups[label]=true;radios[i].click()}
    }
})()""")
time.sleep(1)

# Step 4: 处理经营范围iframe
print("\nStep 4: 经营范围iframe")
# 先点击添加规范经营用语按钮
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(3)

# 通过CDP获取iframe列表
iframe_info = ev("""(function(){
    var iframes=document.querySelectorAll('iframe');
    var r=[];
    for(var i=0;i<iframes.length;i++){
        r.push({idx:i,src:iframes[i].src||'',id:iframes[i].id||'',name:iframes[i].name||'',visible:iframes[i].offsetParent!==null});
    }
    return r;
})()""")
print(f"  iframes: {iframe_info}")

# 尝试访问iframe内容
for iframe in (iframe_info or []):
    if iframe.get('visible') and 'core.html' in iframe.get('src',''):
        print(f"  尝试访问iframe #{iframe.get('idx')}")
        iframe_content = ev("""(function(){
            var iframes=document.querySelectorAll('iframe');
            for(var i=0;i<iframes.length;i++){
                try{
                    var doc=iframes[i].contentDocument;
                    if(doc&&doc.body){
                        // 等待iframe加载
                        var text=doc.body.textContent?.trim()?.substring(0,100)||'';
                        var inputs=doc.querySelectorAll('input');
                        var btns=doc.querySelectorAll('button');
                        var trees=doc.querySelectorAll('.el-tree,[class*="tree"]');
                        var selects=doc.querySelectorAll('select,.el-select');
                        var allEls=doc.querySelectorAll('*');
                        return{accessible:true,bodyText:text,inputs:inputs.length,btns:btns.length,trees:trees.length,selects:selects.length,allEls:allEls.length,
                            htmlSample:doc.body.innerHTML?.substring(0,200)||''};
                    }
                }catch(e){return{accessible:false,error:e.message}}
            }
        })()""")
        print(f"  iframe_content: {iframe_content}")
        
        if iframe_content and iframe_content.get('accessible'):
            # iframe可能还在加载
            if iframe_content.get('allEls',0) < 5:
                print("  iframe内容少，等待加载...")
                time.sleep(5)
                iframe_content2 = ev("""(function(){
                    var iframes=document.querySelectorAll('iframe');
                    for(var i=0;i<iframes.length;i++){
                        try{
                            var doc=iframes[i].contentDocument;
                            if(doc&&doc.body){
                                return{bodyText:doc.body.textContent?.trim()?.substring(0,200)||'',
                                    inputs:doc.querySelectorAll('input').length,
                                    btns:doc.querySelectorAll('button').length,
                                    allEls:doc.querySelectorAll('*').length,
                                    htmlSample:doc.body.innerHTML?.substring(0,300)||''};
                            }
                        }catch(e){return{error:e.message}}
                    }
                })()""")
                print(f"  iframe_content2: {iframe_content2}")

# Step 5: 如果iframe无法直接操作，尝试通过CDP iframe context
print("\nStep 5: CDP iframe context")
# 获取所有iframe targets
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
iframe_targets = [t for t in targets if t.get("type") == "iframe" or t.get("type") == "other"]
print(f"  所有targets: {len(targets)} iframes={len(iframe_targets)}")
for t in iframe_targets:
    print(f"    {t.get('id','')[:20]} type={t.get('type','')} url={t.get('url','')[:60]}")

# 尝试连接iframe的WebSocket
core_iframes = [t for t in targets if 'core.html' in t.get('url','')]
if core_iframes:
    print(f"  找到core.html iframe: {core_iframes[0].get('webSocketDebuggerUrl','')[:50]}")
    try:
        iframe_ws_url = core_iframes[0]["webSocketDebuggerUrl"]
        iframe_ws = websocket.create_connection(iframe_ws_url, timeout=10)
        iframe_ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":"document.body?.innerHTML?.substring(0,300)||'empty'","returnByValue":True,"timeout":10000}}))
        r = json.loads(iframe_ws.recv())
        print(f"  iframe body: {r.get('result',{}).get('result',{}).get('value','')[:200]}")
        
        # 查找搜索框和树
        iframe_ws.send(json.dumps({"id":2,"method":"Runtime.evaluate","params":{"expression":"({inputs:document.querySelectorAll('input').length,btns:document.querySelectorAll('button').length,trees:document.querySelectorAll('.el-tree,[class*=tree]').length,allEls:document.querySelectorAll('*').length})", "returnByValue":True,"timeout":10000}}))
        r2 = json.loads(iframe_ws.recv())
        print(f"  iframe elements: {r2.get('result',{}).get('result',{}).get('value','')}")
        
        # 在iframe中搜索经营范围
        iframe_ws.send(json.dumps({"id":3,"method":"Runtime.evaluate","params":{"expression":"(function(){var inputs=document.querySelectorAll('input');for(var i=0;i<inputs.length;i++){var ph=inputs[i].placeholder||inputs[i].getAttribute('placeholder')||'';if(ph.includes('搜索')||ph.includes('查询')||ph.includes('关键字')){var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(inputs[i],'软件开发');inputs[i].dispatchEvent(new Event('input',{bubbles:true}));return{searched:true,ph:ph}}}return{searched:false,inputs:inputs.length}})()","returnByValue":True,"timeout":10000}}))
        r3 = json.loads(iframe_ws.recv())
        print(f"  iframe search: {r3.get('result',{}).get('result',{}).get('value','')}")
        time.sleep(3)
        
        # 检查搜索结果
        iframe_ws.send(json.dumps({"id":4,"method":"Runtime.evaluate","params":{"expression":"({treeNodes:document.querySelectorAll('.el-tree-node').length,checkboxes:document.querySelectorAll('.el-checkbox').length,results:document.querySelectorAll('[class*=result] li,[class*=item]').length,bodyText:document.body?.textContent?.trim()?.substring(0,200)||''})","returnByValue":True,"timeout":10000}}))
        r4 = json.loads(iframe_ws.recv())
        print(f"  iframe after search: {r4.get('result',{}).get('result',{}).get('value','')}")
        
        iframe_ws.close()
    except Exception as e:
        print(f"  iframe ws error: {e}")

# Step 6: 验证
print("\nStep 6: 验证")
bdi = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var bdi=vm.$data.businessDataInfo;
            var fd=bdi.flowData||{};
            return{
                name:bdi.name||fd.entName||'',
                telephone:bdi.telephone||fd.tel||'',
                regCap:bdi.registerCapital||fd.regCap||'',
                industryType:fd.industryType||fd.industryBigType||bdi.industryType||'',
                businessArea:fd.businessArea||bdi.businessArea||'',
                detailAddr:bdi.detailAddr||fd.detailAddr||'',
                formCount:document.querySelectorAll('.el-form-item').length
            };
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  bdi: {bdi}")

ws.close()
print("✅ 完成")
