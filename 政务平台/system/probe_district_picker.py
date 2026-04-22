import requests, json, websocket, time

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
targets = r.json()
for t in targets:
    if '9087' in str(t.get('url','')) and t.get('type') == 'page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        # 步骤1: 点击区划输入框
        js1 = """
        (function() {
          const labels = Array.from(document.querySelectorAll('h2, label, span, div'));
          const distLabel = labels.find(el => el.textContent.includes('公司在哪里') || el.textContent.includes('行政区划'));
          if (!distLabel) return 'no_label';
          let parent = distLabel.parentElement;
          for (let i=0; i<10; i++) {
            if (!parent) break;
            const input = parent.querySelector('input, .el-input__inner, [class*="picker"], [class*="select"], [class*="cascader"]');
            if (input) {
              input.click();
              input.focus();
              return JSON.stringify({action:'clicked', tag:input.tagName, className:input.className, id:input.id, parentClass:parent.className});
            }
            parent = parent.parentElement;
          }
          return 'no_input_found';
        })()
        """
        ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':js1,'returnByValue':True}}))
        res1 = json.loads(ws.recv())
        val1 = res1.get('result',{}).get('result',{}).get('value','')
        print('STEP1:', val1)
        
        time.sleep(2)
        
        # 步骤2: 探测弹窗内元素
        js2 = """
        (function() {
          const all = Array.from(document.querySelectorAll('li, div, span, a, button'));
          const hits = all.filter(el => {
            const t = el.textContent.trim();
            return t === '广西壮族自治区' || t === '玉林市' || t === '容县' || t === '广西' || t.includes('省级') || t.includes('市级') || t.includes('县级') || t.includes('请选择');
          });
          return hits.slice(0, 20).map(el => ({
            text: el.textContent.trim().substring(0, 60),
            tag: el.tagName,
            className: el.className,
            parentTag: el.parentElement ? el.parentElement.tagName : '',
            parentClass: el.parentElement ? el.parentElement.className : ''
          }));
        })()
        """
        ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':js2,'returnByValue':True}}))
        res2 = json.loads(ws.recv())
        val2 = res2.get('result',{}).get('result',{}).get('value',[])
        print('\nSTEP2 candidates:')
        for v in val2:
            print(v)
        
        # 步骤3: 探测所有弹出层
        js3 = """
        (function() {
          const popups = Array.from(document.querySelectorAll('[class*="popup"], [class*="dialog"], [class*="picker"], [class*="dropdown"], [class*="cascader"], .el-dialog, .el-popper, .el-picker-panel, [class*="panel"]'));
          return popups.map(el => ({
            tag: el.tagName,
            className: el.className,
            text: el.textContent.trim().substring(0, 150)
          }));
        })()
        """
        ws.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':js3,'returnByValue':True}}))
        res3 = json.loads(ws.recv())
        val3 = res3.get('result',{}).get('result',{}).get('value',[])
        print('\nSTEP3 popups count:', len(val3))
        for v in val3[:10]:
            print(v)
        
        ws.close()
        break
