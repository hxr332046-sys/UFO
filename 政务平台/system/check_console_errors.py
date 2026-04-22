import requests, json, websocket

r = requests.get('http://127.0.0.1:9225/json', timeout=5)
targets = r.json()
for t in targets:
    if '9087' in str(t.get('url','')) and t.get('type') == 'page':
        ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=10)
        
        # 读取浏览器控制台日志
        js = """
        (function() {
          // 获取 window 上的错误日志（如果有的话）
          const errors = window.__ufo_errors || [];
          // 获取最近的 console 错误
          return JSON.stringify({
            href: location.href,
            hasVueErrors: !!window.__ufo_errors,
            errorCount: errors.length,
            lastError: errors.length > 0 ? errors[errors.length-1] : null
          });
        })()
        """
        ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':js,'returnByValue':True}}))
        res = json.loads(ws.recv())
        val = res.get('result',{}).get('result',{}).get('value','')
        print('CONSOLE:', val)
        
        # 获取页面上的 Vue 错误提示
        js2 = """
        (function() {
          const alerts = document.querySelectorAll('.el-message, .el-notification, [class*="error"], [class*="alert"]');
          return Array.from(alerts).slice(0, 5).map(el => ({
            className: el.className,
            text: el.textContent.trim().substring(0, 200)
          }));
        })()
        """
        ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':js2,'returnByValue':True}}))
        res2 = json.loads(ws.recv())
        val2 = res2.get('result',{}).get('result',{}).get('value',[])
        print('ALERTS:', val2)
        
        ws.close()
        break
