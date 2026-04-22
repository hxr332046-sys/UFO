#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深入分析operationBusinessDataInfo源码，找到busiAreaData序列化逻辑"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: 获取operationBusinessDataInfo完整源码
# ============================================================
print("Step 1: operationBusinessDataInfo完整源码")
src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var fn=fc.$options?.methods?.operationBusinessDataInfo;
    if(!fn)return'no_method';
    return fn.toString();
}})()""", timeout=15)

if isinstance(src, str) and len(src) > 50:
    # 保存到文件分析
    with open(r'g:\UFO\政务平台\data\op_method_src.js', 'w', encoding='utf-8') as f:
        f.write(src)
    print(f"  源码长度: {len(src)} 字符，已保存到 data/op_method_src.js")
    # 打印关键片段
    # 搜索busiAreaData相关
    idx1 = src.find('busiAreaData')
    if idx1 >= 0:
        print(f"\n  === busiAreaData 上下文 (pos {idx1}) ===")
        print(f"  ...{src[max(0,idx1-100):idx1+200]}...")
    idx2 = src.find('encodeURIComponent')
    if idx2 >= 0:
        print(f"\n  === encodeURIComponent 上下文 (pos {idx2}) ===")
        print(f"  ...{src[max(0,idx2-100):idx2+200]}...")
    idx3 = src.find('genBusiArea')
    if idx3 >= 0:
        print(f"\n  === genBusiArea 上下文 (pos {idx3}) ===")
        print(f"  ...{src[max(0,idx3-100):idx3+200]}...")
    # 搜索JSON.stringify
    idx4 = src.find('JSON.stringify')
    if idx4 >= 0:
        print(f"\n  === JSON.stringify 上下文 (pos {idx4}) ===")
        print(f"  ...{src[max(0,idx4-80):idx4+150]}...")
else:
    print(f"  ERROR: {src[:200]}")

# ============================================================
# Step 2: 搜索save方法源码
# ============================================================
print("\n\nStep 2: save方法源码")
save_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var fn=fc.$options?.methods?.save;
    if(!fn)return'no_method';
    return fn.toString();
}})()""", timeout=15)

if isinstance(save_src, str) and len(save_src) > 50:
    with open(r'g:\UFO\政务平台\data\save_method_src.js', 'w', encoding='utf-8') as f:
        f.write(save_src)
    print(f"  save源码长度: {len(save_src)} 字符，已保存")
    # 搜索关键片段
    for kw in ['operationBusinessDataInfo', 'busiAreaData', 'genBusiArea', 'flow-save']:
        idx = save_src.find(kw)
        if idx >= 0:
            print(f"  {kw} at pos {idx}: ...{save_src[max(0,idx-50):idx+100]}...")

# ============================================================
# Step 3: 搜索businese-info的confirm方法
# ============================================================
print("\n\nStep 3: businese-info confirm源码")
confirm_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    var fn=bi.$options?.methods?.confirm;
    if(!fn)return'no_method';
    return fn.toString();
}})()""", timeout=15)

if isinstance(confirm_src, str) and len(confirm_src) > 50:
    print(f"  confirm源码长度: {len(confirm_src)}")
    for kw in ['busiAreaData', 'genBusiArea', 'busiAreaCode', 'busiAreaName', 'emit', '$parent']:
        idx = confirm_src.find(kw)
        if idx >= 0:
            print(f"  {kw} at pos {idx}: ...{confirm_src[max(0,idx-40):idx+80]}...")

# ============================================================
# Step 4: 检查businese-info是否有flow-save-basic-info回调
# ============================================================
print("\n\nStep 4: businese-info的flow-save回调")
bi_save_cb = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    // 查找所有方法
    var methods=Object.keys(bi.$options?.methods||{{}});
    var saveRelated=methods.filter(function(m){{return m.includes('save')||m.includes('Save')||m.includes('data')||m.includes('Data')||m.includes('submit')}});
    // 查找eventBus监听
    var eb=bi.eventBus||bi.$parent?.eventBus;
    var ebEvents=eb?Object.keys(eb._events||{{}}):[];
    var saveEvents=ebEvents.filter(function(k){{return k.includes('save')}});
    return{{methods:methods,saveRelated:saveRelated,ebSaveEvents:saveEvents}};
}})()""")
print(f"  businese-info: {json.dumps(bi_save_cb, ensure_ascii=False)[:300] if isinstance(bi_save_cb,dict) else bi_save_cb}")

# ============================================================
# Step 5: 检查flow-save-basic-info的回调函数源码
# ============================================================
print("\n\nStep 5: flow-save-basic-info回调源码")
cb_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return'no_bi';
    var eb=bi.eventBus;
    if(!eb)return'no_eb';
    var handlers=eb._events?.['flow-save-basic-info'];
    if(!handlers||!handlers.length)return'no_handler';
    // 取第一个handler的源码
    return handlers[0].toString().substring(0,1000);
}})()""", timeout=15)
print(f"  callback: {cb_src[:500] if isinstance(cb_src,str) else cb_src}")

print("\n✅ 完成")
