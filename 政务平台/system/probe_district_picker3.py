import requests, json, websocket, time

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
targets = r.json()
for t in targets:
    if '9087' in str(t.get('url','')) and t.get('type') == 'page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        # 1. 获取 popover 的完整 outerHTML（不被截断）
        js1 = """
        (function() {
          const popover = document.querySelector('.tne-data-picker-popover');
          if (!popover) return 'no_popover';
          return popover.outerHTML;
        })()
        """
        ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':js1,'returnByValue':True}}))
        res1 = json.loads(ws.recv())
        html = res1.get('result',{}).get('result',{}).get('value','')
        print('POPOVER HTML:', html[:1000])
        print('---')
        
        # 2. 检查 tne-data-picker 上的 Vue 实例
        js2 = """
        (function() {
          const picker = document.querySelector('.tne-data-picker.wherecascader');
          if (!picker) return 'no_picker';
          const vm = picker.__vue__ || picker.__VUE__;
          if (!vm) return 'no_vue_on_picker';
          return JSON.stringify({
            hasVue: true,
            dataKeys: Object.keys(vm.$data || {}),
            propsKeys: Object.keys(vm.$props || {}),
            visible: vm.visible,
            pickerValue: vm.pickerValue,
            value: vm.value,
            options: vm.options ? vm.options.length : 'no_options'
          });
        })()
        """
        ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':js2,'returnByValue':True}}))
        res2 = json.loads(ws.recv())
        print('PICKER VUE:', res2.get('result',{}).get('result',{}).get('value',''))
        
        # 3. 检查 popover 内的详细结构
        js3 = """
        (function() {
          const popover = document.querySelector('.tne-data-picker-popover');
          if (!popover) return 'no_popover';
          const all = Array.from(popover.querySelectorAll('*'));
          return all.slice(0, 30).map(el => ({
            tag: el.tagName,
            className: el.className,
            text: el.textContent.trim().substring(0, 80),
            childCount: el.children.length,
            hasChildren: el.children.length > 0
          }));
        })()
        """
        ws.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':js3,'returnByValue':True}}))
        res3 = json.loads(ws.recv())
        val3 = res3.get('result',{}).get('result',{}).get('value',[])
        print('POPOVER INNER DETAIL:')
        for v in val3:
            print(v)
        
        # 4. 尝试用 mousedown 而不是 click
        js4 = """
        (function() {
          const ref = document.querySelector('.el-popover__reference');
          if (ref) {
            ref.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
            ref.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            return 'dispatched_mousedown_on_reference';
          }
          const picker = document.querySelector('.tne-data-picker.wherecascader');
          if (picker) {
            picker.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
            return 'dispatched_mousedown_on_picker';
          }
          return 'no_target';
        })()
        """
        ws.send(json.dumps({'id':4,'method':'Runtime.evaluate','params':{'expression':js4,'returnByValue':True}}))
        res4 = json.loads(ws.recv())
        print('MOUSEDOWN:', res4.get('result',{}).get('result',{}).get('value',''))
        
        time.sleep(3)
        
        # 5. 再次检查 popover 内容
        js5 = """
        (function() {
          const popover = document.querySelector('.tne-data-picker-popover');
          if (!popover) return 'no_popover';
          const all = Array.from(popover.querySelectorAll('*'));
          const textEls = all.filter(el => el.textContent.trim().length > 1);
          return textEls.slice(0, 20).map(el => ({
            tag: el.tagName,
            className: el.className,
            text: el.textContent.trim().substring(0, 80)
          }));
        })()
        """
        ws.send(json.dumps({'id':5,'method':'Runtime.evaluate','params':{'expression':js5,'returnByValue':True}}))
        res5 = json.loads(ws.recv())
        val5 = res5.get('result',{}).get('result',{}).get('value',[])
        print('AFTER MOUSEDOWN TEXT ELEMENTS:')
        for v in val5:
            print(v)
        
        # 6. 查看 picker 是否有 input 或 trigger 元素
        js6 = """
        (function() {
          const picker = document.querySelector('.tne-data-picker.wherecascader');
          if (!picker) return 'no_picker';
          const inputs = picker.querySelectorAll('input');
          const triggers = picker.querySelectorAll('[class*="trigger"], [class*="reference"], [class*="icon"]');
          return JSON.stringify({
            inputCount: inputs.length,
            triggerCount: triggers.length,
            inputs: Array.from(inputs).map(i => ({type: i.type, className: i.className, value: i.value})),
            triggers: Array.from(triggers).map(t => ({tag: t.tagName, className: t.className, text: t.textContent.trim().substring(0, 30)}))
          });
        })()
        """
        ws.send(json.dumps({'id':6,'method':'Runtime.evaluate','params':{'expression':js6,'returnByValue':True}}))
        res6 = json.loads(ws.recv())
        print('PICKER INPUTS/TRIGGERS:', res6.get('result',{}).get('result',{}).get('value',''))
        
        ws.close()
        break
