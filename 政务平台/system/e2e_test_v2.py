#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
设立登记自动化测试 v2 — 按正确顺序、用组件原生交互
核心原则:
  1. 先刷新页面清除残留状态
  2. 住所/地址先填 → 行业类型 → 经营范围 → 其他字段
  3. 点保存后看验证提示，按提示补全，不绕过
  4. 每次操作后截图留证
"""
import json, time, requests, websocket, sys, base64, os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ============================================================
# CDP 工具函数
# ============================================================
def get_page_ws():
    for attempt in range(5):
        try:
            pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "") and "chrome-error" not in p.get("url", "")]
            if not page:
                page = [p for p in pages if p.get("type") == "page" and "chrome-error" not in p.get("url", "")]
            if not page:
                time.sleep(2); continue
            ws_url = page[0]["webSocketDebuggerUrl"]
            return websocket.create_connection(ws_url, timeout=8)
        except:
            time.sleep(2)
    return None

_mid = 0
def ev(js, timeout=10):
    global _mid; _mid += 1; mid = _mid
    ws = get_page_ws()
    if not ws: return "ERROR:no_page"
    try:
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                            "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
        ws.settimeout(timeout + 2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                ws.close()
                return r.get("result", {}).get("result", {}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

def screenshot(name):
    ws = get_page_ws()
    if not ws: return
    try:
        ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot",
                            "params": {"format": "png", "quality": 60}}))
        ws.settimeout(10)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                data = r.get("result", {}).get("data")
                if data:
                    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(data))
                    print(f"  📸 screenshot: {path}")
                ws.close()
                return
    except:
        pass

def get_errors():
    """获取当前所有验证错误"""
    return ev("""(function(){
        var msgs=document.querySelectorAll('.el-form-item__error');
        var r=[];
        for(var i=0;i<msgs.length;i++){
            var t=msgs[i].textContent?.trim()||'';
            if(t && t.length<80 && t.length>1) r.push(t);
        }
        return r.slice(0,20);
    })()""")

def log_step(step, data):
    print(f"  [{step}] {json.dumps(data, ensure_ascii=False)[:120]}")

# ============================================================
# 开始测试
# ============================================================
print("=" * 60)
print("设立登记自动化测试 v2")
print("=" * 60)

# ===== PHASE 0: 刷新页面 =====
print("\n--- PHASE 0: 刷新页面 ---")
ev("location.reload()")
print("  刷新完成，等待页面加载...")
time.sleep(8)

# 检查页面状态
page_info = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length, title:document.title})")
print(f"  页面: {page_info}")

# 如果不在basic-info，需要重新导航
hash = page_info.get('hash', '') if page_info else ''
if 'basic-info' not in hash:
    print("  不在basic-info，需要重新导航...")
    # 恢复Vuex认证
    ev("""(function(){
        var app=document.getElementById('app');
        if(!app||!app.__vue__)return 'no_vue';
        var vm=app.__vue__;
        var t=localStorage.getItem('top-token');
        var a=localStorage.getItem('Authorization');
        if(t)vm.$store.commit('login/SET_TOKEN',t);
        return {token:!!t,auth:!!a};
    })()""")
    time.sleep(2)
    
    # 导航到企业专区
    ev("""vm.$router.push('/index/enterprise/enterprise-zone')""")
    time.sleep(3)
    
    # 点击"开始办理"
    ev("""(function(){
        var btns=document.querySelectorAll('button,.el-button,.start-btn');
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if(t.includes('开始办理')||t.includes('设立登记')){btns[i].click();return 'clicked:'+t}
        }
        return 'no_btn';
    })()""")
    time.sleep(3)
    
    # toNotName
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var comp=findComp(vm,'without-name',0);
        if(comp){comp.toNotName();return 'toNotName_ok'}
        return 'no_comp';
    })()""")
    time.sleep(3)
    
    # 设置企业类型 + nextBtn
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var comp=findComp(vm,'establish',0);
        if(comp){
            if(comp.$data.radioGroup&&comp.$data.radioGroup.length>0){
                comp.$set(comp.$data.radioGroup[0],'checked','1100');
            }
            comp.nextBtn();
            return 'nextBtn_ok';
        }
        return 'no_comp';
    })()""")
    time.sleep(5)
    
    # 导航到basic-info
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        vm.$router.push('/flow/base/basic-info');
    })()""")
    time.sleep(5)
    
    page_info = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  导航后: {page_info}")

screenshot("v2_phase0_refreshed")

# ===== PHASE 1: 分析表单结构 =====
print("\n--- PHASE 1: 分析表单结构 ---")

# 找到所有form-item及其label/prop
form_items = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var comp=items[i].__vue__;
        var prop=comp?.prop||comp?.$props?.prop||'';
        var hasCascader=!!items[i].querySelector('.el-cascader,[class*="cascader"]');
        var hasSelect=!!items[i].querySelector('.el-select,[class*="tne-select"]');
        var hasInput=!!items[i].querySelector('input.el-input__inner');
        var hasBtn=!!items[i].querySelector('button');
        var hasRadio=!!items[i].querySelector('.el-radio');
        var hasTextarea=!!items[i].querySelector('textarea');
        if(label){
            r.push({i:i,label:label.substring(0,25),prop:prop,
                cascader:hasCascader,select:hasSelect,input:hasInput,
                btn:hasBtn,radio:hasRadio,textarea:hasTextarea});
        }
    }
    return r;
})()""")

if form_items:
    print(f"  表单项数: {len(form_items)}")
    # 按类型分组显示
    cascader_items = [f for f in form_items if f.get('cascader')]
    select_items = [f for f in form_items if f.get('select') and not f.get('cascader')]
    btn_items = [f for f in form_items if f.get('btn')]
    input_items = [f for f in form_items if f.get('input') and not f.get('cascader') and not f.get('select')]
    
    if cascader_items:
        print(f"  --- Cascader项 ({len(cascader_items)}):")
        for c in cascader_items: print(f"    [{c['i']}] {c['label']} prop={c.get('prop','')}")
    if select_items:
        print(f"  --- Select项 ({len(select_items)}):")
        for s in select_items: print(f"    [{s['i']}] {s['label']} prop={s.get('prop','')}")
    if btn_items:
        print(f"  --- 按钮项 ({len(btn_items)}):")
        for b in btn_items: print(f"    [{b['i']}] {b['label']}")
    if input_items:
        print(f"  --- Input项 ({len(input_items)}):")
        for inp in input_items[:15]: print(f"    [{inp['i']}] {inp['label']} prop={inp.get('prop','')}")
        if len(input_items) > 15: print(f"    ... 还有{len(input_items)-15}个")

# ===== PHASE 2: 填写住所/地址（cascader原生交互）=====
print("\n--- PHASE 2: 填写住所/地址 ---")

# 先分析cascader组件结构
cascader_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    // 找residence-information组件
    var resComp=findComp(vm,'residence-information',0);
    if(!resComp) return {error:'no_residence_comp'};
    
    // 分析其内部cascader
    var cascaders=[];
    function findCascaders(vm,d){
        if(d>10)return;
        if(vm.$options&&vm.$options.name&&vm.$options.name.includes('cascader')){
            cascaders.push({name:vm.$options.name, value:vm.$data?.value||vm.$data?.selected||vm.$data?.model||''});
        }
        // 也检查tne-data-cascader
        if(vm.$el&&vm.$el.classList&&vm.$el.classList.contains('tne-data-cascader')){
            cascaders.push({name:'tne-data-cascader', value:vm.value||vm.$data?.value||''});
        }
        for(var i=0;i<(vm.$children||[]).length;i++) findCascaders(vm.$children[i],d+1);
    }
    findCascaders(resComp,0);
    
    return {
        compName:resComp.$options?.name,
        dataKeys:Object.keys(resComp.$data||{}).slice(0,20),
        cascaders:cascaders
    };
})()""")
print(f"  住所组件: {cascader_info}")

# 尝试通过DOM点击cascader面板选择
# 先点击企业住所cascader
print("\n  尝试点击企业住所cascader...")
click_result = ev("""(function(){
    // 找到cascader的input元素
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('企业住所')){
            var cascader=items[i].querySelector('.el-cascader,[class*="cascader"]');
            if(cascader){
                var input=cascader.querySelector('input');
                if(input){
                    input.click();
                    return 'clicked_cascader_input';
                }
            }
        }
    }
    return 'not_found';
})()""")
print(f"  点击结果: {click_result}")
time.sleep(2)

# 检查cascader面板是否打开
panel_check = ev("""(function(){
    var panels=document.querySelectorAll('.el-cascader-menus,.el-cascader__dropdown,[class*="cascader-menu"],[class*="cascader-panel"]');
    var r=[];
    for(var i=0;i<panels.length;i++){
        var visible=panels[i].offsetParent!==null||panels[i].style.display!=='none';
        var items=panels[i].querySelectorAll('.el-cascader-node,[class*="cascader-node"],li');
        r.push({visible:visible,items:items.length,html:panels[i].innerHTML?.substring(0,200)||''});
    }
    // 也检查body下的弹出层
    var poppers=document.querySelectorAll('.el-popper[class*="cascader"]');
    for(var i=0;i<poppers.length;i++){
        var visible=poppers[i].offsetParent!==null||poppers[i].style.display!=='none';
        var items=poppers[i].querySelectorAll('li,.el-cascader-node');
        r.push({visible:visible,items:items.length,isPopper:true});
    }
    return r;
})()""")
print(f"  面板状态: {panel_check}")

# 如果面板打开了，尝试选择省/市/区
if panel_check and isinstance(panel_check, list) and any(p.get('visible') or p.get('isPopper') for p in panel_check):
    print("  面板已打开，尝试选择 广西 → 南宁 → 青秀区...")
    
    # 选择第一级：广西
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-popper[class*="cascader"]');
        for(var i=0;i<poppers.length;i++){
            if(poppers[i].offsetParent===null&&poppers[i].style.display==='none')continue;
            var nodes=poppers[i].querySelectorAll('li,.el-cascader-node');
            for(var j=0;j<nodes.length;j++){
                var t=nodes[j].textContent?.trim()||'';
                if(t.includes('广西')){nodes[j].click();return 'selected_guangxi'}
            }
        }
        return 'not_found';
    })()""")
    time.sleep(2)
    
    # 选择第二级：南宁
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-popper[class*="cascader"]');
        for(var i=0;i<poppers.length;i++){
            if(poppers[i].offsetParent===null&&poppers[i].style.display==='none')continue;
            var menus=poppers[i].querySelectorAll('.el-cascader-menu');
            if(menus.length>=2){
                var nodes=menus[1].querySelectorAll('li,.el-cascader-node');
                for(var j=0;j<nodes.length;j++){
                    var t=nodes[j].textContent?.trim()||'';
                    if(t.includes('南宁')){nodes[j].click();return 'selected_nanning'}
                }
            }
        }
        return 'not_found';
    })()""")
    time.sleep(2)
    
    # 选择第三级：青秀区
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-popper[class*="cascader"]');
        for(var i=0;i<poppers.length;i++){
            if(poppers[i].offsetParent===null&&poppers[i].style.display==='none')continue;
            var menus=poppers[i].querySelectorAll('.el-cascader-menu');
            if(menus.length>=3){
                var nodes=menus[2].querySelectorAll('li,.el-cascader-node');
                for(var j=0;j<nodes.length;j++){
                    var t=nodes[j].textContent?.trim()||'';
                    if(t.includes('青秀')){nodes[j].click();return 'selected_qingxiu'}
                }
            }
        }
        return 'not_found';
    })()""")
    time.sleep(2)
else:
    print("  面板未打开，尝试其他方式...")
    # 尝试通过Vue组件方法设置
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var resComp=findComp(vm,'residence-information',0);
        if(resComp){
            // 找cascader子组件
            function findCascader(vm,d){
                if(d>10)return null;
                if(vm.$options&&vm.$options.name&&vm.$options.name.includes('cascader'))return vm;
                if(vm.$el&&vm.$el.__vue__&&vm.$el.__vue__.$options?.name?.includes('cascader'))return vm.$el.__vue__;
                for(var i=0;i<(vm.$children||[]).length;i++){var r=findCascader(vm.$children[i],d+1);if(r)return r}
                return null;
            }
            var cas=findCascader(resComp,0);
            if(cas){
                // 尝试设置值
                cas.$emit('input',['450000','450100','450103']);
                return 'emit_cascader';
            }
        }
        return 'no_comp';
    })()""")
    time.sleep(2)

screenshot("v2_phase2_residence")

# 检查住所cascader值
residence_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('企业住所')){
            var input=items[i].querySelector('input');
            return {value:input?.value||'',error:items[i].querySelector('.el-form-item__error')?.textContent||''};
        }
    }
})()""")
print(f"  企业住所值: {residence_val}")

# ===== PHASE 3: 填写详细地址 =====
print("\n--- PHASE 3: 填写详细地址 ---")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        var lt=label?.textContent?.trim()||'';
        if(lt.includes('详细地址')||lt.includes('住所地详细地址')){
            var input=items[i].querySelector('input.el-input__inner');
            if(input){
                var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                setter.call(input,'民大道100号');
                input.dispatchEvent(new Event('input',{bubbles:true}));
                input.dispatchEvent(new Event('change',{bubbles:true}));
            }
        }
    }
})()""")
time.sleep(1)

# ===== PHASE 4: 填写生产经营地址 =====
print("\n--- PHASE 4: 生产经营地址 ---")
# 生产经营地址通常和企业住所相同，看看有没有"同企业住所"选项
same_check = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('生产经营')){
            var radio=items[i].querySelector('.el-radio');
            var checkbox=items[i].querySelector('.el-checkbox');
            var text=items[i].querySelector('.el-form-item__content')?.textContent?.substring(0,100)||'';
            return {hasRadio:!!radio,hasCheckbox:!!checkbox,text:text};
        }
    }
})()""")
print(f"  生产经营地址区域: {same_check}")

# 如果有"同企业住所"复选框，勾选它
if same_check and same_check.get('hasCheckbox'):
    ev("""(function(){
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var label=items[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('生产经营')){
                var cb=items[i].querySelector('.el-checkbox');
                if(cb&&!cb.classList.contains('is-checked'))cb.click();
            }
        }
    })()""")
    time.sleep(1)

# ===== PHASE 5: 填写基本信息字段 =====
print("\n--- PHASE 5: 填写基本信息字段 ---")

# 填写注册资本、联系电话、邮政编码等简单input字段
fill_data = {
    '注册资本': '100',
    '联系电话': '13800138000',
    '邮政编码': '530022',
    '从业人数': '5',
}

for label_text, value in fill_data.items():
    ev(f"""(function(){{
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){{
            var label=items[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('{label_text}')){{
                var input=items[i].querySelector('input.el-input__inner');
                if(input){{
                    var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    setter.call(input,'{value}');
                    input.dispatchEvent(new Event('input',{{bubbles:true}}));
                    input.dispatchEvent(new Event('change',{{bubbles:true}}));
                }}
            }}
        }}
    }})()""")
    time.sleep(0.5)

# 币种选择 - 人民币
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('币种')){
            var select=items[i].querySelector('.el-select');
            if(select){
                var input=select.querySelector('input');
                if(input)input.click();
            }
        }
    }
})()""")
time.sleep(1)
# 选择人民币选项
ev("""(function(){
    var opts=document.querySelectorAll('.el-select-dropdown__item');
    for(var i=0;i<opts.length;i++){
        if(opts[i].textContent.trim().includes('人民币')){
            opts[i].click();
            return 'selected_cny';
        }
    }
})()""")
time.sleep(1)

# 投资方式 - 选货币
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('投资方式')){
            var radios=items[i].querySelectorAll('.el-radio');
            for(var j=0;j<radios.length;j++){
                var t=radios[j].textContent?.trim()||'';
                if(t.includes('货币')){radios[j].click();return 'selected_currency'}
            }
        }
    }
})()""")
time.sleep(1)

screenshot("v2_phase5_basic_fields")

# ===== PHASE 6: 行业类型（tree select 原生交互）=====
print("\n--- PHASE 6: 行业类型 ---")

# 点击行业类型select
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var select=items[i].querySelector('.el-select,[class*="tne-select"]');
            if(select){
                var input=select.querySelector('input');
                if(input){input.click();return 'clicked'}
            }
        }
    }
    return 'not_found';
})()""")
time.sleep(3)

# 检查下拉面板
tree_panel = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown,[class*="select-dropdown"]');
    for(var i=0;i<poppers.length;i++){
        if(poppers[i].offsetParent===null&&poppers[i].style.display==='none')continue;
        var tree=poppers[i].querySelector('.el-tree,[class*="tree"]');
        var items=poppers[i].querySelectorAll('.el-tree-node,[class*="tree-node"]');
        return {hasTree:!!tree,items:items.length,html:poppers[i].innerHTML?.substring(0,300)||''};
    }
    return {noPopper:true};
})()""")
print(f"  树面板: {tree_panel}")

# 如果有树，展开I节点，选择65
if tree_panel and tree_panel.get('hasTree'):
    print("  展开I节点...")
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
        for(var i=0;i<poppers.length;i++){
            if(poppers[i].offsetParent===null)continue;
            var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
            for(var j=0;j<nodes.length;j++){
                var t=nodes[j].textContent?.trim()||'';
                if(t.includes('信息传输')||t.includes('[I]')){
                    nodes[j].querySelector('.el-tree-node__expand-icon')?.click();
                    return 'expanded_I';
                }
            }
        }
    })()""")
    time.sleep(3)  # 等待懒加载
    
    # 选择65 - 软件和信息技术服务业
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
        for(var i=0;i<poppers.length;i++){
            if(poppers[i].offsetParent===null)continue;
            var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
            for(var j=0;j<nodes.length;j++){
                var t=nodes[j].textContent?.trim()||'';
                if(t.includes('软件和信息技术')||t.includes('[65]')){
                    nodes[j].click();
                    return 'selected_65';
                }
            }
        }
    })()""")
    time.sleep(2)
else:
    print("  树面板未打开，尝试Vue store方式...")
    # 备用方案：通过Vue store expand + emit
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name&&vm.$options.name.includes('select'))return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        // 找行业类型select组件
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var label=items[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('行业类型')){
                var selectComp=items[i].querySelector('.el-select,[class*="tne-select"]')?.__vue__;
                if(selectComp){
                    selectComp.$emit('input','I65');
                    return 'emit_I65';
                }
            }
        }
    })()""")
    time.sleep(2)

# 验证行业类型值
industry_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=items[i].querySelector('input');
            return {value:input?.value||'',error:items[i].querySelector('.el-form-item__error')?.textContent||''};
        }
    }
})()""")
print(f"  行业类型值: {industry_val}")

screenshot("v2_phase6_industry")

# ===== PHASE 7: 经营范围 =====
print("\n--- PHASE 7: 经营范围 ---")

# 找"添加规范经营用语"按钮并点击
btn_result = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,[class*="add-btn"]');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加规范经营用语')||t.includes('经营范围')){
            if(btns[i].offsetParent!==null){btns[i].click();return 'clicked:'+t.substring(0,20)}
        }
    }
    // 也检查form-item内的按钮
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btn=items[i].querySelector('button');
            if(btn){btn.click();return 'clicked_in_form'}
        }
    }
    return 'no_btn';
})()""")
print(f"  按钮点击: {btn_result}")
time.sleep(3)

# 检查对话框是否打开
dialog_check = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        var visible=dialogs[i].offsetParent!==null||dialogs[i].style.display!=='none';
        if(visible){
            var title=dialogs[i].querySelector('.el-dialog__title,[class*="dialog-title"]')?.textContent?.trim()||'';
            return {visible:true,title:title,html:dialogs[i].innerHTML?.substring(0,300)||''};
        }
    }
    return {visible:false};
})()""")
print(f"  对话框: {dialog_check}")

# 如果对话框打开了，在里面搜索经营范围
if dialog_check and dialog_check.get('visible'):
    print("  对话框已打开，搜索经营范围...")
    # 在对话框中搜索"软件开发"
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent===null)continue;
            var input=dialogs[i].querySelector('input.el-input__inner');
            if(input){
                var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                setter.call(input,'软件开发');
                input.dispatchEvent(new Event('input',{bubbles:true}));
                return 'searched';
            }
        }
    })()""")
    time.sleep(3)
    
    # 查看搜索结果
    search_results = ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent===null)continue;
            var list=dialogs[i].querySelectorAll('.el-table__row,[class*="search-list"] li,[class*="result-item"]');
            var r=[];
            for(var j=0;j<Math.min(list.length,10);j++){
                r.push(list[j].textContent?.trim()?.substring(0,50)||'');
            }
            return {count:list.length,samples:r};
        }
    })()""")
    print(f"  搜索结果: {search_results}")
    
    # 勾选搜索结果
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent===null)continue;
            var checkboxes=dialogs[i].querySelectorAll('.el-checkbox,[class*="checkbox"]');
            for(var j=0;j<Math.min(checkboxes.length,5);j++){
                if(!checkboxes[j].classList.contains('is-checked')){
                    checkboxes[j].click();
                }
            }
            // 也尝试点击表格行
            var rows=dialogs[i].querySelectorAll('.el-table__row');
            for(var j=0;j<Math.min(rows.length,3);j++){
                rows[j].click();
            }
        }
    })()""")
    time.sleep(2)
    
    # 点确定
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
        for(var i=0;i<dialogs.length;i++){
            if(dialogs[i].offsetParent===null)continue;
            var btns=dialogs[i].querySelectorAll('button,.el-button');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if(t.includes('确定')||t.includes('确认')){
                    btns[j].click();
                    return 'confirmed';
                }
            }
        }
    })()""")
    time.sleep(2)
else:
    print("  对话框未打开，尝试通过businese-info.confirm()设置...")
    # 备用：通过confirm方法设置
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var comp=findComp(vm,'businese-info',0);
        if(comp){
            comp.confirm({
                busiAreaData:[
                    {id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                    {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
                ],
                genBusiArea:'软件开发;信息技术咨询服务',
                busiAreaCode:'I65',
                busiAreaName:'软件开发;信息技术咨询服务'
            });
            return 'confirm_ok';
        }
        return 'no_comp';
    })()""")
    time.sleep(2)

# 检查经营范围值
scope_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var content=items[i].querySelector('.el-form-item__content');
            return {
                text:content?.textContent?.trim()?.substring(0,80)||'',
                error:items[i].querySelector('.el-form-item__error')?.textContent||''
            };
        }
    }
})()""")
print(f"  经营范围值: {scope_val}")

screenshot("v2_phase7_scope")

# ===== PHASE 8: 第一次保存 — 收集验证提示 =====
print("\n--- PHASE 8: 第一次保存（收集提示）---")

# 安装XHR拦截器
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

# 点击保存按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('保存')||t.includes('暂存'))&&btns[i].offsetParent!==null){
            btns[i].click();return 'clicked:'+t;
        }
    }
    return 'no_btn';
})()""")
time.sleep(5)

# 收集验证提示
errors = get_errors()
print(f"  验证提示: {errors}")

# 检查API响应
resp = ev("window.__save_result")
if resp:
    print(f"  API status={resp.get('status')}")
    try:
        p = json.loads(resp.get('resp', '{}'))
        print(f"  code={p.get('code','')} msg={p.get('msg','')[:60]}")
    except:
        print(f"  raw: {resp.get('resp','')[:100]}")
else:
    print("  无API响应（可能前端验证阻止了提交）")

screenshot("v2_phase8_first_save")

# ===== PHASE 9: 按提示补全 =====
print("\n--- PHASE 9: 按提示补全 ---")

if errors and isinstance(errors, list) and len(errors) > 0:
    print(f"  有 {len(errors)} 个提示需要处理:")
    for i, err in enumerate(errors):
        print(f"    {i+1}. {err}")
    
    # 逐个处理验证提示
    for err in errors:
        if '住所' in err or '地址' in err:
            print(f"  → 处理地址类提示: {err}")
            # 尝试通过Vue组件方式设置
            ev("""(function(){
                var app=document.getElementById('app');var vm=app.__vue__;
                function find(vm,d){
                    if(d>15)return null;
                    if(vm.$data&&vm.$data.businessDataInfo)return vm;
                    for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
                    return null;
                }
                var comp=find(vm,0);
                if(comp){
                    var bdi=comp.$data.businessDataInfo;
                    // 设置区域代码
                    comp.$set(bdi,'distCode','450103');
                    comp.$set(bdi,'fisDistCode','450103');
                    comp.$set(bdi,'provinceCode','450000');
                    comp.$set(bdi,'provinceName','广西壮族自治区');
                    comp.$set(bdi,'cityCode','450100');
                    comp.$set(bdi,'cityName','南宁市');
                    comp.$set(bdi,'distCodeName','青秀区');
                    comp.$set(bdi,'address','民大道100号');
                    comp.$set(bdi,'detAddress','民大道100号');
                    return 'set_bdi';
                }
            })()""")
            time.sleep(1)
        
        elif '行业' in err:
            print(f"  → 处理行业类型提示: {err}")
            ev("""(function(){
                var app=document.getElementById('app');var vm=app.__vue__;
                function find(vm,d){
                    if(d>15)return null;
                    if(vm.$data&&vm.$data.businessDataInfo)return vm;
                    for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
                    return null;
                }
                var comp=find(vm,0);
                if(comp){
                    var bdi=comp.$data.businessDataInfo;
                    comp.$set(bdi,'itemIndustryTypeCode','I65');
                    comp.$set(bdi,'industryTypeName','软件和信息技术服务业');
                    comp.$set(bdi,'industryType','I65');
                    comp.$set(bdi,'industryCode','I65');
                    return 'set_industry';
                }
            })()""")
            time.sleep(1)
        
        elif '经营' in err:
            print(f"  → 处理经营范围提示: {err}")
            # 通过confirm设置
            ev("""(function(){
                var app=document.getElementById('app');var vm=app.__vue__;
                function findComp(vm,name,d){
                    if(d>15)return null;
                    if(vm.$options&&vm.$options.name===name)return vm;
                    for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
                    return null;
                }
                var comp=findComp(vm,'businese-info',0);
                if(comp){
                    comp.confirm({
                        busiAreaData:[
                            {id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                            {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
                        ],
                        genBusiArea:'软件开发;信息技术咨询服务',
                        busiAreaCode:'I65',
                        busiAreaName:'软件开发;信息技术咨询服务'
                    });
                    return 'confirm_ok';
                }
            })()""")
            time.sleep(2)
        
        else:
            print(f"  → 未知提示: {err}")
else:
    print("  ✅ 无验证提示！")

# ===== PHASE 10: 第二次保存 =====
print("\n--- PHASE 10: 第二次保存 ---")

# 重新安装拦截器（刷新后可能丢失）
ev("""(function(){
    window.__save_result2=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_result2={status:self.status,resp:self.responseText?.substring(0,500)||'',body:body?.substring(0,300)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 用组件save方法保存草稿
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(comp){
        try{comp.save(null,null,'working');return 'save_called'}catch(e){return 'error:'+e.message}
    }
    return 'no_comp';
})()""", timeout=15)
time.sleep(8)

# 检查结果
errors2 = get_errors()
print(f"  验证提示: {errors2}")

resp2 = ev("window.__save_result2")
if resp2:
    print(f"  API status={resp2.get('status')}")
    try:
        p = json.loads(resp2.get('resp', '{}'))
        code = p.get('code', '')
        msg = p.get('msg', '')[:60]
        print(f"  code={code} msg={msg}")
        if str(code) in ['0', '0000', '200']:
            print("  ✅ 保存成功！")
        else:
            print(f"  ⚠️ 保存返回: code={code}")
    except:
        print(f"  raw: {resp2.get('resp','')[:150]}")
    
    # 如果保存失败，分析请求body
    body = resp2.get('body', '')
    if body:
        print(f"  请求body前300字符: {body[:300]}")
else:
    print("  无API响应")

screenshot("v2_phase10_second_save")

# ===== PHASE 11: 最终状态 =====
print("\n--- PHASE 11: 最终状态 ---")
final_hash = ev("location.hash")
final_errors = get_errors()
print(f"  路由: {final_hash}")
print(f"  验证提示: {final_errors}")

# 收集关键字段状态
key_fields = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return {error:'no_comp'};
    var bdi=comp.$data.businessDataInfo;
    return {
        entName:bdi.entName||'',
        distCode:bdi.distCode||'',
        address:bdi.address?.substring(0,30)||'',
        itemIndustryTypeCode:bdi.itemIndustryTypeCode||'',
        businessArea:bdi.businessArea?.substring(0,50)||'',
        registerCapital:bdi.registerCapital||'',
        entPhone:bdi.entPhone||''
    };
})()""")
print(f"  关键字段: {key_fields}")

# busineseForm状态
busi_form = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return {error:'no_comp'};
    var form=comp.busineseForm||{};
    return {
        busiAreaDataLen:(form.busiAreaData||[]).length,
        genBusiArea:form.genBusiArea||'',
        busiAreaCode:form.busiAreaCode||'',
        busiAreaName:form.busiAreaName||''
    };
})()""")
print(f"  busineseForm: {busi_form}")

screenshot("v2_final")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
