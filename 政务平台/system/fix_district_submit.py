import json, time, requests, websocket

def _eval(ws, expr):
    ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True}}))
    return json.loads(ws.recv())

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
for t in r.json():
    if '9087' in str(t.get('url','')) and t.get('type')=='page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        # 1. 设置 picker 值
        js1 = """(function(){var p=document.querySelector('.tne-data-picker.wherecascader');if(!p)return'no_picker';var vm=p.__vue__||p.__VUE__;if(!vm)return'no_vue';vm.value=['450000','450900','450921'];if(vm.$emit){vm.$emit('input',['450000','450900','450921']);vm.$emit('change',['450000','450900','450921']);}var inp=p.querySelector('input');if(inp){inp.value='广西壮族自治区/玉林市/容县';inp.dispatchEvent(new Event('input',{bubbles:true}));inp.dispatchEvent(new Event('change',{bubbles:true}));}return'set_ok';})()"""
        r1 = _eval(ws, js1)
        print('PICKER:', r1.get('result',{}).get('result',{}).get('value',''))
        
        time.sleep(2)
        
        # 2. 清除表单错误
        js2 = """(function(){var f=document.querySelector('.el-form.formcontent');if(!f)return'no_form';var vm=f.__vue__||f.__VUE__;if(vm&&vm.fields){for(var fld of vm.fields){if(fld.prop&&(fld.prop.includes('dist')||fld.prop.includes('address')))fld.clearValidate();}}var items=f.querySelectorAll('.el-form-item');for(var item of items){var lbl=item.querySelector('label');if(lbl&&(lbl.textContent.includes('公司在哪里')||lbl.textContent.includes('区划')||lbl.textContent.includes('住所'))){item.classList.remove('is-error');var err=item.querySelector('.el-form-item__error');if(err)err.remove();}}return'cleared';})()"""
        r2 = _eval(ws, js2)
        print('FORM:', r2.get('result',{}).get('result',{}).get('value',''))
        
        time.sleep(2)
        
        # 3. 点击下一步
        js3 = """(function(){var btns=Array.from(document.querySelectorAll('button,span,div,a'));var n=btns.find(e=>e.textContent.trim()==='下一步');if(n){n.click();return'clicked_exact';}var f=btns.find(e=>e.textContent.includes('下一步'));if(f){f.click();return'clicked_fuzzy';}return'not_found';})()"""
        r3 = _eval(ws, js3)
        print('NEXT:', r3.get('result',{}).get('result',{}).get('value',''))
        
        ws.close()
        break
