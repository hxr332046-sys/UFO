import requests, json, websocket

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
targets = r.json()
for t in targets:
    if '9087' in str(t.get('url','')) and t.get('type') == 'page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        js = """
        (function() {
          const all = Array.from(document.querySelectorAll('*'));
          const results = [];
          
          for (const el of all) {
            const vm = el.__vue__ || el.__VUE__;
            if (!vm) continue;
            
            // 找包含 guide/base 相关表单字段的组件
            let data = vm.$data || vm;
            let found = false;
            
            // 检查直接属性
            if (data.entType !== undefined || data.distCode !== undefined || data.nameCode !== undefined || data.address !== undefined) {
              found = true;
            }
            
            // 检查 $data.form
            if (!found && data.form) {
              const f = data.form;
              if (f.entType !== undefined || f.distCode !== undefined || f.nameCode !== undefined || f.address !== undefined) {
                data = f;
                found = true;
              }
            }
            
            // 检查 $data.model / $data.ruleForm
            if (!found && data.model) {
              const m = data.model;
              if (m.entType !== undefined || m.distCode !== undefined || m.nameCode !== undefined || m.address !== undefined) {
                data = m;
                found = true;
              }
            }
            if (!found && data.ruleForm) {
              const rf = data.ruleForm;
              if (rf.entType !== undefined || rf.distCode !== undefined || rf.nameCode !== undefined || rf.address !== undefined) {
                data = rf;
                found = true;
              }
            }
            
            if (found) {
              const keys = Object.keys(data).filter(k => ['entType','nameCode','distCode','distCodeArr','address','streetCode','streetName','fzSign','regCapital','havaAdress','organize','industry','industrySpecial','namePre','nameMark'].includes(k));
              results.push({
                tag: el.tagName,
                className: el.className,
                id: el.id,
                keys: keys,
                sample: keys.reduce((acc, k) => { acc[k] = data[k]; return acc; }, {})
              });
            }
          }
          
          return JSON.stringify(results.slice(0, 5));
        })()
        """
        ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':js,'returnByValue':True}}))
        res = json.loads(ws.recv())
        val = res.get('result',{}).get('result',{}).get('value','[]')
        
        try:
            data = json.loads(val)
            print('FOUND', len(data), 'Vue components with form fields:')
            for i, item in enumerate(data):
                print(f'\n--- Component {i+1} ---')
                print(f'Tag: {item.get("tag")}')
                print(f'Class: {item.get("className","")[:100]}')
                print(f'Keys: {item.get("keys")}')
                print(f'Sample values: {json.dumps(item.get("sample"), ensure_ascii=False)}')
        except Exception as e:
            print('PARSE ERROR:', e)
            print('RAW:', val[:500])
        
        ws.close()
        break
