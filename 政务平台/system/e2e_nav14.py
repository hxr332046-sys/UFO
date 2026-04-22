#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 分析toBanLi源码+cardlist数据 → 正确调用 → 自然导航到表单"""
import json, time, os, requests, websocket
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# 恢复Vuex
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")

# 确保在首页
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/page')})()""")
time.sleep(3)

# Step 1: 分析toBanLi源码
print("Step 1: 分析toBanLi源码")
src = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
            var current=allEls[i];
            for(var d=0;d<15&&current;d++){
                var comp=current.__vue__;
                if(comp&&typeof comp.toBanLi==='function'){
                    return{
                        toBanLi:comp.toBanLi.toString().substring(0,800),
                        depth:d,
                        compName:comp.$options?.name||'',
                        dataKeys:Object.keys(comp.$data||{}).slice(0,15)
                    };
                }
                current=current.parentElement;
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  toBanLi src: {src.get('toBanLi','')[:500] if src else 'None'}")

# Step 2: 获取cardlist数据
print("\nStep 2: 获取cardlist数据")
cardlist = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
            var current=allEls[i];
            for(var d=0;d<15&&current;d++){
                var comp=current.__vue__;
                if(comp&&typeof comp.toBanLi==='function'){
                    var cl=comp.$data?.cardlist||comp.$data?.allList||comp.$data?.itemClick||[];
                    // 也检查selected
                    var sel=comp.$data?.selected||comp.$data?.active||'';
                    return{
                        cardlistLen:cl.length,
                        cardlist:JSON.stringify(cl)?.substring(0,500)||'',
                        selected:sel,
                        active:comp.$data?.active||'',
                        itemClick:JSON.stringify(comp.$data?.itemClick)?.substring(0,100)||''
                    };
                }
                current=current.parentElement;
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  cardlistLen: {cardlist.get('cardlistLen',0) if cardlist else 0}")
print(f"  cardlist: {cardlist.get('cardlist','')[:300] if cardlist else ''}")
print(f"  selected: {cardlist.get('selected','') if cardlist else ''}")
print(f"  active: {cardlist.get('active','') if cardlist else ''}")

# Step 3: 安装XHR拦截器
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(){
        var self=this;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 用正确的card数据调用toBanLi
print("\nStep 4: 调用toBanLi")
# 尝试多种参数格式
for param_format in [
    # 格式1: 直接传cardlist中设立登记的item
    """(function(){
        var allEls=document.querySelectorAll('*');
        for(var i=0;i<allEls.length;i++){
            var t=allEls[i].textContent?.trim()||'';
            if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
                var current=allEls[i];
                for(var d=0;d<15&&current;d++){
                    var comp=current.__vue__;
                    if(comp&&typeof comp.toBanLi==='function'){
                        var cl=comp.$data?.cardlist||comp.$data?.allList||[];
                        for(var j=0;j<cl.length;j++){
                            var name=cl[j].name||cl[j].busiName||cl[j].title||cl[j].label||'';
                            if(name.includes('设立登记')||name.includes('经营主体')){
                                try{comp.toBanLi(cl[j]);return{called:true,card:JSON.stringify(cl[j]).substring(0,100)}}catch(e){return{error:e.message}}
                            }
                        }
                        // 如果cardlist中没有设立登记，传整个cardlist的第一个
                        if(cl.length>0){
                            try{comp.toBanLi(cl[0]);return{called:true,card:JSON.stringify(cl[0]).substring(0,100)}}catch(e){return{error:e.message}}
                        }
                        // 传空对象
                        try{comp.toBanLi({});return{called:true,card:'empty'}}catch(e){return{error:e.message}}
                    }
                    current=current.parentElement;
                }
            }
        }
        return{error:'not_found'};
    })()""",
    # 格式2: 传event对象
    """(function(){
        var allEls=document.querySelectorAll('*');
        for(var i=0;i<allEls.length;i++){
            var t=allEls[i].textContent?.trim()||'';
            if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
                var current=allEls[i];
                for(var d=0;d<15&&current;d++){
                    var comp=current.__vue__;
                    if(comp&&typeof comp.toBanLi==='function'){
                        try{comp.toBanLi({name:'设立登记',code:'07',busiType:'07',entType:'1100'});return{called:true}}catch(e){return{error:e.message}}
                    }
                    current=current.parentElement;
                }
            }
        }
        return{error:'not_found2'};
    })()"""
]:
    result = ev(param_format)
    print(f"  result: {result}")
    if result and result.get('called'):
        time.sleep(5)
        break

# Step 5: 检查API和页面
print("\nStep 5: 检查结果")
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# Step 6: 如果到了新页面，继续导航
if page and page.get('hash','') != '#/index/page':
    print("\nStep 6: 继续导航")
    
    if 'enterprise' in page.get('hash',''):
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(5)
    elif 'without-name' in page.get('hash','') or 'select-prise' in page.get('hash',''):
        print("  在名称选择页")
        
        # 获取名称列表
        ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
            if(wn&&typeof wn.getData==='function')wn.getData();
        })()""")
        time.sleep(3)
        
        # 检查列表
        list_check = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
            if(!wn)return null;
            var pl=wn.$data?.priseList||wn.$data?.busiDataList||[];
            var apiLogs=window.__api_logs||[];
            return{len:pl.length,apis:apiLogs.filter(function(l){return l.url?.includes('name')||l.url?.includes('prise')||l.url?.includes('select')}).map(function(l){return l.url?.split('?')[0]?.split('/').pop()+' status='+l.status})};
        })()""")
        print(f"  list: len={list_check.get('len',0) if list_check else 0} apis={list_check.get('apis',[]) if list_check else []}")
        
        # 如果有列表，选择第一个
        if list_check and list_check.get('len',0) > 0:
            print("  选择第一个...")
            ev("""(function(){
                var rows=document.querySelectorAll('.el-table__row');
                for(var i=0;i<rows.length;i++){
                    if(rows[i].offsetParent!==null){rows[i].click();return}
                }
            })()""")
            time.sleep(2)
            
            # 检查nameId
            comp = ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                return{nameId:wn?.$data?.nameId||'',hash:location.hash};
            })()""")
            print(f"  nameId={comp.get('nameId','') if comp else ''}")
            
            if comp and comp.get('nameId'):
                nid = comp['nameId']
                ev(f"""(function(){{
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                    if(wn&&typeof wn.startSheli==='function')wn.startSheli({{nameId:'{nid}'}});
                }})()""")
                time.sleep(5)
        else:
            # 使用其他来源名称
            print("  使用其他来源名称...")
            ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                if(wn){
                    if(typeof wn.toOther==='function')wn.toOther();
                    else if('isOther' in wn.$data)wn.$set(wn.$data,'isOther',true);
                    wn.$forceUpdate();
                }
            })()""")
            time.sleep(2)
            
            # 填写
            ev("""(function(){
                var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
                for(var i=0;i<inputs.length;i++){
                    var ph=inputs[i].placeholder||'';
                    if(ph.includes('企业名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
                    if(ph.includes('保留单号')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
                }
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&sp.$data?.form){sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');sp.$set(sp.$data.form,'numbers','GX2024001');sp.$forceUpdate()}
            })()""")
            time.sleep(1)
            
            # 找提交按钮
            btns2 = ev("""(function(){var btns=document.querySelectorAll('button,.el-button');var r=[];for(var i=0;i<btns.length;i++){if(btns[i].offsetParent!==null)r.push({idx:i,text:btns[i].textContent?.trim()?.substring(0,20)||'',type:btns[i].type||''})}return r})()""")
            print(f"  按钮: {btns2}")
            
            # 点击所有可能的提交按钮
            for btn in (btns2 or []):
                t = btn.get('text','')
                idx = btn.get('idx',0)
                if any(kw in t for kw in ['确定','确认','提交','保存','下一步','选择']):
                    print(f"  点击: {t}")
                    ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
                    time.sleep(3)
                    
                    # 检查API
                    api_logs2 = ev("window.__api_logs||[]")
                    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
                    for l in new_apis:
                        print(f"  NEW API: {l.get('method','')} {l.get('url','').split('?')[0].split('/').pop()} status={l.get('status')} resp={l.get('response','')[:80]}")
                    
                    # 检查nameId
                    comp2 = ev("""(function(){
                        var app=document.getElementById('app');var vm=app?.__vue__;
                        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                        var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                        return{nameId:wn?.$data?.nameId||'',hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length};
                    })()""")
                    print(f"  comp2: nameId={comp2.get('nameId','') if comp2 else ''} hash={comp2.get('hash','') if comp2 else ''}")
                    
                    if comp2 and comp2.get('nameId'):
                        nid = comp2['nameId']
                        print(f"  ✅ nameId={nid}")
                        ev(f"""(function(){{
                            var app=document.getElementById('app');var vm=app?.__vue__;
                            function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                            var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                            if(wn&&typeof wn.startSheli==='function')wn.startSheli({{nameId:'{nid}'}});
                        }})()""")
                        time.sleep(5)
                        break

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("440.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("440.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})

ws.close()
print("✅ 完成")
