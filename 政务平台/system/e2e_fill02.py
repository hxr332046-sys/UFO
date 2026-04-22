#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析businessDataInfo模型 → 正确填写行业类型子选项 → 经营范围对话框"""
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

# Step 1: 找到basic-info组件（可能不叫basic-info）
print("\nStep 1: 找到表单组件")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        // 检查是否有businessDataInfo
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            return{compName:vm.$options?.name||'',dataKeys:Object.keys(vm.$data).slice(0,20),
                bdiKeys:Object.keys(vm.$data.businessDataInfo).slice(0,40),
                bdiSample:JSON.stringify(vm.$data.businessDataInfo).substring(0,500),
                methods:Object.keys(vm.$options?.methods||{}).slice(0,20),
                parentName:vm.$parent?.$options?.name||''};
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findFormComp(vm.$children[i],d+1);if(r)return r;
        }
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  compName: {comp.get('compName','') if comp else 'None'}")
print(f"  bdiKeys: {comp.get('bdiKeys',[]) if comp else []}")
print(f"  bdiSample: {comp.get('bdiSample','')[:300] if comp else ''}")
print(f"  methods: {comp.get('methods',[]) if comp else []}")

if not comp:
    print("❌ 未找到businessDataInfo组件")
    ws.close(); exit()

# Step 2: 填写businessDataInfo
print("\nStep 2: 填写businessDataInfo")
bdi_keys = comp.get('bdiKeys',[])
print(f"  所有字段: {bdi_keys}")

# 分析每个字段的值
bdi_detail = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var bdi=vm.$data.businessDataInfo;
            var result={};
            for(var k in bdi){
                var v=bdi[k];
                if(v===null||v===undefined||v==='')result[k]='(empty)';
                else if(typeof v==='object')result[k]='object:'+JSON.stringify(v).substring(0,50);
                else result[k]=String(v).substring(0,50);
            }
            return result;
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  bdi_detail: {json.dumps(bdi_detail, ensure_ascii=False)[:500] if bdi_detail else 'None'}")

# Step 3: 填写简单字段
print("\nStep 3: 填写简单字段")
fill = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var bdi=vm.$data.businessDataInfo;
            var inst=vm;
            // 文本字段
            inst.$set(bdi,'entName','广西智信数据科技有限公司');
            inst.$set(bdi,'regCap','100');
            inst.$set(bdi,'empNum','5');
            inst.$set(bdi,'licCopyNum','1');
            inst.$set(bdi,'tel','13800138000');
            inst.$set(bdi,'postalCode','530022');
            inst.$set(bdi,'detailAddr','民族大道100号');
            inst.$set(bdi,'proDetailAddr','民族大道100号');
            // Radio字段
            inst.$set(bdi,'setUpMode','1');
            inst.$set(bdi,'accountMethod','1');
            inst.$set(bdi,'operTermType','1');
            inst.$set(bdi,'isNeedPaperLic','0');
            inst.$set(bdi,'isFreeTrade','0');
            inst.$forceUpdate();
            return{filled:true};
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  fill: {fill}")

# 同步DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input.el-input__inner');
        if(!input||!input.offsetParent)continue;
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

# Step 4: 处理行业类型 - 需要选择子选项
print("\nStep 4: 行业类型 - 选择子选项")
# 先点击行业类型输入框展开
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click();input.dispatchEvent(new Event('focus',{bubbles:true}))}
            return;
        }
    }
})()""")
time.sleep(2)

# 查看下拉选项
dropdown = ev("""(function(){
    var popper=document.querySelectorAll('.el-select-dropdown__item');
    var r=[];
    for(var i=0;i<popper.length;i++){
        if(popper[i].offsetParent!==null||popper[i].style?.display!=='none'){
            r.push({idx:i,text:popper[i].textContent?.trim()?.substring(0,50)||'',hasClass:popper[i].className?.includes('group')||false});
        }
    }
    return{total:popper.length,visible:r.length,items:r};
})()""")
print(f"  dropdown: total={dropdown.get('total',0)} visible={dropdown.get('visible',0)}")
for item in (dropdown.get('items',[]) or []):
    print(f"    {item.get('idx')}: {item.get('text','')} group={item.get('hasClass',False)}")

# 选择[I]信息传输选项
selected = ev("""(function(){
    var popper=document.querySelectorAll('.el-select-dropdown__item');
    for(var i=0;i<popper.length;i++){
        var t=popper[i].textContent?.trim()||'';
        if(t.includes('[I]')||t.includes('信息传输')||t.includes('软件')){
            popper[i].click();
            return{selected:t.substring(0,50),idx:i};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  selected: {selected}")
time.sleep(3)

# 如果选择了父选项，需要再选择子选项
if selected and not selected.get('error'):
    # 检查是否展开了子选项
    child_dropdown = ev("""(function(){
        var popper=document.querySelectorAll('.el-select-dropdown__item');
        var r=[];
        for(var i=0;i<popper.length;i++){
            if(popper[i].offsetParent!==null){
                r.push({idx:i,text:popper[i].textContent?.trim()?.substring(0,50)||''});
            }
        }
        return{visible:r.length,items:r.slice(0,10)};
    })()""")
    print(f"  child_dropdown: visible={child_dropdown.get('visible',0)} items={child_dropdown.get('items',[])}")
    
    # 如果有子选项，选择软件相关
    if child_dropdown.get('visible',0) > 0:
        child_selected = ev("""(function(){
            var popper=document.querySelectorAll('.el-select-dropdown__item');
            for(var i=0;i<popper.length;i++){
                var t=popper[i].textContent?.trim()||'';
                if(popper[i].offsetParent!==null&&(t.includes('软件')||t.includes('信息技术'))){
                    popper[i].click();
                    return{selected:t.substring(0,50),idx:i};
                }
            }
            // 选第一个可见子选项
            for(var i=0;i<popper.length;i++){
                if(popper[i].offsetParent!==null){
                    popper[i].click();
                    return{selected:popper[i].textContent?.trim()?.substring(0,50)||'',idx:i,fallback:true};
                }
            }
            return{error:'no_visible'};
        })()""")
        print(f"  child_selected: {child_selected}")
        time.sleep(2)

# Step 5: 处理经营范围对话框
print("\nStep 5: 经营范围对话框")
# 点击添加规范经营用语
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if(t.includes('添加')||t.includes('规范')){
                    btns[j].click();
                    return{clicked:t};
                }
            }
        }
    }
})()""")
time.sleep(3)

# 分析对话框内容（可能是iframe或自定义组件）
dialog_analysis = ev("""(function(){
    // 检查iframe
    var iframes=document.querySelectorAll('iframe');
    for(var i=0;i<iframes.length;i++){
        if(iframes[i].offsetParent!==null||iframes[i].style?.display!=='none'){
            return{type:'iframe',src:iframes[i].src||iframes[i].getAttribute('data-src')||'',id:iframes[i].id||'',name:iframes[i].name||''};
        }
    }
    // 检查tni-dialog
    var dialogs=document.querySelectorAll('.tni-dialog,[class*="custom-dialog"]');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
            var html=dialogs[i].innerHTML?.substring(0,300)||'';
            var text=dialogs[i].textContent?.trim()?.substring(0,100)||'';
            return{type:'tni-dialog',text:text,htmlSample:html.substring(0,100),className:dialogs[i].className?.substring(0,50)||''};
        }
    }
    // 检查el-dialog
    var elDialogs=document.querySelectorAll('.el-dialog__wrapper');
    for(var i=0;i<elDialogs.length;i++){
        if(elDialogs[i].offsetParent!==null||elDialogs[i].style?.display!=='none'){
            var text=elDialogs[i].textContent?.trim()?.substring(0,100)||'';
            return{type:'el-dialog',text:text};
        }
    }
    return{type:'unknown'};
})()""")
print(f"  dialog: {dialog_analysis}")

# 如果是iframe，尝试通过CDP访问
if dialog_analysis and dialog_analysis.get('type') == 'iframe':
    print("  经营范围对话框是iframe，需要CDP iframe上下文")
    # 获取iframe的URL
    iframe_src = dialog_analysis.get('src','')
    print(f"  iframe src: {iframe_src}")
    
    # 如果iframe是同源的，可以直接访问
    if iframe_src and ('icpsp' in iframe_src or 'zhjg' in iframe_src or iframe_src.startsWith('/')):
        iframe_result = ev("""(function(){
            var iframes=document.querySelectorAll('iframe');
            for(var i=0;i<iframes.length;i++){
                try{
                    var doc=iframes[i].contentDocument||iframes[i].contentWindow?.document;
                    if(doc){
                        var inputs=doc.querySelectorAll('input');
                        var btns=doc.querySelectorAll('button');
                        var trees=doc.querySelectorAll('.el-tree,[class*="tree"]');
                        return{accessible:true,inputs:inputs.length,btns:btns.length,trees:trees.length,
                            bodyText:doc.body?.textContent?.trim()?.substring(0,100)||''};
                    }
                }catch(e){
                    return{accessible:false,error:e.message};
                }
            }
        })()""")
        print(f"  iframe access: {iframe_result}")

# Step 6: 验证填写结果
print("\nStep 6: 验证填写结果")
bdi_after = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var bdi=vm.$data.businessDataInfo;
            var result={};
            for(var k in bdi){
                var v=bdi[k];
                if(v===null||v===undefined||v===''||v===0)continue;
                if(typeof v==='object')result[k]='obj:'+JSON.stringify(v).substring(0,50);
                else result[k]=String(v).substring(0,50);
            }
            return result;
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  bdi_after: {json.dumps(bdi_after, ensure_ascii=False)[:500] if bdi_after else 'None'}")

ws.close()
print("✅ 完成")
