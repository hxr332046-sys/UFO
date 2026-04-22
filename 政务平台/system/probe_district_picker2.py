import requests, json, websocket, time

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
targets = r.json()
for t in targets:
    if '9087' in str(t.get('url','')) and t.get('type') == 'page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        # 1. 获取 tne-data-picker 的完整DOM结构
        js1 = """
        (function() {
          const picker = document.querySelector('.tne-data-picker.wherecascader');
          if (!picker) return 'no_picker';
          return JSON.stringify({
            tag: picker.tagName,
            className: picker.className,
            innerHTML: picker.innerHTML.substring(0, 500),
            children: Array.from(picker.children).map(c => ({
              tag: c.tagName,
              className: c.className,
              text: c.textContent.trim().substring(0, 100)
            }))
          });
        })()
        """
        ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':js1,'returnByValue':True}}))
        res1 = json.loads(ws.recv())
        print('PICKER STRUCT:', res1.get('result',{}).get('result',{}).get('value',''))
        
        # 2. 尝试点击 picker 本身
        js2 = """
        (function() {
          const picker = document.querySelector('.tne-data-picker.wherecascader');
          if (!picker) return 'no_picker';
          picker.click();
          return 'clicked_picker';
        })()
        """
        ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':js2,'returnByValue':True}}))
        res2 = json.loads(ws.recv())
        print('CLICK:', res2.get('result',{}).get('result',{}).get('value',''))
        
        time.sleep(3)
        
        # 3. 等待后再次探测弹出层内容
        js3 = """
        (function() {
          const popover = document.querySelector('.tne-data-picker-popover');
          if (!popover) return 'no_popover';
          return JSON.stringify({
            tag: popover.tagName,
            className: popover.className,
            text: popover.textContent.trim().substring(0, 300),
            children: Array.from(popover.children).map(c => ({
              tag: c.tagName,
              className: c.className,
              text: c.textContent.trim().substring(0, 200)
            }))
          });
        })()
        """
        ws.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':js3,'returnByValue':True}}))
        res3 = json.loads(ws.recv())
        print('POPOVER AFTER CLICK:', res3.get('result',{}).get('result',{}).get('value',''))
        
        # 4. 检查是否有 el-cascader-menu 或类似级联菜单
        js4 = """
        (function() {
          const menus = Array.from(document.querySelectorAll('.el-cascader-menu, .el-cascader-node, .el-cascader-panel, .tne-cascader, [class*="cascader"]'));
          return menus.slice(0, 10).map(el => ({
            tag: el.tagName,
            className: el.className,
            text: el.textContent.trim().substring(0, 100)
          }));
        })()
        """
        ws.send(json.dumps({'id':4,'method':'Runtime.evaluate','params':{'expression':js4,'returnByValue':True}}))
        res4 = json.loads(ws.recv())
        val4 = res4.get('result',{}).get('result',{}).get('value',[])
        print('CASCADER ELEMENTS:', val4)
        
        # 5. 探测Vue组件上的值
        js5 = """
        (function() {
          const app = document.querySelector('#app');
          let vm = null;
          if (app && app.__vue__) vm = app.__vue__;
          if (app && app.__VUE__) vm = app.__VUE__;
          if (!vm) {
            // 遍历找 Vue 实例
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
              if (el.__vue__) { vm = el.__vue__; break; }
              if (el.__VUE__) { vm = el.__VUE__; break; }
            }
          }
          if (!vm) return 'no_vue';
          
          // 找 form 数据
          let form = vm.$refs?.form || vm.form || vm.$data?.form;
          if (!form && vm.$children) {
            for (const child of vm.$children) {
              if (child.form) { form = child.form; break; }
              if (child.$data && child.$data.form) { form = child.$data.form; break; }
            }
          }
          
          if (!form) return 'no_form';
          return JSON.stringify({
            distCode: form.distCode,
            distCodeArr: form.distCodeArr,
            address: form.address,
            entType: form.entType,
            nameCode: form.nameCode
          });
        })()
        """
        ws.send(json.dumps({'id':5,'method':'Runtime.evaluate','params':{'expression':js5,'returnByValue':True}}))
        res5 = json.loads(ws.recv())
        print('VUE FORM:', res5.get('result',{}).get('result',{}).get('value',''))
        
        ws.close()
        break
