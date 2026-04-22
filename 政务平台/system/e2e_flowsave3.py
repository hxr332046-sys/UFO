#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""拦截API+确保form完整+调用fzjgFlowSave"""
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

# ============================================================
# Step 1: 回到guide/base页面
# ============================================================
print("Step 1: 回到guide/base")
ev("""(function(){
    document.getElementById('app').__vue__.$router.push('/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=');
})()""")
time.sleep(3)

# ============================================================
# Step 2: 拦截所有XHR和router.jump
# ============================================================
print("Step 2: 拦截XHR+router.jump")
ev("""(function(){
    window.__all_xhr=[];
    window.__save_api=null;
    window.__jump_args=[];
    
    // 拦截XHR
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        window.__all_xhr.push({url:url.substring(0,80),bodyLen:(body||'').length});
        if(url.includes('guide')||url.includes('flow')||url.includes('save')||url.includes('extraDto')){
            var self=this;
            self.addEventListener('load',function(){
                window.__save_api={url:url,status:self.status,text:(self.responseText||'').substring(0,200)};
            });
        }
        return origSend.apply(this,arguments);
    };
    
    // 拦截router.jump
    var vm=document.getElementById('app').__vue__;
    var router=vm.$router||vm.$root?.$router;
    if(router&&router.jump){
        var origJump=router.jump.bind(router);
        router.jump=function(){
            window.__jump_args.push(Array.from(arguments).map(function(a){
                return typeof a==='object'?JSON.stringify(a).substring(0,200):String(a);
            }));
            return origJump.apply(router,arguments);
        };
    }
    
    return 'intercepted';
})()""")

# ============================================================
# Step 3: 确保form数据完整
# ============================================================
print("\nStep 3: 确保form数据")
ensure = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    var form=comp.form||comp.$data?.form;
    if(!form)return'no_form';
    
    // 完整设置所有需要的字段
    comp.$set(form,'entType','1100');
    comp.$set(form,'entTypeCode','1100');
    comp.$set(form,'busiType','02_4');
    comp.$set(form,'nameCode','0');
    comp.$set(form,'registerCapital','100');
    comp.$set(form,'moneyKindCode','156');
    comp.$set(form,'distList',['450000','450100','450103']);
    comp.$set(form,'havaAdress','0');
    comp.$set(form,'fzSign','N');
    comp.$set(form,'detAddress','民族大道100号');
    comp.$set(form,'address','广西壮族自治区/南宁市/青秀区');
    comp.$set(form,'distCode','450103');
    comp.$set(form,'streetCode','');
    comp.$set(form,'streetName','');
    comp.$set(form,'parentEntRegno','');
    comp.$set(form,'parentEntName','');
    
    // 设置cascader值
    var casEl=document.querySelector('.wherecascader');
    if(casEl){
        var casVm=casEl.__vue__;
        if(casVm){
            casVm.$emit('input',['450000','450100','450103']);
            casVm.$emit('change',['450000','450100','450103']);
            casVm.$set(casVm.$data,'inputSelected','广西壮族自治区/南宁市/青秀区');
            casVm.$set(casVm.$data,'checkValue',['450000','450100','450103']);
        }
    }
    
    // 清除验证
    var elForm=comp.$refs?.form;
    if(elForm){
        try{elForm.clearValidate()}catch(e){}
    }
    
    return {formSet:true,formKeys:Object.keys(form).length};
})()""")
print(f"  {ensure}")

# ============================================================
# Step 4: 调用fzjgFlowSave（这是下一步按钮的实际入口）
# ============================================================
print("\nStep 4: 调用fzjgFlowSave")
save_result = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findGuideComp(vm,d){
        if(d>12)return null;
        var data=vm.$data||{};
        if(data.distList!==undefined&&vm.$options?.name==='index')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){
            var r=findGuideComp(vm.$children[i],d+1);
            if(r)return r;
        }
        return null;
    }
    var comp=findGuideComp(vm,0);
    if(!comp)return'no_comp';
    try{
        comp.fzjgFlowSave();
        return {called:true};
    }catch(e){
        return {error:e.message.substring(0,100)};
    }
})()""", timeout=20)
print(f"  fzjgFlowSave: {save_result}")
time.sleep(8)

# ============================================================
# Step 5: 检查结果
# ============================================================
print("\nStep 5: 检查结果")
xhr_calls = ev("window.__all_xhr")
print(f"  XHR调用: {xhr_calls}")

save_api = ev("window.__save_api")
print(f"  保存API: {save_api}")

jump_args = ev("window.__jump_args")
print(f"  router.jump: {jump_args}")

cur = ev("location.hash")
print(f"  路由: {cur}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误: {errors}")

comps = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    return {flowControl:!!fc,withoutName:!!wn,hash:location.hash};
})()""")
print(f"  组件: {comps}")

# 如果有without-name
if isinstance(comps, dict) and comps.get('withoutName'):
    ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0);
        if(wn)wn.toNotName();
    })()""")
    time.sleep(5)
    comps2 = ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var fc=findComp(vm,'flow-control',0);
        return {flowControl:!!fc,hash:location.hash};
    })()""")
    print(f"  toNotName后: {comps2}")

print("\n✅ 完成")
