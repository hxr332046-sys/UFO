#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复经营期限+经营范围 → 保存 → 遍历步骤"""
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

# Step 1: 分析经营期限的form-item和radio组件
print("\nStep 1: 经营期限分析")
period_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营期限')){
            var comp=items[i].__vue__;
            var prop=comp?.prop||'';
            var radios=items[i].querySelectorAll('.el-radio');
            var radioInfo=[];
            for(var j=0;j<radios.length;j++){
                var rComp=radios[j].__vue__;
                radioInfo.push({idx:j,label:rComp?.$props?.label||rComp?.$attrs?.label||'',value:rComp?.$props?.value||rComp?.$attrs?.value||'',text:radios[j].textContent?.trim()?.substring(0,20)||''});
            }
            // 找el-radio-group
            var group=items[i].querySelector('.el-radio-group');
            var groupComp=group?.__vue__;
            var groupValue=groupComp?.value||groupComp?.$attrs?.value||'';
            return{prop:prop,groupValue:groupValue,groupCompName:groupComp?.$options?.name||'',radios:radioInfo};
        }
    }
})()""")
print(f"  period_info: {period_info}")

# Step 2: 设置经营期限radio-group值
print("\nStep 2: 设置经营期限")
if period_info:
    prop = period_info.get('prop','')
    # 找到"长期"对应的value
    radios = period_info.get('radios',[])
    long_term_val = '1'  # 默认
    for r in radios:
        if '长期' in r.get('text','') or '长期' in r.get('label',''):
            long_term_val = r.get('value','1') or r.get('label','1')
            break
    
    print(f"  prop={prop} long_term_val={long_term_val}")
    
    # 设置radio-group
    ev(f"""(function(){{
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){{
            var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
            if(label.includes('经营期限')){{
                // 设置radio-group
                var group=items[i].querySelector('.el-radio-group');
                var comp=group?.__vue__;
                if(comp){{
                    comp.$emit('input','{long_term_val}');
                    comp.$emit('change','{long_term_val}');
                    comp.value='{long_term_val}';
                }}
                // 点击长期radio
                var radios=items[i].querySelectorAll('.el-radio');
                for(var j=0;j<radios.length;j++){{
                    var text=radios[j].textContent?.trim()||'';
                    if(text.includes('长期')){{
                        var input=radios[j].querySelector('.el-radio__input');
                        if(input&&!input.classList.contains('is-checked'))input.click();
                    }}
                }}
                // 设置el-form model
                var formComp=null;
                var current=items[i].__vue__;
                for(var d=0;d<10&&current;d++){{
                    if(current.$options?.name==='ElForm'&&current.model){{
                        formComp=current;break;
                    }}
                    current=current.$parent;
                }}
                if(formComp&&formComp.model){{
                    formComp.$set(formComp.model,'{prop}','{long_term_val}');
                    formComp.$set(formComp.model,'busiPeriod','{long_term_val}');
                }}
            }}
        }}
    }})()""")
    time.sleep(2)

# Step 3: 经营范围 - 分析按钮和对话框流程
print("\nStep 3: 经营范围分析")
scope_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var comp=items[i].__vue__;
            var prop=comp?.prop||'';
            var btns=items[i].querySelectorAll('button');
            var btnInfo=[];
            for(var j=0;j<btns.length;j++){
                var bComp=btns[j].__vue__;
                btnInfo.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,20)||'',click:typeof bComp?.handleClick==='function'});
            }
            // 检查是否有textarea
            var textarea=items[i].querySelector('textarea');
            var input=items[i].querySelector('input');
            return{prop:prop,btns:btnInfo,hasTextarea:!!textarea,hasInput:!!input,
                textareaVal:textarea?.value||'',inputVal:input?.value||''};
        }
    }
})()""")
print(f"  scope_info: {scope_info}")

# Step 4: 通过iframe CDP操作经营范围对话框
print("\nStep 4: 经营范围iframe操作")
# 点击添加按钮
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')){
                    btns[j].click();
                    return;
                }
            }
        }
    }
})()""")
time.sleep(5)

# 连接iframe CDP
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
core_targets = [t for t in targets if 'core.html' in t.get('url','')]

if core_targets:
    iframe_ws_url = core_targets[0]["webSocketDebuggerUrl"]
    iframe_ws = websocket.create_connection(iframe_ws_url, timeout=15)
    iframe_mid = 0
    
    def ev_iframe(js):
        global iframe_mid; iframe_mid += 1; mid = iframe_mid
        iframe_ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
        for _ in range(30):
            try:
                iframe_ws.settimeout(15); r = json.loads(iframe_ws.recv())
                if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
            except: return None
        return None
    
    # 等待对话框加载
    for attempt in range(8):
        state = ev_iframe("""(function(){
            var wrappers=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<wrappers.length;i++){
                var title=wrappers[i].querySelector('.el-dialog__header');
                if(title?.textContent?.includes('经营范围选择')){
                    var display=getComputedStyle(wrappers[i]).display;
                    var body=wrappers[i].querySelector('.el-dialog__body');
                    var trees=body?body.querySelectorAll('.el-tree').length:0;
                    var inputs=body?body.querySelectorAll('input').length:0;
                    var allEls=body?body.querySelectorAll('*').length:0;
                    return{display:display,trees:trees,inputs:inputs,allEls:allEls,
                        bodyText:body?body.textContent?.trim()?.substring(0,60):''};
                }
            }
            return{notFound:true};
        })()""")
        print(f"  attempt {attempt}: display={state.get('display','')} trees={state.get('trees',0)} inputs={state.get('inputs',0)} allEls={state.get('allEls',0)}")
        
        if state and state.get('display') != 'none' and state.get('allEls',0) > 20:
            break
        time.sleep(2)
    
    # 如果对话框display:none，强制打开
    if state and state.get('display') == 'none':
        print("  强制打开对话框")
        ev_iframe("""(function(){
            var wrappers=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<wrappers.length;i++){
                var title=wrappers[i].querySelector('.el-dialog__header');
                if(title?.textContent?.includes('经营范围选择')){
                    wrappers[i].style.display='block';
                    var dialog=wrappers[i].querySelector('.el-dialog');
                    if(dialog){
                        dialog.style.display='block';
                        dialog.style.marginTop='15vh';
                    }
                    var vml=dialog?.__vue__;
                    if(vml){
                        vml.$emit('open');
                    }
                    return{forced:true};
                }
            }
        })()""")
        time.sleep(3)
    
    # 详细分析对话框内容
    dialog_content = ev_iframe("""(function(){
        var wrappers=document.querySelectorAll('.el-dialog__wrapper');
        for(var i=0;i<wrappers.length;i++){
            var title=wrappers[i].querySelector('.el-dialog__header');
            if(title?.textContent?.includes('经营范围选择')){
                var body=wrappers[i].querySelector('.el-dialog__body');
                if(!body)return{error:'no_body'};
                var html=body.innerHTML||'';
                // 找所有子元素
                var children=[];
                function walk(el,depth){
                    if(depth>3)return;
                    children.push({tag:el.tagName,class:el.className?.toString()?.substring(0,30)||'',text:el.childNodes?.length===1&&el.childNodes[0].nodeType===3?el.textContent?.trim()?.substring(0,30):''});
                    for(var c=0;c<el.children.length;c++){
                        walk(el.children[c],depth+1);
                    }
                }
                walk(body,0);
                return{childCount:children.length,children:children.slice(0,30),htmlLen:html.length,htmlSample:html.substring(0,300)};
            }
        }
    })()""")
    print(f"  dialog_content: childCount={dialog_content.get('childCount',0) if dialog_content else 0}")
    if dialog_content:
        for c in (dialog_content.get('children',[]) or []):
            if c.get('text'):
                print(f"    {c.get('tag')} class={c.get('class','')[:20]} text={c.get('text','')[:25]}")
        print(f"  htmlSample: {dialog_content.get('htmlSample','')[:150]}")
    
    # 如果对话框body有内容，操作
    if dialog_content and dialog_content.get('childCount',0) > 5:
        # 搜索
        ev_iframe("""(function(){
            var wrappers=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<wrappers.length;i++){
                var title=wrappers[i].querySelector('.el-dialog__header');
                if(title?.textContent?.includes('经营范围选择')){
                    var body=wrappers[i].querySelector('.el-dialog__body');
                    var inputs=body.querySelectorAll('input');
                    for(var j=0;j<inputs.length;j++){
                        var ph=inputs[j].placeholder||'';
                        if(ph.includes('查询')||ph.includes('搜索')||ph.includes('关键字')){
                            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                            s.call(inputs[j],'软件开发');
                            inputs[j].dispatchEvent(new Event('input',{bubbles:true}));
                            return{searched:true,ph:ph};
                        }
                    }
                    return{searched:false,inputs:inputs.length};
                }
            }
        })()""")
        time.sleep(3)
        
        # 查看搜索结果
        search_result = ev_iframe("""(function(){
            var wrappers=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<wrappers.length;i++){
                var title=wrappers[i].querySelector('.el-dialog__header');
                if(title?.textContent?.includes('经营范围选择')){
                    var body=wrappers[i].querySelector('.el-dialog__body');
                    var trees=body.querySelectorAll('.el-tree');
                    var nodes=body.querySelectorAll('.el-tree-node__content');
                    var checkboxes=body.querySelectorAll('.el-checkbox__input:not(.is-checked)');
                    var listItems=body.querySelectorAll('[class*="item"]');
                    var nodeTexts=[];
                    for(var n=0;n<Math.min(nodes.length,10);n++){
                        nodeTexts.push(nodes[n].textContent?.trim()?.substring(0,30)||'');
                    }
                    return{trees:trees.length,nodes:nodes.length,checkboxes:checkboxes.length,listItems:listItems.length,nodeTexts:nodeTexts};
                }
            }
        })()""")
        print(f"  search_result: {search_result}")
        
        # 选择节点
        if search_result and search_result.get('checkboxes',0) > 0:
            ev_iframe("""(function(){
                var wrappers=document.querySelectorAll('.el-dialog__wrapper');
                for(var i=0;i<wrappers.length;i++){
                    var title=wrappers[i].querySelector('.el-dialog__header');
                    if(title?.textContent?.includes('经营范围选择')){
                        var body=wrappers[i].querySelector('.el-dialog__body');
                        var checkboxes=body.querySelectorAll('.el-checkbox__input:not(.is-checked)');
                        for(var c=0;c<Math.min(checkboxes.length,3);c++){
                            checkboxes[c].click();
                        }
                        return{clicked:Math.min(checkboxes.length,3)};
                    }
                }
            })()""")
            time.sleep(1)
        elif search_result and search_result.get('nodes',0) > 0:
            # 点击包含"软件"的节点
            ev_iframe("""(function(){
                var wrappers=document.querySelectorAll('.el-dialog__wrapper');
                for(var i=0;i<wrappers.length;i++){
                    var title=wrappers[i].querySelector('.el-dialog__header');
                    if(title?.textContent?.includes('经营范围选择')){
                        var body=wrappers[i].querySelector('.el-dialog__body');
                        var nodes=body.querySelectorAll('.el-tree-node__content');
                        for(var n=0;n<nodes.length;n++){
                            var text=nodes[n].textContent?.trim()||'';
                            if(text.includes('软件开发')||text.includes('信息技术咨询')){
                                nodes[n].click();
                                return{clicked:text.substring(0,20)};
                            }
                        }
                    }
                }
            })()""")
            time.sleep(1)
        
        # 点击确定
        ev_iframe("""(function(){
            var wrappers=document.querySelectorAll('.el-dialog__wrapper');
            for(var i=0;i<wrappers.length;i++){
                var title=wrappers[i].querySelector('.el-dialog__header');
                if(title?.textContent?.includes('经营范围选择')){
                    var footer=wrappers[i].querySelector('.el-dialog__footer');
                    if(!footer)footer=wrappers[i];
                    var btns=footer.querySelectorAll('button,.el-button');
                    for(var j=0;j<btns.length;j++){
                        var t=btns[j].textContent?.trim()||'';
                        if(t.includes('确定')||t.includes('确认')||t.includes('选择')){
                            btns[j].click();
                            return{clicked:t};
                        }
                    }
                    return{error:'no_confirm',btnCount:btns.length};
                }
            }
        })()""")
        time.sleep(2)
    
    iframe_ws.close()

# Step 5: 验证
print("\nStep 5: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors: {errors}")

# Step 6: 如果经营范围还有问题，直接设置el-form model
if errors and any('经营范围' in e for e in errors):
    print("\nStep 6: 直接设置经营范围model")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findAllForms(vm,d){
            if(d>15)return[];
            var result=[];
            if(vm.$options?.name==='ElForm'&&vm.model&&Object.keys(vm.model).length>0)result.push(vm);
            for(var i=0;i<(vm.$children||[]).length;i++)result=result.concat(findAllForms(vm.$children[i],d+1));
            return result;
        }
        var forms=findAllForms(vm,0);
        for(var f=0;f<forms.length;f++){
            var model=forms[f].model;
            if('businessArea' in model){
                forms[f].$set(model,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
                forms[f].$set(model,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
                forms[f].$set(model,'busiAreaData',[{name:'软件开发',code:'I6511'},{name:'信息技术咨询服务',code:'I6531'},{name:'数据处理和存储支持服务',code:'I6541'}]);
                forms[f].clearValidate();
                forms[f].$forceUpdate();
            }
        }
    })()""")
    time.sleep(1)

# Step 7: 保存
print("\nStep 7: 保存")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

save_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findFormComp(vm,0);
    if(comp&&typeof comp.save==='function'){
        comp.save(null,function(){},'working');
        return{called:true};
    }
    return{error:'no_save'};
})()""")
print(f"  save: {save_result}")
time.sleep(5)

# 检查API
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'getUserInfo' not in url and 'getCacheCreateTime' not in url:
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:30]}")
            except: pass

errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors after save: {errors2}")

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

ws.close()
print("✅ 完成")
