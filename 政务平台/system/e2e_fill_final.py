#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整设立登记表单自动化脚本 v1.0
已验证方法:
  - 行业类型: Vue store expand + $emit('input','I65')
  - cascader同步: selected→distCode/address
  - 经营范围: tni-business-range.searchList格式 → businese-info.confirm()
  - 保存草稿: comp.save(null,null,'working')
待验证:
  - 服务端busiAreaData格式是否通过（用searchList原始格式）
"""
import json, time, requests, websocket, sys

# ============================================================
# CDP工具函数
# ============================================================
def get_page_ws():
    for attempt in range(5):
        try:
            pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
            page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","") and "chrome-error" not in p.get("url","")]
            if not page:
                page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
            if not page:
                time.sleep(2); continue
            ws_url = page[0]["webSocketDebuggerUrl"]
            return websocket.create_connection(ws_url, timeout=8)
        except:
            time.sleep(2)
    return None

def ev(js, timeout=10):
    try:
        ws = get_page_ws()
        if not ws: return "ERROR:no_page"
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

def wait_for_form(max_wait=30):
    """等待表单加载"""
    for i in range(max_wait//3):
        r = ev("document.querySelectorAll('.el-form-item').length")
        if isinstance(r, (int, float)) and r > 5:
            return True
        time.sleep(3)
    return False

# ============================================================
# Step 0: 检查网络和页面
# ============================================================
print("=" * 60)
print("设立登记表单自动化 v1.0")
print("=" * 60)

cur = ev("({hash:location.hash,url:location.href.substring(0,80)})")
print(f"当前页面: {cur}")

if isinstance(cur, dict) and "chrome-error" in cur.get("url",""):
    print("⚠️ 页面网络错误，尝试刷新...")
    ev("location.reload()")
    time.sleep(10)
    cur = ev("({hash:location.hash,url:location.href.substring(0,80)})")
    if isinstance(cur, dict) and "chrome-error" in cur.get("url",""):
        print("❌ 网络不通，请检查政务平台连接后重试")
        sys.exit(1)

# 如果不在表单页，导航
if isinstance(cur, dict) and "#/flow/base/basic-info" not in cur.get("hash",""):
    print("导航到表单页...")
    ev("location.hash='#/flow/base/basic-info'")
    time.sleep(5)
    if not wait_for_form():
        # 尝试完整URL
        ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info'")
        time.sleep(8)
        if not wait_for_form():
            print("❌ 无法导航到表单页")
            sys.exit(1)

form_count = ev("document.querySelectorAll('.el-form-item').length")
print(f"表单已加载: {form_count}个表单项")

# ============================================================
# Step 1: 填写基础字段 (通过Vue $set)
# ============================================================
print("\n--- Step 1: 基础字段 ---")

ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);if(!comp)return'no_comp';
    var bdi=comp.$data.businessDataInfo;
    
    comp.$set(bdi,'entName','广西智信数据科技有限公司');
    comp.$set(bdi,'name','广西智信数据科技有限公司');
    comp.$set(bdi,'distCode','450103');
    comp.$set(bdi,'distCodeName','青秀区');
    comp.$set(bdi,'fisDistCode','450103');
    comp.$set(bdi,'address','广西壮族自治区/南宁市/青秀区');
    comp.$set(bdi,'detAddress','民族大道100号');
    comp.$set(bdi,'isSelectDistCode','1');
    comp.$set(bdi,'havaAdress','0');
    comp.$set(bdi,'regionCode','450103');
    comp.$set(bdi,'regionName','青秀区');
    comp.$set(bdi,'businessAddress','广西壮族自治区/南宁市/青秀区');
    comp.$set(bdi,'detBusinessAddress','民族大道100号');
    comp.$set(bdi,'itemIndustryTypeCode','I65');
    comp.$set(bdi,'industryTypeName','软件和信息技术服务业');
    comp.$set(bdi,'multiIndustry','I65');
    comp.$set(bdi,'multiIndustryName','软件和信息技术服务业');
    comp.$set(bdi,'industryId','I65');
    comp.$set(bdi,'zlBusinessInd','I65');
    comp.$set(bdi,'busiAreaCode','I65');
    comp.$forceUpdate();
    return'ok';
})()""")

# 同步DOM输入框
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('企业名称')){s.call(input,'广西智信数据科技有限公司');input.dispatchEvent(new Event('input',{bubbles:true}))}
        if(label.includes('详细地址')&&label.includes('住所')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}))}
        if(label.includes('详细地址')&&label.includes('经营')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")
print("  基础字段已设置")

# ============================================================
# Step 2: 行业类型 I65 (Vue store expand + $emit)
# ============================================================
print("\n--- Step 2: 行业类型 I65 ---")

ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click()}
            return;
        }
    }
})()""")
time.sleep(3)

# 展开I节点
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');if(!tree)continue;
        var s=tree.__vue__?.store;if(!s)return;
        var roots=s.root?.childNodes||[];
        for(var i=0;i<roots.length;i++){
            if(roots[i].data?.code==='I'){roots[i].expand();return}
        }
    }
})()""")
time.sleep(3)

# 选择65节点
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');if(!tree)continue;
        var comp=tree.__vue__;if(!comp)return;
        var s=comp.store;if(!s)return;
        var roots=s.root?.childNodes||[];
        for(var i=0;i<roots.length;i++){
            if(roots[i].data?.code==='I'){
                var cs=roots[i].childNodes||[];
                for(var j=0;j<cs.length;j++){
                    if(cs[j].data?.code==='65'){
                        var selectComp=null;
                        var items=document.querySelectorAll('.el-form-item');
                        for(var k=0;k<items.length;k++){
                            var l=items[k].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                            if(l.includes('行业类型')){selectComp=items[k].querySelector('.el-select')?.__vue__;break}
                        }
                        if(selectComp){
                            selectComp.$emit('input','I65');
                            selectComp.$emit('change',cs[j].data);
                            selectComp.selectedLabel='软件和信息技术服务业';
                        }
                        return;
                    }
                }
            }
        }
    }
})()""")
time.sleep(2)
ev("document.body.click()")
time.sleep(1)

ind_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型'))return items[i].querySelector('input')?.value||'';
    }
})()""")
print(f"  行业类型: {ind_val}")

# ============================================================
# Step 3: 经营范围 - 通过tni-business-range搜索选择
# ============================================================
print("\n--- Step 3: 经营范围 ---")

# 点击添加按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return}
    }
})()""")
time.sleep(5)

# 在搜索框输入"软件开发"
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return;
    var si=comp.$refs?.searchInput;
    if(si){
        var inputEl=si.$el?.querySelector('input');
        if(inputEl){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputEl,'软件开发');
            inputEl.dispatchEvent(new Event('input',{bubbles:true}));
            return;
        }
    }
    // 备选: DOM搜索框
    var el=comp.$el;
    var inputs=el.querySelectorAll('input');
    for(var i=0;i<inputs.length;i++){
        var ph=inputs[i].placeholder||'';
        if(ph.includes('搜索')||ph.includes('关键词')||ph.includes('检索')){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputs[i],'软件开发');
            inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
            return;
        }
    }
})()""")
time.sleep(4)

# 获取searchList中的匹配项（正确格式）
search_items = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return[];
    var sl=comp.searchList||comp.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){
        var name=sl[i].name||'';
        if(name==='软件开发'||name==='信息技术咨询服务'||name.includes('数据处理和存储')){
            items.push(JSON.parse(JSON.stringify(sl[i])));
        }
    }
    return items;
})()""", timeout=12)

print(f"  搜索匹配: {len(search_items) if isinstance(search_items,list) else search_items}项")
if isinstance(search_items, list):
    for it in search_items[:3]:
        print(f"    {it.get('name','')} (id={it.get('id','')}, stateCo={it.get('stateCo','')})")

# 设置第一项为主营
if isinstance(search_items, list) and len(search_items) > 0:
    # 标记主营
    search_items[0]['isMainIndustry'] = '1'
    search_items[0]['stateCo'] = '3'
    for i in range(1, len(search_items)):
        search_items[i]['isMainIndustry'] = '0'
        if search_items[i].get('stateCo') != '3':
            search_items[i]['stateCo'] = '1'
    
    names = ';'.join([it.get('name','') for it in search_items])
    confirm_data = {
        'busiAreaData': search_items,
        'genBusiArea': names,
        'busiAreaCode': 'I65',
        'busiAreaName': names
    }
    
    # 调用businese-info.confirm()
    confirm_json = json.dumps(confirm_data, ensure_ascii=False)
    confirm_js = '(function(){var app=document.getElementById("app");var vm=app&&app.__vue__;function findComp(vm,name,d){if(d>15)return null;if(vm.$options&&vm.$options.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var comp=findComp(vm,"businese-info",0);if(!comp)return;comp.confirm(' + confirm_json + ');})()'
    ev(confirm_js)
    print(f"  confirm: {len(search_items)}项, {names[:40]}")
else:
    print("  ❌ searchList为空，尝试直接设置...")
    # 备选: 手动构造（可能服务端不通过）
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }
        var comp=findComp(vm,'businese-info',0);
        if(!comp)return;
        comp.confirm({
            busiAreaData:[
                {id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
            ],
            genBusiArea:'软件开发;信息技术咨询服务',
            busiAreaCode:'I65',
            busiAreaName:'软件开发;信息技术咨询服务'
        });
    })()""")

# 关闭对话框
ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog');
    for(var i=0;i<ds.length;i++){
        if(ds[i].offsetParent===null)continue;
        var close=ds[i].querySelector('[class*="close"]');
        if(close)close.click();
    }
    document.body.click();
})()""")
time.sleep(1)

# ============================================================
# Step 4: 验证
# ============================================================
print("\n--- Step 4: 验证 ---")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

bf = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var form=comp.busineseForm||{};
    return{
        busiAreaDataLen:(form.busiAreaData||[]).length,
        sample:(form.busiAreaData||[]).length>0?JSON.stringify(form.busiAreaData[0]).substring(0,150):'empty',
        genBusiArea:form.genBusiArea?.substring(0,40)||'',
        busiAreaCode:form.busiAreaCode||''
    };
})()""")
print(f"  busineseForm: {bf}")

# ============================================================
# Step 5: 保存草稿
# ============================================================
print("\n--- Step 5: 保存草稿 ---")

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

ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    try{comp.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
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
            else:
                print("  ⚠️ 保存失败，需检查数据格式")
        except:
            print(f"  raw: {r[:150]}")
else:
    print("  无API响应")

# ============================================================
# Step 6: 最终状态
# ============================================================
print("\n--- Step 6: 最终状态 ---")
hash = ev("location.hash")
print(f"  路由: {hash}")

final_errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {final_errors}")

fields = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    return{
        entName:bdi.entName||'',
        distCode:bdi.distCode||'',
        address:bdi.address?.substring(0,30)||'',
        itemIndustryTypeCode:bdi.itemIndustryTypeCode||'',
        businessArea:bdi.businessArea?.substring(0,30)||''
    };
})()""")
print(f"  关键字段: {fields}")

print("\n" + "=" * 60)
print("✅ 脚本执行完成")
print("=" * 60)
