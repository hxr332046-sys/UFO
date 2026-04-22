#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""establish页面分析 → 填写企业类型 → 逐步前进 → flow路由注册 → 表单"""
import json, time, requests, websocket

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    return websocket.create_connection(ws_url, timeout=30)

ws = get_ws()
_mid = 0
def ev(js):
    global _mid, ws; _mid += 1; mid = _mid
    try:
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    except:
        ws = get_ws()
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 完全重载
print("Step 1: 重载页面")
ev("window.location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'")
time.sleep(8)
ws = get_ws()
for _ in range(10):
    if ev("(function(){return !!document.getElementById('app')?.__vue__})()"): break
    time.sleep(2)

# Step 2: 恢复Vuex
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")
time.sleep(2)

# Step 3: 安装XHR拦截器
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,500)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 导航到without-name → toNotName
print("\nStep 4: 导航到establish页面")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

# 调用toNotName
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(wn&&typeof wn.toNotName==='function')wn.toNotName();
})()""")
time.sleep(5)

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# Step 5: 深度分析establish组件
print("\nStep 5: 分析establish组件")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var est=findComp(vm,'establish',0)||findComp(vm,'enterprise-establish',0);
    if(!est){
        // 搜索所有组件
        var all=[];
        function findAll(vm,d){if(d>12)return;if(vm.$options?.name&&vm.$el?.offsetParent!==null&&vm.$options?.name!=='layout'&&vm.$options?.name!=='index'&&vm.$options?.name!=='all-services'&&vm.$options?.name!=='header-comp'&&vm.$options?.name!=='footer-comp'){all.push({name:vm.$options.name,methods:Object.keys(vm.$options?.methods||{}).slice(0,10),dataKeys:Object.keys(vm.$data||{}).slice(0,10)})}for(var i=0;i<(vm.$children||[]).length;i++)findAll(vm.$children[i],d+1)}
        findAll(vm,0);
        return{error:'no_establish',allComps:all};
    }
    var methods=est.$options?.methods||{};
    var srcs={};
    for(var m in methods){srcs[m]=methods[m].toString().substring(0,500)}
    return{
        compName:est.$options?.name||'',
        methods:Object.keys(methods),
        srcs:srcs,
        dataKeys:Object.keys(est.$data||{}).slice(0,20),
        step:est.$data?.step||est.$data?.activeStep||'',
        busiType:est.$data?.busiType||est.$route?.query?.busiType||'',
        entType:est.$data?.entType||est.$route?.query?.entType||'',
        enterpriseTypeList:est.$data?.enterpriseTypeList?.length||0,
        enterpriseType:est.$data?.enterpriseType||''
    };
})()""")
print(f"  comp: {comp}")

# Step 6: 如果有enterpriseType选择，填写
if comp and comp.get('enterpriseTypeList',0) > 0:
    print("\nStep 6: 选择企业类型")
    # 获取企业类型列表
    types = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var est=findComp(vm,'establish',0)||findComp(vm,'enterprise-establish',0);
        if(!est)return null;
        var list=est.$data?.enterpriseTypeList||[];
        return{len:list.length,items:list.slice(0,10).map(function(t){return JSON.stringify(t).substring(0,100)})};
    })()""")
    print(f"  types: len={types.get('len',0) if types else 0}")
    for item in (types.get('items',[]) if types else []):
        print(f"    {item}")
    
    # 选择第一个企业类型
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var est=findComp(vm,'establish',0)||findComp(vm,'enterprise-establish',0);
        if(!est)return;
        var list=est.$data?.enterpriseTypeList||[];
        if(list.length>0){
            // 点击第一个类型卡片
            var cards=document.querySelectorAll('[class*="card"],[class*="item"],[class*="type"]');
            for(var i=0;i<cards.length;i++){
                if(cards[i].offsetParent!==null&&cards[i].textContent?.trim()?.length<50){
                    cards[i].click();
                    return;
                }
            }
            // 直接设置
            est.$set(est.$data,'enterpriseType',list[0].code||list[0].id||list[0].value||'');
            est.$forceUpdate();
        }
    })()""")
    time.sleep(2)

# Step 7: 点击下一步
print("\nStep 7: 点击下一步")
# 找establish组件的下一步方法
next_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var est=findComp(vm,'establish',0)||findComp(vm,'enterprise-establish',0);
    if(!est)return{error:'no_comp'};
    
    // 查找下一步方法
    var methods=est.$options?.methods||{};
    for(var m in methods){
        var src=methods[m].toString();
        if(src.includes('next')||src.includes('Next')||src.includes('step')||src.includes('Step')||src.includes('jump')||src.includes('Jump')||src.includes('submit')||src.includes('handleNext')){
            try{
                methods[m].call(est);
                return{called:m};
            }catch(e){
                return{error:e.message,method:m};
            }
        }
    }
    
    // 尝试DOM点击
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('下一步')&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:'下一步'};
        }
    }
    return{error:'no_next'};
})()""")
print(f"  next_result: {next_result}")
time.sleep(5)

# 检查API和页面
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'isNeedEnterpriseType' not in url and 'notHmEnterpriseType' not in url and 'selectModuleFlows' not in url:
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")

page2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  page: hash={page2.get('hash','') if page2 else '?'} forms={page2.get('formCount',0) if page2 else 0}")

# Step 8: 如果页面变了，继续分析
if page2 and page2.get('hash','') != page.get('hash',''):
    print("\nStep 8: 新页面")
    comp2 = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findActive(vm,d){if(d>12)return null;
            if(vm.$options?.name&&vm.$el?.offsetParent!==null&&vm.$options?.name!=='layout'&&vm.$options?.name!=='index'&&vm.$options?.name!=='all-services'&&vm.$options?.name!=='header-comp'&&vm.$options?.name!=='footer-comp'){
                return{compName:vm.$options?.name,methods:Object.keys(vm.$options?.methods||{}).slice(0,15),dataKeys:Object.keys(vm.$data||{}).slice(0,15)};
            }
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findActive(vm.$children[i],d+1);if(r)return r}return null}
        return findActive(vm,0);
    })()""")
    print(f"  comp: {comp2}")

# Step 9: 检查flow路由
routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
print(f"\n  flow routes: {routes.get('flow',[])}")

# Step 10: 如果establish组件有步骤，逐步推进
print("\nStep 10: 逐步推进establish步骤")
for step in range(8):
    current = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var est=findComp(vm,'establish',0)||findComp(vm,'enterprise-establish',0);
        return{
            hash:location.hash,
            formCount:document.querySelectorAll('.el-form-item').length,
            step:est?.$data?.step||est?.$data?.activeStep||'',
            enterpriseType:est?.$data?.enterpriseType||'',
            compExists:!!est
        };
    })()""")
    h = current.get('hash','') if current else '?'
    fc = current.get('formCount',0) if current else 0
    step_val = current.get('step','') if current else ''
    et = current.get('enterpriseType','') if current else ''
    comp_exists = current.get('compExists',False) if current else False
    
    print(f"\n  步骤{step}: hash={h} forms={fc} step={step_val} entType={et} comp={comp_exists}")
    
    if fc > 20:
        print("  ✅ 大量表单！")
        break
    
    # 检查flow路由
    flow = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');return all.filter(function(r){return r.includes('flow')})})()""")
    if flow:
        print(f"  ✅ flow路由: {flow}")
        for route in flow:
            if 'basic-info' in route:
                ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                time.sleep(5)
                fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
                if fc2 and fc2.get('formCount',0) > 10:
                    print(f"  ✅ 表单加载！hash={fc2.get('hash','')} forms={fc2.get('formCount',0)}")
                break
        break
    
    if not comp_exists:
        print("  establish组件不存在，停止")
        break
    
    # 填写表单（如果有）
    if fc > 0:
        ev("""(function(){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
            for(var i=0;i<inputs.length;i++){
                if(!inputs[i].value&&inputs[i].offsetParent!==null&&!inputs[i].disabled){
                    s.call(inputs[i],'测试数据');inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
                }
            }
        })()""")
        time.sleep(1)
    
    # 勾选checkbox
    ev("""(function(){var cbs=document.querySelectorAll('.el-checkbox__input:not(.is-checked)');for(var i=0;i<cbs.length;i++){cbs[i].click()}})()""")
    time.sleep(1)
    
    # 选择radio
    ev("""(function(){var radios=document.querySelectorAll('.el-radio__input:not(.is-checked)');for(var i=0;i<radios.length;i++){radios[i].click()}})()""")
    time.sleep(1)
    
    # 点击下一步
    clicked = ev("""(function(){
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if((t.includes('下一步')||t.includes('确定')||t.includes('同意')||t.includes('确认'))&&btns[i].offsetParent!==null&&!btns[i].disabled){
                btns[i].click();return{clicked:t};
            }
        }
        return{clicked:false};
    })()""")
    print(f"  点击: {clicked}")
    
    if not clicked or not clicked.get('clicked'):
        # 尝试Vue方法
        method_result = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var est=findComp(vm,'establish',0)||findComp(vm,'enterprise-establish',0);
            if(!est)return null;
            var methods=est.$options?.methods||{};
            for(var m in methods){
                if(m.includes('next')||m.includes('Next')||m.includes('handle')||m.includes('submit')){
                    try{methods[m].call(est);return{called:m}}catch(e){return{error:e.message,method:m}}
                }
            }
            return null;
        })()""")
        print(f"  method: {method_result}")
    
    time.sleep(3)
    
    # 检查API
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])] and 'getUserInfo' not in l.get('url','') and 'getCacheCreateTime' not in l.get('url','')]
    for l in new_apis[-3:]:
        url = l.get('url','')
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    api_logs = api_logs2

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

ws.close()
print("✅ 完成")
