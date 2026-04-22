#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step20: 深入分析without-name组件渲染条件 → 触发表单显示"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)

_mid = 0
def ev(js, mid=None):
    global _mid
    if mid is None: mid = _mid + 1; _mid = mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":10000}}))
    for _ in range(20):
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r.get("result",{}).get("result",{}).get("value")
        except:
            return None
    return None

# 1. 恢复Vuex token
print("=== 1. 恢复Vuex token ===")
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
    return{token:t.substring(0,10),len:t.length};
})()""")

# 2. 确保在without-name页面
print("\n=== 2. 导航 ===")
ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    if(vm?.$router)vm.$router.push('/index/without-name?entType=1100');
})()""")
time.sleep(5)

# 3. 深入分析without-name组件
print("\n=== 3. without-name组件完整分析 ===")
comp = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    
    // 找without-name组件实例
    var inst=null;
    for(var i=0;i<matched.length;i++){
        var m=matched[i];
        if(m.name==='without-name'){
            inst=m.instances?.default;
            break;
        }
    }
    if(!inst)return{error:'no_instance'};
    
    // 获取完整$data
    var data={};
    for(var k in inst.$data||{}){
        var v=inst.$data[k];
        if(typeof v==='object'&&v!==null){
            data[k]=JSON.stringify(v)?.substring(0,100)||'object';
        }else{
            data[k]=String(v).substring(0,50);
        }
    }
    
    // 获取computed
    var computed={};
    for(var k in inst.$options?.computed||{}){
        try{
            var v=inst[k];
            if(typeof v==='object'&&v!==null){
                computed[k]=JSON.stringify(v)?.substring(0,80)||'object';
            }else if(v!==undefined){
                computed[k]=String(v).substring(0,50);
            }
        }catch(e){}
    }
    
    // 获取methods
    var methods=[];
    for(var k in inst.$options?.methods||{}){
        methods.push(k);
    }
    
    // 获取watch
    var watches=Object.keys(inst.$options?.watch||{});
    
    // 获取template条件 - 检查v-if/v-show
    var el=inst.$el;
    var conditions=[];
    if(el){
        // 检查所有子元素的v-if条件
        var all=el.querySelectorAll('*');
        for(var i=0;i<Math.min(all.length,100);i++){
            var style=getComputedStyle(all[i]);
            if(style.display==='none'||style.visibility==='hidden'){
                conditions.push({tag:all[i].tagName,cls:all[i].className?.substring(0,25)||'',display:style.display,visibility:style.visibility,text:all[i].textContent?.trim()?.substring(0,20)||''});
            }
        }
    }
    
    return{
        data:data,
        computed:computed,
        methods:methods.slice(0,20),
        watches:watches,
        hiddenElements:conditions.slice(0,15),
        elHtml:el?.innerHTML?.substring(0,500)||'no_el',
        elChildCount:el?.children?.length||0
    };
})()""")
if comp:
    print(f"  data: {json.dumps(comp.get('data',{}), ensure_ascii=False)[:300]}")
    print(f"  computed: {json.dumps(comp.get('computed',{}), ensure_ascii=False)[:300]}")
    print(f"  methods: {comp.get('methods',[])}")
    print(f"  watches: {comp.get('watches',[])}")
    print(f"  hiddenElements: {comp.get('hiddenElements',[])}")
    print(f"  elChildCount: {comp.get('elChildCount',0)}")
    print(f"  elHtml: {(comp.get('elHtml','') or '')[:200]}")

# 4. 检查busiDataList内容
print("\n=== 4. busiDataList详细内容 ===")
busi = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    var bdl=inst.$data?.busiDataList;
    return{
        type:typeof bdl,
        isArray:Array.isArray(bdl),
        length:bdl?.length||0,
        content:JSON.stringify(bdl)?.substring(0,500)||'null',
        priseName:inst.$data?.priseName,
        priseNo:inst.$data?.priseNo
    };
})()""")
print(f"  busiDataList: {json.dumps(busi or {}, ensure_ascii=False)[:400]}")

# 5. 检查组件模板渲染逻辑
print("\n=== 5. 模板渲染分析 ===")
template = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    
    // 获取render函数
    var render=inst.$options?.render;
    var renderStr=render?render.toString().substring(0,500):'no_render';
    
    // 获取template
    var tpl=inst.$options?.template;
    var tplStr=tpl?tpl.substring(0,500):'no_template';
    
    // 检查v-if条件变量
    var conditions={};
    var possibleIfVars=['showForm','visible','loaded','ready','step','currentStep','activeStep','showNameInput','hasBusiData','isEstablish'];
    for(var i=0;i<possibleIfVars.length;i++){
        var v=inst[possibleIfVars[i]];
        if(v!==undefined)conditions[possibleIfVars[i]]=typeof v==='object'?JSON.stringify(v)?.substring(0,40):String(v);
    }
    
    // 检查$el内部结构
    var el=inst.$el;
    var structure=[];
    if(el){
        function walk(node,depth){
            if(depth>4)return;
            var tag=node.tagName||'#text';
            var text=node.textContent?.trim()?.substring(0,20)||'';
            var cls=node.className||'';
            var display=getComputedStyle(node)?.display||'';
            structure.push({depth:depth,tag:tag,cls:cls?.substring(0,15),display:display,text:text});
            for(var i=0;i<node.children?.length&&i<5;i++){
                walk(node.children[i],depth+1);
            }
        }
        walk(el,0);
    }
    
    return{renderPreview:renderStr,templatePreview:tplStr,conditions:conditions,structure:structure.slice(0,30)};
})()""")
print(f"  conditions: {template.get('conditions',{}) if template else 'N/A'}")
print(f"  structure:")
for s in (template.get('structure',[]) if template else []):
    indent = "  " * s.get('depth',0)
    print(f"    {indent}{s.get('tag','')} .{s.get('cls','')} display={s.get('display','')} text={s.get('text','')}")

# 6. 如果有条件控制表单显示，尝试修改
print("\n=== 6. 尝试触发渲染 ===")
trigger = ev("""(function(){
    var app=document.getElementById('app');
    var vm=app?.__vue__;
    var route=vm?.$route;
    var matched=route?.matched||[];
    var inst=null;
    for(var i=0;i<matched.length;i++){
        if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
    }
    if(!inst)return{error:'no_instance'};
    
    var results=[];
    
    // 尝试调用init/mounted/created等方法
    var tryMethods=['init','initData','loadData','fetchData','getList','getBusiData','handleInit','onMounted','refresh','reload'];
    for(var i=0;i<tryMethods.length;i++){
        if(typeof inst[tryMethods[i]]==='function'){
            try{
                inst[tryMethods[i]]();
                results.push(tryMethods[i]+':called');
            }catch(e){
                results.push(tryMethods[i]+':'+e.message.substring(0,30));
            }
        }
    }
    
    // 检查是否有step/currentStep控制
    if(inst.$data.step!==undefined||inst.$data.currentStep!==undefined){
        inst.$data.step=1;
        inst.$data.currentStep=1;
        results.push('set_step=1');
    }
    
    // 检查busiDataList是否为空，如果是则填充
    if(!inst.$data.busiDataList||inst.$data.busiDataList.length===0){
        inst.$data.busiDataList=[{name:'test',code:'1100'}];
        results.push('set_busiDataList');
    }
    
    // forceUpdate
    inst.$forceUpdate();
    results.push('forceUpdate');
    
    return results;
})()""")
print(f"  trigger: {trigger}")
time.sleep(5)

# 7. 检查结果
page = ev("""(function(){
    return{
        hash:location.hash,
        formCount:document.querySelectorAll('.el-form-item').length,
        inputCount:document.querySelectorAll('input,textarea,select').length,
        text:(document.body.innerText||'').substring(0,300)
    };
})()""")
print(f"\n=== 7. 结果 ===")
print(f"  forms: {(page or {}).get('formCount',0)} inputs: {(page or {}).get('inputCount',0)}")
print(f"  text: {(page or {}).get('text','')[:200]}")

# 8. 如果还是没有，检查真实浏览器中的情况
if (page or {}).get('formCount',0) == 0:
    print("\n=== 8. 检查组件内部iframe ===")
    # 可能表单在iframe中
    iframes = ev("""(function(){
        var ifs=document.querySelectorAll('iframe');
        var r=[];
        for(var i=0;i<ifs.length;i++){
            r.push({i:i,src:(ifs[i].src||ifs[i].getAttribute('src')||'').substring(0,80),visible:ifs[i].offsetParent!==null,w:ifs[i].offsetWidth,h:ifs[i].offsetHeight});
        }
        return r;
    })()""")
    print(f"  iframes: {iframes}")
    
    # 检查是否有弹窗/对话框
    dialogs = ev("""(function(){
        var dgs=document.querySelectorAll('.el-dialog,.el-drawer,[class*="modal"],[class*="popup"],[class*="overlay"]');
        var r=[];
        for(var i=0;i<dgs.length;i++){
            r.push({cls:dgs[i].className?.substring(0,30)||'',visible:dgs[i].offsetParent!==null,text:dgs[i].textContent?.trim()?.substring(0,30)||''});
        }
        return r;
    })()""")
    print(f"  dialogs: {dialogs}")

    # 检查Vue组件的完整DOM
    full_dom = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        var route=vm?.$route;
        var matched=route?.matched||[];
        var inst=null;
        for(var i=0;i<matched.length;i++){
            if(matched[i].name==='without-name'){inst=matched[i].instances?.default;break}
        }
        if(!inst||!inst.$el)return{error:'no_el'};
        return{outerHTML:inst.$el.outerHTML?.substring(0,800)||'empty'};
    })()""")
    print(f"  component DOM: {(full_dom or {}).get('outerHTML','')[:400]}")

# 截图
try:
    ws.send(json.dumps({"id":8888,"method":"Page.captureScreenshot","params":{"format":"png"}}))
    for _ in range(10):
        try:
            ws.settimeout(10);r=json.loads(ws.recv())
            if r.get("id")==8888:
                d=r.get("result",{}).get("data","")
                if d:
                    p=os.path.join(os.path.dirname(__file__),"..","data","e2e_step20.png")
                    with open(p,"wb") as f:f.write(base64.b64decode(d))
                    print(f"\n📸 {p}")
                break
        except:break
except:pass

ws.close()
print("\n✅ Step20 完成")
